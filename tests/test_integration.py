import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import main as app  # noqa: E402
from activity_diagram import ActivityDiagram  # noqa: E402
from graph_analysis import analyze_steps  # noqa: E402
from markdown_writer import activity_markdown, sequence_markdown  # noqa: E402
from sequence_diagram import SequenceDiagram  # noqa: E402

SEQUENCE_SAMPLE = PROJECT_DIR / "samples" / "sequence_sample.json"
ACTIVITY_SAMPLE = PROJECT_DIR / "samples" / "activity_sample.json"

EXPECTED_SEQUENCE = """Sequence Diagram:
Customer -> OrderSystem: PlaceOrder(item: Milk, quantity: 2)
OrderSystem -> Order: CreateOrder(id: 123, items: [Milk])
Order -> PaymentGateway: ProcessPayment(amount: 50)"""

EXPECTED_ACTIVITY = """Activity Diagram:
StartOrderProcessing -> CheckInventory
CheckInventory -> ProcessPayment (if inventoryAvailable AND NOT blacklisted)
CheckInventory -> NotifyCustomer (if NOT (inventoryAvailable AND NOT blacklisted))
ProcessPayment -> CompleteOrder
NotifyCustomer -> EndOrderProcessing"""


class EndToEndTest(unittest.TestCase):
    def test_sequence_diagram_render(self):
        document = app.load_document(SEQUENCE_SAMPLE)
        self.assertEqual(document.kind, "sequence")
        self.assertEqual(app.render_sequence(document), EXPECTED_SEQUENCE)
        self.assertEqual(
            document.data["sequence"][0]["parameters"], ["item: Milk", "quantity: 2"]
        )

    def test_activity_diagram_render(self):
        document = app.load_document(ACTIVITY_SAMPLE)
        self.assertEqual(document.kind, "activity")
        self.assertEqual(app.render_activity(document), EXPECTED_ACTIVITY)

    def test_sequence_markdown(self):
        document = app.load_document(SEQUENCE_SAMPLE)
        text = sequence_markdown(document.data)
        self.assertIn("# Диаграмма последовательности", text)
        self.assertIn("| № | Отправитель | Получатель |", text)
        self.assertIn("PlaceOrder", text)
        self.assertIn("```text", text)
        self.assertIn("PaymentGateway", text)

    def test_activity_markdown_analysis_block(self):
        document = app.load_document(ACTIVITY_SAMPLE)
        analysis = analyze_steps(document.data["activity"])
        text = activity_markdown(document.data, analysis)
        self.assertIn("## Анализ", text)
        self.assertIn("Циклы: не обнаружены", text)
        self.assertIn("Недостижимые шаги: нет", text)
        self.assertIn("CompleteOrder", text)
        self.assertIn("NOT (inventoryAvailable AND NOT blacklisted)", text)

    def test_diagram_classes(self):
        sequence = SequenceDiagram.from_document(app.load_document(SEQUENCE_SAMPLE).data)
        self.assertEqual(
            sequence.participants(),
            ["Customer", "OrderSystem", "Order", "PaymentGateway"],
        )
        activity = ActivityDiagram.from_document(app.load_document(ACTIVITY_SAMPLE).data)
        self.assertEqual(len(activity.transitions), 5)
        self.assertEqual(activity.transitions[1].label, "inventoryAvailable AND NOT blacklisted")
        self.assertEqual(
            activity.transitions[2].label,
            "NOT (inventoryAvailable AND NOT blacklisted)",
        )


class CliTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output = Path(self.temp_dir.name)

    def run_cli(self, arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = app.main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_render_and_report(self):
        code, out, err = self.run_cli(
            [
                "--file",
                str(SEQUENCE_SAMPLE),
                "--render",
                "sequence",
                "--output",
                str(self.output),
                "--plugins-dir",
                str(PROJECT_DIR / "plugins"),
            ]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("Sequence Diagram:", out)
        self.assertIn(EXPECTED_SEQUENCE, out)
        report = self.output / "sequence-diagram.md"
        self.assertTrue(report.exists())
        self.assertIn("Диаграмма последовательности", report.read_text(encoding="utf-8"))

    def test_analyze_activity(self):
        code, out, err = self.run_cli(
            [
                "--file",
                str(ACTIVITY_SAMPLE),
                "--analyze",
                "--output",
                str(self.output),
            ]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("Начальные узлы: StartOrderProcessing", out)
        self.assertIn("Тупиковый узел", out)
        self.assertTrue((self.output / "activity-diagram.md").exists())

    def test_export_mermaid(self):
        code, out, err = self.run_cli(
            [
                "--file",
                str(SEQUENCE_SAMPLE),
                "--export",
                "mermaid",
                "--output",
                str(self.output),
            ]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("sequenceDiagram", out)
        exported = self.output / "sequence-diagram.mmd"
        self.assertTrue(exported.exists())
        self.assertIn("Customer->>OrderSystem", exported.read_text(encoding="utf-8"))

    def test_missing_file_fails(self):
        code, out, err = self.run_cli(["--file", str(self.output / "nope.json")])
        self.assertEqual(code, 1)
        self.assertIn("Ошибка", err)

    def test_invalid_schema_fails(self):
        bad = self.output / "bad.json"
        bad.write_text('{"sequence": []}', encoding="utf-8")
        code, out, err = self.run_cli(["--file", str(bad)])
        self.assertEqual(code, 1)
        self.assertIn("expected at least 1 item", err)

    def test_help_without_arguments(self):
        code, out, err = self.run_cli([])
        self.assertEqual(code, 0)
        self.assertIn("--repl", out)

    def test_unknown_argument(self):
        with self.assertRaises(SystemExit):
            app.parse_arguments(["--nonsense"])


if __name__ == "__main__":
    unittest.main()
