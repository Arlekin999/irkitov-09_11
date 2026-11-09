"""Собственный парсер JSON (без использования стандартного модуля json).

Поддерживаются все типы JSON: объект, массив, строка (с escape-последовательностями
\\" \\\\ \\/ \\b \\f \\n \\r \\t \\uXXXX), число (int и float), true, false, null.
Ошибки сообщаются с позицией в формате "строка:столбец".
"""

from __future__ import annotations

import sys
from bisect import bisect_right
from pathlib import Path
from typing import Any, List

MAX_DEPTH = 512

_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}

_WHITESPACE = " \t\n\r"
_HEX_DIGITS = "0123456789abcdefABCDEF"


class JsonParseError(ValueError):
    """Ошибка разбора JSON с указанием позиции."""

    def __init__(self, message: str, line: int, column: int, position: int):
        self.message = message
        self.line = line
        self.column = column
        self.position = position
        super().__init__("%s at %d:%d" % (message, line, column))

    def __str__(self) -> str:
        return "%s at %d:%d" % (self.message, self.line, self.column)


class JsonParser:
    """Рекурсивный парсер JSON с ограничением глубины вложенности."""

    def __init__(self, text: str, max_depth: int = MAX_DEPTH):
        if text.startswith("\ufeff"):
            text = text[1:]
        self.text = text
        self.length = len(text)
        self.pos = 0
        self.max_depth = max_depth
        self._line_offsets = self._build_line_offsets(text)

    @staticmethod
    def _build_line_offsets(text: str) -> List[int]:
        offsets = [0]
        index = text.find("\n")
        while index != -1:
            offsets.append(index + 1)
            index = text.find("\n", index + 1)
        return offsets

    def _line_column(self, position: int) -> tuple:
        line_index = bisect_right(self._line_offsets, position) - 1
        if line_index < 0:
            line_index = 0
        return line_index + 1, position - self._line_offsets[line_index] + 1

    def _error(self, message: str, position: int = None) -> JsonParseError:
        if position is None:
            position = self.pos
        line, column = self._line_column(position)
        return JsonParseError(message, line, column, position)

    def parse(self) -> Any:
        previous_limit = sys.getrecursionlimit()
        safe_limit = min(max(previous_limit, self.max_depth * 4 + 200), 100000)
        sys.setrecursionlimit(safe_limit)
        try:
            value = self._parse_value(0)
        except RecursionError:
            raise self._error(
                "Maximum nesting depth (%d) exceeded" % self.max_depth
            )
        finally:
            sys.setrecursionlimit(previous_limit)
        self._skip_whitespace()
        if self.pos < self.length:
            raise self._error("Unexpected trailing character %r" % self.text[self.pos])
        return value

    def _skip_whitespace(self) -> None:
        while self.pos < self.length and self.text[self.pos] in _WHITESPACE:
            self.pos += 1

    def _parse_value(self, depth: int) -> Any:
        if depth > self.max_depth:
            raise self._error(
                "Maximum nesting depth (%d) exceeded" % self.max_depth
            )
        self._skip_whitespace()
        if self.pos >= self.length:
            raise self._error("Unexpected end of input")
        char = self.text[self.pos]
        if char == "{":
            return self._parse_object(depth)
        if char == "[":
            return self._parse_array(depth)
        if char == '"':
            return self._parse_string()
        if char == "-" or char.isdigit():
            return self._parse_number()
        if self.text.startswith("true", self.pos):
            self.pos += 4
            return True
        if self.text.startswith("false", self.pos):
            self.pos += 5
            return False
        if self.text.startswith("null", self.pos):
            self.pos += 4
            return None
        raise self._error("Unexpected character %r" % char)

    def _parse_object(self, depth: int) -> dict:
        result = {}
        self.pos += 1
        self._skip_whitespace()
        if self.pos < self.length and self.text[self.pos] == "}":
            self.pos += 1
            return result
        while True:
            self._skip_whitespace()
            if self.pos >= self.length:
                raise self._error("Unterminated object")
            if self.text[self.pos] != '"':
                raise self._error("Expected string key")
            key = self._parse_string()
            self._skip_whitespace()
            if self.pos >= self.length or self.text[self.pos] != ":":
                raise self._error("Expected ':' after key")
            self.pos += 1
            value = self._parse_value(depth + 1)
            result[key] = value
            self._skip_whitespace()
            if self.pos >= self.length:
                raise self._error("Unterminated object")
            char = self.text[self.pos]
            if char == ",":
                self.pos += 1
                continue
            if char == "}":
                self.pos += 1
                return result
            raise self._error("Expected ',' or '}' in object")

    def _parse_array(self, depth: int) -> list:
        result = []
        self.pos += 1
        self._skip_whitespace()
        if self.pos < self.length and self.text[self.pos] == "]":
            self.pos += 1
            return result
        while True:
            result.append(self._parse_value(depth + 1))
            self._skip_whitespace()
            if self.pos >= self.length:
                raise self._error("Unterminated array")
            char = self.text[self.pos]
            if char == ",":
                self.pos += 1
                continue
            if char == "]":
                self.pos += 1
                return result
            raise self._error("Expected ',' or ']' in array")

    def _parse_string(self) -> str:
        start = self.pos
        self.pos += 1
        chars = []
        while True:
            if self.pos >= self.length:
                raise self._error("Unterminated string", start)
            char = self.text[self.pos]
            if char == '"':
                self.pos += 1
                return "".join(chars)
            if char == "\\":
                self.pos += 1
                chars.append(self._parse_escape())
                continue
            if char in "\n\r":
                raise self._error("Unterminated string", start)
            if ord(char) < 0x20:
                raise self._error(
                    "Control character %r in string" % char
                )
            chars.append(char)
            self.pos += 1

    def _parse_escape(self) -> str:
        if self.pos >= self.length:
            raise self._error("Unterminated escape sequence")
        char = self.text[self.pos]
        if char in _ESCAPES:
            self.pos += 1
            return _ESCAPES[char]
        if char == "u":
            return self._parse_unicode_escape()
        raise self._error("Invalid escape sequence \\%s" % char)

    def _parse_unicode_escape(self) -> str:
        code = self._read_hex4()
        if 0xD800 <= code <= 0xDBFF:
            if self.text.startswith("\\u", self.pos):
                saved = self.pos
                self.pos += 1
                low = self._read_hex4()
                if 0xDC00 <= low <= 0xDFFF:
                    return chr(0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00))
                self.pos = saved
                raise self._error("Unpaired high surrogate")
            raise self._error("Unpaired high surrogate")
        if 0xDC00 <= code <= 0xDFFF:
            raise self._error("Unpaired low surrogate")
        return chr(code)

    def _read_hex4(self) -> int:
        self.pos += 1
        start = self.pos
        digits = self.text[self.pos:self.pos + 4]
        if len(digits) != 4:
            raise self._error("Truncated \\u escape", start - 1)
        for digit in digits:
            if digit not in _HEX_DIGITS:
                raise self._error("Invalid \\u escape %r" % digits, start - 1)
        self.pos += 4
        return int(digits, 16)

    def _parse_number(self) -> Any:
        start = self.pos
        if self.pos < self.length and self.text[self.pos] == "-":
            self.pos += 1
        if self.pos >= self.length:
            raise self._error("Invalid number", start)
        if self.text[self.pos] == "0":
            self.pos += 1
            if self.pos < self.length and self.text[self.pos].isdigit():
                raise self._error("Leading zeros are not allowed", start)
        elif self.text[self.pos].isdigit():
            while self.pos < self.length and self.text[self.pos].isdigit():
                self.pos += 1
        else:
            raise self._error("Invalid number", start)

        is_float = False
        if self.pos < self.length and self.text[self.pos] == ".":
            is_float = True
            self.pos += 1
            if self.pos >= self.length or not self.text[self.pos].isdigit():
                raise self._error("Invalid number: expected digit after '.'", start)
            while self.pos < self.length and self.text[self.pos].isdigit():
                self.pos += 1
        if self.pos < self.length and self.text[self.pos] in "eE":
            is_float = True
            self.pos += 1
            if self.pos < self.length and self.text[self.pos] in "+-":
                self.pos += 1
            if self.pos >= self.length or not self.text[self.pos].isdigit():
                raise self._error("Invalid number: expected exponent digits", start)
            while self.pos < self.length and self.text[self.pos].isdigit():
                self.pos += 1

        raw = self.text[start:self.pos]
        try:
            return float(raw) if is_float else int(raw)
        except ValueError:
            raise self._error("Invalid number %r" % raw, start)


def parse_json(text: str, max_depth: int = MAX_DEPTH) -> Any:
    """Разбирает строку JSON и возвращает Python-значение."""
    return JsonParser(text, max_depth=max_depth).parse()


def load_json_file(path, max_depth: int = MAX_DEPTH) -> Any:
    """Читает файл и разбирает его содержимое как JSON."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise JsonParseError(
            "Cannot read file %s: %s" % (file_path, exc.strerror), 1, 1, 0
        )
    try:
        return parse_json(text, max_depth=max_depth)
    except JsonParseError as exc:
        raise JsonParseError(
            "%s: %s" % (file_path.name, exc.message), exc.line, exc.column, exc.position
        )
