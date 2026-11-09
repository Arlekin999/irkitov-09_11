import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from json_parser import JsonParseError  # noqa: E402
from repl import Repl, ReplError, tokenize  # noqa: E402
from schema_validator import ValidationError  # noqa: E402

SEQUENCE_SAMPLE = PROJECT_DIR / "samples" / "sequence_sample.json"
ACTIVITY_SAMPLE = PROJECT_DIR / "samples" / "activity_sample.json"


class TokenizerTest(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(tokenize("load file.json"), ["load", "file.json"])
        self.assertEqual(tokenize("   "), [])

    def test_quotes(self):
        self.assertEqual(
            tokenize('load "my file.json"'), ["load", "my file.json"]
        )
        self.assertEqual(tokenize("export 'a b'"), ["export", "a b"])
        self.assertEqual(tokenize('say ""'), ["say", ""])

    def test_escapes(self):
        self.assertEqual(tokenize(r'"a\"b"'), ['a"b'])
        self.assertEqual(tokenize(r'"a\nb"'), ["a\nb"])

    def test_unterminated_quote(self):
        with self.assertRaises(ReplError):
            tokenize('load "abc')


class ReplTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = Path(self.temp_dir.name)
        self.messages = []
        self.repl = Repl(
            plugin_dir=PROJECT_DIR / "plugins",
            output_dir=self.output_dir,
            history_path=self.output_dir / "history.txt",
            out=self.messages.append,
        )
        self.repl.load_plugins()

    def output(self):
        return "\n".join(self.messages)

    def test_history_written(self):
        self.repl.execute("help")
        self.repl.execute("plugins")
        history = (self.output_dir / "history.txt").read_text(encoding="utf-8")
        self.assertEqual(history.splitlines(), ["help", "plugins"])

    def test_load_validate_and_render(self):
        self.repl.execute("load %s %s" % (SEQUENCE_SAMPLE, ACTIVITY_SAMPLE))
        self.assertEqual(len(self.repl.documents), 2)
        self.repl.execute("validate")
        self.assertIn("документ корректен", self.output())
        self.messages.clear()
        self.repl.execute("render sequence")
        self.assertIn("Customer -> OrderSystem: PlaceOrder", self.output())
        self.messages.clear()
        self.repl.execute("render activity")
        self.assertIn("Activity Diagram:", self.output())
        self.assertIn("NOT (inventoryAvailable AND NOT blacklisted)", self.output())

    def test_analyze(self):
        self.repl.execute("load %s" % ACTIVITY_SAMPLE)
        self.repl.execute("analyze")
        self.assertIn("Начальные узлы: StartOrderProcessing", self.output())
        self.assertIn("Тупиковый узел", self.output())

    def test_export_and_report(self):
        self.repl.execute("load %s %s" % (SEQUENCE_SAMPLE, ACTIVITY_SAMPLE))
        self.repl.execute("export mermaid")
        self.assertIn("sequenceDiagram", self.output())
        self.assertIn("flowchart TD", self.output())
        self.assertTrue((self.output_dir / "sequence-diagram.mmd").exists())
        self.assertTrue((self.output_dir / "activity-diagram.mmd").exists())
        self.messages.clear()
        self.repl.execute("report")
        self.assertTrue((self.output_dir / "sequence-diagram.md").exists())
        self.assertTrue((self.output_dir / "activity-diagram.md").exists())
        self.assertIn("Сохранено", self.output())

    def test_plugins_command(self):
        self.repl.execute("plugins")
        text = self.output()
        self.assertIn("mermaid", text)
        self.assertIn("exporters", text)

    def test_plugins_without_loader(self):
        repl = Repl(
            plugin_dir=PROJECT_DIR / "plugins",
            output_dir=self.output_dir,
            history_path=self.output_dir / "history-2.txt",
            out=self.messages.append,
        )
        repl.execute("plugins")
        self.assertIn("Плагины не загружены", self.output())

    def test_clear_and_help(self):
        self.repl.execute("load %s" % SEQUENCE_SAMPLE)
        self.repl.execute("clear")
        self.assertEqual(self.repl.documents, [])
        self.messages.clear()
        self.repl.execute("help")
        self.assertIn("load <файл>", self.output())

    def test_quit(self):
        self.repl.execute("quit")
        self.assertFalse(self.repl.running)

    def test_unknown_command(self):
        with self.assertRaises(ReplError):
            self.repl.execute("nonsense")

    def test_command_without_documents(self):
        with self.assertRaises(ReplError):
            self.repl.execute("validate")
        with self.assertRaises(ReplError):
            self.repl.execute("render sequence")
        with self.assertRaises(ReplError):
            self.repl.execute("analyze")

    def test_bad_usage(self):
        for command in ("render", "render wrong", "export", "load", "report wrong"):
            with self.assertRaises(ReplError):
                self.repl.execute(command)

    def test_load_invalid_json(self):
        bad = self.output_dir / "bad.json"
        bad.write_text('{"sequence": [}', encoding="utf-8")
        with self.assertRaises(JsonParseError):
            self.repl.execute("load %s" % bad)

    def test_load_invalid_schema_on_validate(self):
        bad = self.output_dir / "bad.json"
        bad.write_text('{"sequence": []}', encoding="utf-8")
        self.repl.execute("load %s" % bad)
        self.repl.execute("validate")
        self.assertIn("expected at least 1 item", self.output())

    def test_run_loop_with_input(self):
        repl = Repl(
            plugin_dir=PROJECT_DIR / "plugins",
            output_dir=self.output_dir,
            history_path=self.output_dir / "history.txt",
            out=self.messages.append,
        )
        inputs = iter(["load %s" % SEQUENCE_SAMPLE, "render sequence", "quit"])
        with mock.patch("builtins.input", side_effect=lambda prompt="": next(inputs)):
            repl.run()
        self.assertIn("Sequence Diagram:", self.output())
        self.assertFalse(repl.running)
        history = (self.output_dir / "history.txt").read_text(encoding="utf-8")
        self.assertIn("render sequence", history)

    def test_run_loop_eof(self):
        repl = Repl(
            plugin_dir=PROJECT_DIR / "plugins",
            output_dir=self.output_dir,
            out=self.messages.append,
        )
        with mock.patch("builtins.input", side_effect=EOFError):
            repl.run()
        self.assertIn("REPL диаграмм", self.output())


if __name__ == "__main__":
    unittest.main()
