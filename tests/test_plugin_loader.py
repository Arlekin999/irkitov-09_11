import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from plugin_loader import (  # noqa: E402
    PluginLoader,
    call_exporter,
    load_plugins,
    new_registry,
    run_validators,
)

GOOD_PLUGIN = """
NAME = "good"

def register(registry):
    registry["exporters"]["good"] = lambda document, kind: "exported:" + kind
"""

VALIDATOR_PLUGIN = """
NAME = "checker"

def register(registry):
    registry["validators"]["checker"] = lambda document: ["custom warning"]
"""

BAD_IMPORT_PLUGIN = """
NAME = "broken"
raise RuntimeError("boom")
"""

NO_NAME_PLUGIN = """
def register(registry):
    pass
"""

NO_REGISTER_PLUGIN = """
NAME = "no_register"
"""

CONFLICT_PLUGIN = """
NAME = "good"

def register(registry):
    registry["exporters"]["conflict"] = lambda document, kind: "conflict"
"""

BROKEN_REGISTER_PLUGIN = """
NAME = "crash"

def register(registry):
    raise ValueError("register failed")
"""


class PluginLoaderTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.directory = Path(self.temp_dir.name)

    def write(self, name, content):
        path = self.directory / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_successful_load(self):
        self.write("good.py", GOOD_PLUGIN)
        registry = new_registry()
        loader = PluginLoader(self.directory, registry=registry)
        self.assertEqual(loader.load_all(), ["good"])
        self.assertEqual(registry["exporters"]["good"]({}, "sequence"), "exported:sequence")
        self.assertEqual(loader.errors, [])

    def test_import_error_is_isolated(self):
        self.write("good.py", GOOD_PLUGIN)
        self.write("broken.py", BAD_IMPORT_PLUGIN)
        registry = new_registry()
        loader = PluginLoader(self.directory, registry=registry)
        names = loader.load_all()
        self.assertEqual(names, ["good"])
        self.assertEqual(len(loader.errors), 1)
        self.assertIn("ошибка импорта", loader.errors[0])
        self.assertIn("boom", loader.errors[0])
        self.assertIn("good", registry["exporters"])

    def test_missing_name_and_register(self):
        self.write("no_name.py", NO_NAME_PLUGIN)
        self.write("no_register.py", NO_REGISTER_PLUGIN)
        loader = PluginLoader(self.directory)
        loader.load_all()
        self.assertEqual(loader.loaded, [])
        self.assertEqual(len(loader.errors), 2)
        self.assertTrue(any("NAME" in error for error in loader.errors))
        self.assertTrue(any("register" in error for error in loader.errors))

    def test_name_conflict(self):
        self.write("good.py", GOOD_PLUGIN)
        self.write("zz_duplicate.py", CONFLICT_PLUGIN)
        registry = new_registry()
        loader = PluginLoader(self.directory, registry=registry)
        loader.load_all()
        self.assertEqual(len(loader.loaded), 1)
        self.assertTrue(any("конфликт имён" in error for error in loader.errors))
        self.assertNotIn("conflict", registry["exporters"])

    def test_register_exception(self):
        self.write("crash.py", BROKEN_REGISTER_PLUGIN)
        loader = PluginLoader(self.directory)
        loader.load_all()
        self.assertEqual(loader.loaded, [])
        self.assertTrue(any("ошибка регистрации" in error for error in loader.errors))

    def test_unique_module_names(self):
        good_path = self.write("good.py", GOOD_PLUGIN)
        other_path = self.write("other.py", GOOD_PLUGIN.replace('"good"', '"other"'))
        loader = PluginLoader(self.directory)
        loader.load_file(good_path)
        loader.load_file(other_path)
        good_name = loader._module_name(good_path)
        other_name = loader._module_name(other_path)
        self.assertNotEqual(good_name, other_name)
        self.assertTrue(good_name.startswith("_plugin_good_"))
        self.assertIn(good_name, sys.modules)
        self.assertIn(other_name, sys.modules)

    def test_missing_directory(self):
        loader = PluginLoader(self.directory / "missing")
        self.assertEqual(loader.discover(), [])
        self.assertEqual(loader.load_all(), [])

    def test_non_python_file_rejected(self):
        path = self.write("plugin.txt", "NAME = 'x'")
        loader = PluginLoader(self.directory)
        self.assertFalse(loader.load_file(path))
        self.assertTrue(any(".py" in error for error in loader.errors))

    def test_validator_plugin(self):
        self.write("checker.py", VALIDATOR_PLUGIN)
        loader = PluginLoader(self.directory)
        loader.load_all()
        self.assertEqual(run_validators(loader.registry, {}), ["custom warning"])

    def test_broken_validator_is_isolated(self):
        registry = new_registry()
        registry["validators"]["bad"] = lambda document: 1 / 0
        messages = run_validators(registry, {})
        self.assertEqual(len(messages), 1)
        self.assertIn("exception", messages[0])

    def test_missing_exporter(self):
        with self.assertRaises(KeyError):
            call_exporter(new_registry(), "mermaid", {}, "sequence")

    def test_mermaid_plugin(self):
        loader = load_plugins(PROJECT_DIR / "plugins")
        self.assertIn("mermaid", loader.plugin_names())
        sequence = call_exporter(
            loader.registry,
            "mermaid",
            {"sequence": [{"actor": "A", "action": "Ping", "target": "B"}]},
            "sequence",
        )
        self.assertIn("sequenceDiagram", sequence)
        self.assertIn("A->>B: Ping", sequence)
        activity = call_exporter(
            loader.registry,
            "mermaid",
            {
                "activity": [
                    {"step": "Start", "condition": "ok", "true": "End", "false": "Wait"},
                    {"step": "Wait", "next": "Start"},
                ]
            },
            "activity",
        )
        self.assertIn("flowchart TD", activity)
        self.assertIn("Start -->|ok| End", activity)
        self.assertIn("Start -.->|NOT (ok)| Wait", activity)


if __name__ == "__main__":
    unittest.main()
