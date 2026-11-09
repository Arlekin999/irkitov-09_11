import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from graph_analysis import (  # noqa: E402
    analyze_steps,
    build_graph,
    reachable_from,
    tarjan_scc,
    topological_sort,
)


class GraphAnalysisTest(unittest.TestCase):
    def test_build_graph(self):
        nodes, adjacency = build_graph(
            [
                {"step": "A", "next": ["B", "C"]},
                {"step": "B", "next": "C"},
                {"step": "C", "condition": "ok", "true": "D", "false": "E"},
            ]
        )
        self.assertEqual(nodes, ["A", "B", "C", "D", "E"])
        self.assertIn(("B", ""), adjacency["A"])
        self.assertIn(("D", "ok"), adjacency["C"])
        self.assertIn(("E", "NOT (ok)"), adjacency["C"])

    def test_acyclic_graph(self):
        steps = [
            {"step": "A", "next": "B"},
            {"step": "B", "next": ["C", "D"]},
            {"step": "C", "next": "End"},
            {"step": "D", "next": "End"},
            {"step": "End", "next": []},
        ]
        analysis = analyze_steps(steps)
        self.assertEqual(analysis.cycles, [])
        self.assertEqual(analysis.start_nodes, ["A"])
        self.assertEqual(analysis.unreachable, [])
        self.assertEqual(analysis.dead_ends, ["End"])
        self.assertEqual(analysis.topological_order, ["A", "B", "C", "D", "End"])
        self.assertEqual(analysis.warnings, [])
        self.assertTrue(analysis.is_acyclic)

    def test_simple_cycle(self):
        steps = [
            {"step": "A", "next": "B"},
            {"step": "B", "next": "C"},
            {"step": "C", "next": "A"},
        ]
        analysis = analyze_steps(steps)
        self.assertEqual(analysis.cycles, [["A", "B", "C"]])
        self.assertIsNone(analysis.topological_order)
        self.assertTrue(any("цикл" in warning.lower() for warning in analysis.warnings))
        self.assertTrue(
            any("Топологическая сортировка невозможна" in warning for warning in analysis.warnings)
        )

    def test_multiple_cycles(self):
        steps = [
            {"step": "A", "next": "B"},
            {"step": "B", "next": "A"},
            {"step": "C", "next": "D"},
            {"step": "D", "next": "C"},
            {"step": "Start", "next": ["A", "C"]},
        ]
        analysis = analyze_steps(steps)
        self.assertEqual(len(analysis.cycles), 2)
        self.assertEqual(sorted(analysis.cycles), [["A", "B"], ["C", "D"]])

    def test_self_loop(self):
        steps = [
            {"step": "Start", "next": "A"},
            {"step": "A", "next": ["A", "End"]},
            {"step": "End", "next": []},
        ]
        analysis = analyze_steps(steps)
        self.assertEqual(analysis.cycles, [["A"]])
        self.assertIsNone(analysis.topological_order)

    def test_unreachable_steps(self):
        steps = [
            {"step": "A", "next": "B"},
            {"step": "B", "next": []},
            {"step": "C", "next": "D"},
            {"step": "D", "next": ["C", "E"]},
            {"step": "E", "next": []},
        ]
        analysis = analyze_steps(steps)
        self.assertEqual(analysis.start_nodes, ["A"])
        self.assertEqual(analysis.unreachable, ["C", "D", "E"])
        self.assertTrue(any("недостижим" in warning.lower() for warning in analysis.warnings))

    def test_multiple_start_nodes(self):
        steps = [
            {"step": "A", "next": "B"},
            {"step": "C", "next": "B"},
            {"step": "B", "next": []},
        ]
        analysis = analyze_steps(steps)
        self.assertEqual(analysis.start_nodes, ["A", "C"])
        self.assertTrue(
            any("несколько начальных узлов" in warning.lower() for warning in analysis.warnings)
        )

    def test_dead_end_warnings(self):
        steps = [
            {"step": "A", "next": ["B", "EndOk", "End"]},
            {"step": "B", "next": []},
            {"step": "EndOk", "next": []},
            {"step": "End", "next": []},
        ]
        analysis = analyze_steps(steps)
        self.assertEqual(analysis.dead_ends, ["B", "EndOk", "End"])
        dead_end_warnings = [
            warning for warning in analysis.warnings if "Тупиковый узел" in warning
        ]
        self.assertEqual(len(dead_end_warnings), 1)
        self.assertIn("B", dead_end_warnings[0])

    def test_no_start_nodes(self):
        steps = [
            {"step": "A", "next": "B"},
            {"step": "B", "next": "A"},
        ]
        analysis = analyze_steps(steps)
        self.assertEqual(analysis.start_nodes, [])
        self.assertTrue(any("начального узла" in warning for warning in analysis.warnings))

    def test_tarjan_components(self):
        nodes = ["A", "B", "C", "D", "E"]
        adjacency = {
            "A": [("B", "")],
            "B": [("C", "")],
            "C": [("A", ""), ("D", "")],
            "D": [("E", "")],
            "E": [("D", "")],
        }
        components = tarjan_scc(nodes, adjacency)
        self.assertEqual(sorted(sorted(component) for component in components),
                         [["A", "B", "C"], ["D", "E"]])

    def test_topological_sort_detects_cycle(self):
        nodes = ["A", "B"]
        adjacency = {"A": [("B", "")], "B": [("A", "")]}
        self.assertIsNone(topological_sort(nodes, adjacency))

    def test_reachable_from(self):
        adjacency = {
            "A": [("B", "")],
            "B": [("C", "")],
            "C": [],
            "D": [("C", "")],
        }
        self.assertEqual(reachable_from(adjacency, ["A"]), {"A", "B", "C"})

    def test_summary_lines(self):
        steps = [
            {"step": "A", "next": "B"},
            {"step": "B", "next": "A"},
        ]
        lines = analyze_steps(steps).summary_lines()
        text = "\n".join(lines)
        self.assertIn("Цикл: A -> B -> A", text)
        self.assertIn("Недостижимые шаги", text)
        self.assertIn("Предупреждения", text)


if __name__ == "__main__":
    unittest.main()
