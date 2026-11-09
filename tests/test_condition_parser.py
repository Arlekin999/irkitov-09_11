import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from condition_parser import (  # noqa: E402
    Binary,
    Comparison,
    ConditionSyntaxError,
    Not,
    Variable,
    negate,
    normalize_condition,
    parse_condition,
)


class ConditionParserTest(unittest.TestCase):
    def test_variable_and_normalization(self):
        self.assertEqual(normalize_condition("inventoryAvailable"), "inventoryAvailable")
        self.assertEqual(
            normalize_condition("inventoryAvailable AND NOT blacklisted"),
            "inventoryAvailable AND NOT blacklisted",
        )

    def test_operator_precedence(self):
        node = parse_condition("a OR b AND NOT c")
        self.assertIsInstance(node, Binary)
        self.assertEqual(node.op, "OR")
        self.assertEqual(node.right.op, "AND")
        self.assertIsInstance(node.right.right, Not)
        self.assertIsInstance(node.right.right.operand, Variable)
        self.assertEqual(node.to_text(), "a OR b AND NOT c")

    def test_parentheses(self):
        self.assertEqual(normalize_condition("(a OR b) AND c"), "(a OR b) AND c")
        self.assertEqual(normalize_condition("((a))"), "a")
        self.assertEqual(normalize_condition("NOT (a AND b)"), "NOT (a AND b)")
        self.assertEqual(normalize_condition("NOT a AND b"), "NOT a AND b")

    def test_comparisons(self):
        for text in ("a == 1", "a != 2", "a < 3", "a > 4", "a <= 5", "a >= 6"):
            node = parse_condition(text)
            self.assertIsInstance(node, Comparison)
            self.assertEqual(node.to_text(), text)

    def test_comparison_has_higher_priority_than_logic(self):
        node = parse_condition("a == 1 AND b != 2 OR c < 3")
        self.assertEqual(node.op, "OR")
        self.assertEqual(node.left.op, "AND")
        self.assertEqual(node.to_text(), "a == 1 AND b != 2 OR c < 3")

    def test_string_and_number_literals(self):
        node = parse_condition('status == "paid" AND amount >= 10.5')
        self.assertEqual(node.to_text(), "status == 'paid' AND amount >= 10.5")

    def test_negation(self):
        node = parse_condition("a AND NOT b")
        self.assertEqual(negate(node).to_text(), "NOT (a AND NOT b)")
        simple = negate(parse_condition("a"))
        self.assertEqual(simple.to_text(), "NOT a")

    def test_variables_collection(self):
        node = parse_condition("a AND (b OR NOT c) AND a == 1")
        self.assertEqual(node.variables(), {"a", "b", "c"})

    def test_evaluation(self):
        node = parse_condition("inventoryAvailable AND NOT blacklisted")
        self.assertTrue(node.evaluate({"inventoryAvailable": True, "blacklisted": False}))
        self.assertFalse(node.evaluate({"inventoryAvailable": True, "blacklisted": True}))
        comparison = parse_condition("amount >= 10")
        self.assertTrue(comparison.evaluate({"amount": 15}))
        self.assertFalse(comparison.evaluate({"amount": 5}))
        with self.assertRaises(KeyError):
            parse_condition("missing").evaluate({})

    def test_case_insensitive_keywords(self):
        self.assertEqual(normalize_condition("a and not b"), "a AND NOT b")

    def test_identifiers_with_dots(self):
        self.assertEqual(
            normalize_condition("order.status == 1"), "order.status == 1"
        )


class ConditionParserErrorTest(unittest.TestCase):
    def assert_error(self, text, fragment, position=None):
        with self.assertRaises(ConditionSyntaxError) as context:
            parse_condition(text)
        message = str(context.exception)
        self.assertIn(fragment, message)
        if position is not None:
            self.assertTrue(message.endswith("at %s" % position), message)

    def test_empty_condition(self):
        self.assert_error("", "Empty condition", "1:1")
        self.assert_error("   ", "Empty condition")

    def test_missing_operand(self):
        self.assert_error("a AND", "Expected expression", "1:6")
        self.assert_error("AND a", "Expected expression, got keyword", "1:1")

    def test_unbalanced_parentheses(self):
        self.assert_error("(a AND b", "Expected ')'")
        self.assert_error("a AND b)", "Unexpected token")

    def test_chained_comparison(self):
        self.assert_error("a < b < c", "Chained comparisons are not supported")

    def test_unterminated_string(self):
        self.assert_error('a == "abc', "Unterminated string literal")

    def test_unexpected_character(self):
        self.assert_error("a & b", "Unexpected character")
        self.assert_error("a = 1", "Unexpected character")

    def test_multi_line_position(self):
        self.assert_error("a AND\nNOT", "Expected expression", "2:4")


if __name__ == "__main__":
    unittest.main()
