import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from schema_validator import (  # noqa: E402
    ValidationError,
    kind_of,
    validate,
    validate_document,
    validate_or_raise,
)

SEQUENCE = {
    "sequence": [
        {"actor": "Customer", "action": "PlaceOrder", "target": "OrderSystem"},
        {
            "actor": "OrderSystem",
            "action": "CreateOrder",
            "target": "Order",
            "parameters": ["id: 1"],
        },
    ]
}

ACTIVITY = {
    "activity": [
        {"step": "Start", "next": "Check"},
        {"step": "Check", "condition": "ok", "true": "Pay", "false": "Notify"},
        {"step": "Pay", "next": ["End", "Notify"]},
        {"step": "Notify", "next": "End"},
    ]
}


class SchemaValidatorTest(unittest.TestCase):
    def test_valid_documents(self):
        self.assertEqual(validate_document(SEQUENCE), [])
        self.assertEqual(validate_document(ACTIVITY), [])
        self.assertEqual(validate_or_raise(SEQUENCE), "sequence")
        self.assertEqual(validate_or_raise(ACTIVITY), "activity")

    def test_kind_detection(self):
        self.assertEqual(kind_of(SEQUENCE), "sequence")
        self.assertEqual(kind_of(ACTIVITY), "activity")
        with self.assertRaises(ValidationError):
            kind_of({"unknown": []})
        with self.assertRaises(ValidationError):
            kind_of([])

    def test_missing_required_field(self):
        document = {"sequence": [{"actor": "A", "action": "B"}]}
        issues = validate_document(document)
        self.assertEqual(len(issues), 1)
        self.assertIn("sequence[0].target: required field is missing", issues[0])

    def test_wrong_field_type_path(self):
        document = {
            "sequence": [
                {"actor": "A", "action": "B", "target": "C"},
                {
                    "actor": "A",
                    "action": "B",
                    "target": "C",
                    "parameters": "not-an-array",
                },
            ]
        }
        issues = validate_document(document)
        self.assertEqual(len(issues), 1)
        self.assertEqual(
            issues[0], "sequence[1].parameters: expected array, got string"
        )

    def test_parameters_items_type(self):
        document = {
            "sequence": [
                {"actor": "A", "action": "B", "target": "C", "parameters": [1]}
            ]
        }
        issues = validate_document(document)
        self.assertIn("sequence[0].parameters[0]: expected string, got integer", issues)

    def test_empty_arrays(self):
        self.assertIn(
            "sequence: expected at least 1 item(s), got 0",
            validate_document({"sequence": []}),
        )
        self.assertIn(
            "activity: expected at least 1 item(s), got 0",
            validate_document({"activity": []}),
        )

    def test_empty_string_value(self):
        document = {"sequence": [{"actor": "", "action": "B", "target": "C"}]}
        issues = validate_document(document)
        self.assertIn("sequence[0].actor: expected length >= 1, got 0", issues)

    def test_unknown_root_field(self):
        issues = validate_document({"sequence": [], "extra": 1})
        self.assertIn("extra: unexpected field", issues)

    def test_activity_condition_rules(self):
        cases = [
            ({"step": "A", "condition": "x", "true": "B"}, "condition requires field 'false'"),
            ({"step": "A", "condition": "x", "false": "B"}, "condition requires field 'true'"),
            ({"step": "A"}, "expected 'next' or 'condition'"),
            (
                {"step": "A", "next": "B", "condition": "x", "true": "B", "false": "C"},
                "mutually exclusive",
            ),
        ]
        for step, fragment in cases:
            issues = validate_document({"activity": [step, {"step": "B", "next": []}]})
            self.assertTrue(
                any(fragment in issue for issue in issues),
                "%r not found in %r" % (fragment, issues),
            )

    def test_activity_next_list_items(self):
        document = {"activity": [{"step": "A", "next": ["B", 5]}, {"step": "B", "next": []}]}
        issues = validate_document(document)
        self.assertTrue(any("activity[0].next[1]: expected non-empty string" in issue for issue in issues))

    def test_rules_engine_directly(self):
        schema = {
            "type": "object",
            "allow_extra": False,
            "fields": {
                "name": {"type": "str", "required": True, "min_length": 2},
                "level": {"type": "int", "required": False, "min": 0, "max": 5},
                "tags": {"type": "array", "items": {"type": "str"}},
            },
        }
        self.assertEqual(validate({"name": "ok", "level": 3}, schema), [])
        issues = validate({"name": "x", "level": 9, "tags": [1], "other": 0}, schema)
        self.assertIn("name: expected length >= 2, got 1", issues)
        self.assertIn("level: expected <= 5, got 9", issues)
        self.assertIn("tags[0]: expected string, got integer", issues)
        self.assertIn("other: unexpected field", issues)

    def test_root_type_errors(self):
        self.assertIn(
            "<root>: expected object with key 'sequence' or 'activity'",
            validate_document([1, 2]),
        )


if __name__ == "__main__":
    unittest.main()
