import json
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from json_parser import (  # noqa: E402
    JsonParseError,
    JsonParser,
    load_json_file,
    parse_json,
)


class JsonParserValidTest(unittest.TestCase):
    def test_primitives(self):
        self.assertIsNone(parse_json("null"))
        self.assertIs(parse_json("true"), True)
        self.assertIs(parse_json("false"), False)
        self.assertEqual(parse_json('"text"'), "text")
        self.assertEqual(parse_json("42"), 42)
        self.assertEqual(parse_json("-7"), -7)
        self.assertEqual(parse_json("3.5"), 3.5)
        self.assertEqual(parse_json("1e3"), 1000.0)
        self.assertEqual(parse_json("-2.5E-2"), -0.025)

    def test_containers(self):
        self.assertEqual(parse_json("[]"), [])
        self.assertEqual(parse_json("{}"), {})
        self.assertEqual(parse_json("[1, 2, [3]]"), [1, 2, [3]])
        self.assertEqual(parse_json('{"a": 1, "b": [true, null]}'), {
            "a": 1,
            "b": [True, None],
        })

    def test_arbitrary_key_order(self):
        text = '{"z": 1, "a": {"y": 2, "b": 3}, "m": [4]}'
        self.assertEqual(
            parse_json(text),
            {"z": 1, "a": {"y": 2, "b": 3}, "m": [4]},
        )

    def test_whitespace_and_bom(self):
        self.assertEqual(parse_json('\n\t {"a" : 1 } \r\n'), {"a": 1})
        self.assertEqual(parse_json("\ufeff[1, 2]"), [1, 2])

    def test_escape_sequences(self):
        value = parse_json(r'"a\"b\\c\/d\be\ff\ng\rh\ti"')
        self.assertEqual(value, 'a"b\\c/d\be\ff\ng\rh\ti')

    def test_unicode_escape(self):
        self.assertEqual(parse_json(r'"\u041f\u0440\u0438\u0432\u0435\u0442"'), "Привет")
        self.assertEqual(parse_json(r'"\uD83D\uDE00"'), "\U0001F600")
        self.assertEqual(parse_json(r'"\u0041"'), "A")

    def test_big_numbers(self):
        big = 10 ** 30
        self.assertEqual(parse_json(str(big)), big)
        self.assertEqual(
            parse_json("123456789012345678901234567890"),
            int("123456789012345678901234567890"),
        )
        self.assertAlmostEqual(parse_json("1.7976931348623157e308"), 1.7976931348623157e308)

    def test_deep_nesting_within_limit(self):
        depth = 500
        text = "[" * depth + "1" + "]" * depth
        value = parse_json(text)
        for _ in range(depth - 1):
            value = value[0]
        self.assertEqual(value, [1])

    def test_matches_standard_library(self):
        text = (
            '{"sequence": [{"actor": "Customer", "action": "PlaceOrder", '
            '"target": "OrderSystem", "parameters": ["item: Milk", "quantity: 2"]}], '
            '"flag": true, "number": -12.75e3, "empty": {}, "list": [null, false]}'
        )
        self.assertEqual(parse_json(text), json.loads(text))

    def test_file_loading(self):
        sample = PROJECT_DIR / "samples" / "sequence_sample.json"
        document = load_json_file(sample)
        self.assertIn("sequence", document)
        self.assertEqual(len(document["sequence"]), 3)


class JsonParserErrorTest(unittest.TestCase):
    def assert_error(self, text, fragment, position=None):
        with self.assertRaises(JsonParseError) as context:
            parse_json(text)
        message = str(context.exception)
        self.assertIn(fragment, message)
        if position is not None:
            self.assertIn("at %s" % position, message)
        return context.exception

    def test_unterminated_string_position(self):
        error = self.assert_error('{\n  "a": "abc\n}', "Unterminated string", "2:8")
        self.assertEqual(error.line, 2)
        self.assertEqual(error.column, 8)

    def test_trailing_comma(self):
        self.assert_error('{"a": 1,}', "Expected string key")
        self.assert_error("[1, 2, ]", "Unexpected character")

    def test_leading_zero(self):
        self.assert_error("012", "Leading zeros are not allowed", "1:1")

    def test_invalid_escape(self):
        self.assert_error(r'"\x41"', "Invalid escape sequence")

    def test_truncated_unicode(self):
        self.assert_error(r'"\u12"', "Truncated \\u escape")

    def test_unpaired_surrogate(self):
        self.assert_error(r'"\uD800"', "Unpaired high surrogate")
        self.assert_error(r'"\uDC00"', "Unpaired low surrogate")

    def test_control_character(self):
        self.assert_error('"a\x01b"', "Control character")

    def test_missing_colon_and_bracket(self):
        self.assert_error('{"a" 1}', "Expected ':' after key")
        self.assert_error("[1, 2", "Unterminated array")
        self.assert_error('{"a": 1', "Unterminated object")

    def test_trailing_content(self):
        self.assert_error("1 2", "Unexpected trailing character")
        self.assert_error("", "Unexpected end of input")

    def test_depth_limit(self):
        text = "[" * 600 + "]" * 600
        self.assert_error(text, "Maximum nesting depth")

    def test_custom_depth_limit(self):
        with self.assertRaises(JsonParseError):
            JsonParser("[[[1]]]", max_depth=2).parse()

    def test_duplicate_keys_last_wins(self):
        self.assertEqual(parse_json('{"a": 1, "a": 2}'), {"a": 2})

    def test_number_errors(self):
        self.assert_error("-", "Invalid number")
        self.assert_error("1.", "expected digit after '.'")
        self.assert_error("1e", "expected exponent digits")


if __name__ == "__main__":
    unittest.main()
