"""Парсер логических условий для диаграмм деятельности.

Грамматика (рекурсивный спуск, приоритеты: NOT > сравнения > AND > OR):

    expr       := or_expr
    or_expr    := and_expr (OR and_expr)*
    and_expr   := not_expr (AND not_expr)*
    not_expr   := NOT not_expr | comparison
    comparison := primary ((== | != | < | > | <= | >=) primary)?
    primary    := '(' expr ')' | NUMBER | STRING | IDENT
"""

from __future__ import annotations

from bisect import bisect_right
from typing import Any, Dict, List, Set

_KEYWORDS = {"and": "AND", "or": "OR", "not": "NOT"}
_COMPARISONS = {"==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}
_SINGLE_CHAR_TOKENS = "()<>!="


class ConditionSyntaxError(ValueError):
    """Синтаксическая ошибка условия с позицией."""

    def __init__(self, message: str, line: int, column: int):
        self.message = message
        self.line = line
        self.column = column
        super().__init__("%s at %d:%d" % (message, line, column))


class Node:
    """Узел AST логического условия."""

    precedence = 5

    def to_text(self) -> str:
        return _render(self, 0)

    def variables(self) -> Set[str]:
        return set()

    def evaluate(self, env: Dict[str, Any]) -> Any:
        raise NotImplementedError

    def __str__(self) -> str:  # pragma: no cover - удобство отладки
        return self.to_text()


class Literal(Node):
    def __init__(self, value: Any):
        self.value = value

    def evaluate(self, env: Dict[str, Any]) -> Any:
        return self.value


class Variable(Node):
    precedence = 5

    def __init__(self, name: str):
        self.name = name

    def to_text(self) -> str:
        return self.name

    def variables(self) -> Set[str]:
        return {self.name}

    def evaluate(self, env: Dict[str, Any]) -> Any:
        if self.name not in env:
            raise KeyError("Variable %r is not defined" % self.name)
        return env[self.name]


class Not(Node):
    precedence = 3

    def __init__(self, operand: Node):
        self.operand = operand

    def to_text(self) -> str:
        return _render(self, 0)

    def variables(self) -> Set[str]:
        return self.operand.variables()

    def evaluate(self, env: Dict[str, Any]) -> Any:
        return not self.operand.evaluate(env)


class Binary(Node):
    def __init__(self, op: str, left: Node, right: Node):
        self.op = op
        self.left = left
        self.right = right

    @property
    def precedence(self) -> int:
        return 1 if self.op == "OR" else 2

    def to_text(self) -> str:
        return _render(self, 0)

    def variables(self) -> Set[str]:
        return self.left.variables() | self.right.variables()

    def evaluate(self, env: Dict[str, Any]) -> Any:
        if self.op == "AND":
            return bool(self.left.evaluate(env)) and bool(self.right.evaluate(env))
        return bool(self.left.evaluate(env)) or bool(self.right.evaluate(env))


class Comparison(Node):
    precedence = 4

    def __init__(self, op: str, left: Node, right: Node):
        self.op = op
        self.left = left
        self.right = right

    def to_text(self) -> str:
        return _render(self, 0)

    def variables(self) -> Set[str]:
        return self.left.variables() | self.right.variables()

    def evaluate(self, env: Dict[str, Any]) -> Any:
        left = self.left.evaluate(env)
        right = self.right.evaluate(env)
        if self.op == "==":
            return left == right
        if self.op == "!=":
            return left != right
        if self.op == "<":
            return left < right
        if self.op == ">":
            return left > right
        if self.op == "<=":
            return left <= right
        return left >= right


def _render(node: Node, parent_precedence: int) -> str:
    if isinstance(node, Not):
        inner = _render(node.operand, node.precedence)
        text = "NOT " + inner
    elif isinstance(node, Binary):
        left = _render(node.left, node.precedence)
        right = _render(node.right, node.precedence + 1)
        text = "%s %s %s" % (left, node.op, right)
    elif isinstance(node, Comparison):
        text = "%s %s %s" % (
            _render(node.left, node.precedence),
            node.op,
            _render(node.right, node.precedence),
        )
    elif isinstance(node, Variable):
        text = node.name
    elif isinstance(node, Literal):
        text = repr(node.value) if isinstance(node.value, str) else str(node.value)
    else:  # pragma: no cover
        text = str(node)
    if node.precedence < parent_precedence:
        return "(" + text + ")"
    return text


class _Token:
    __slots__ = ("kind", "value", "position")

    def __init__(self, kind: str, value: str, position: int):
        self.kind = kind
        self.value = value
        self.position = position

    def __repr__(self) -> str:  # pragma: no cover
        return "_Token(%r, %r)" % (self.kind, self.value)


class _Tokenizer:
    def __init__(self, text: str):
        self.text = text
        self.length = len(text)
        self.pos = 0
        self._line_offsets = [0]
        for index, char in enumerate(text):
            if char == "\n":
                self._line_offsets.append(index + 1)

    def _line_column(self, position: int) -> tuple:
        line_index = bisect_right(self._line_offsets, position) - 1
        if line_index < 0:
            line_index = 0
        return line_index + 1, position - self._line_offsets[line_index] + 1

    def error(self, message: str, position: int = None) -> ConditionSyntaxError:
        if position is None:
            position = self.pos
        line, column = self._line_column(min(position, self.length))
        return ConditionSyntaxError(message, line, column)

    def tokens(self) -> List[_Token]:
        result = []
        while self.pos < self.length:
            char = self.text[self.pos]
            if char in " \t\r\n":
                self.pos += 1
                continue
            start = self.pos
            if char.isdigit():
                result.append(self._read_number())
            elif char.isalpha() or char == "_":
                result.append(self._read_identifier())
            elif char in "'\"":
                result.append(self._read_string())
            elif char in _SINGLE_CHAR_TOKENS:
                result.append(self._read_operator())
            else:
                raise self.error("Unexpected character %r" % char)
        result.append(_Token("EOF", "", self.length))
        return result

    def _read_number(self) -> _Token:
        start = self.pos
        while self.pos < self.length and self.text[self.pos].isdigit():
            self.pos += 1
        if (
            self.pos + 1 < self.length
            and self.text[self.pos] == "."
            and self.text[self.pos + 1].isdigit()
        ):
            self.pos += 1
            while self.pos < self.length and self.text[self.pos].isdigit():
                self.pos += 1
        raw = self.text[start:self.pos]
        return _Token("NUMBER", raw, start)

    def _read_identifier(self) -> _Token:
        start = self.pos
        while self.pos < self.length:
            char = self.text[self.pos]
            if char.isalnum() or char in "_.":
                self.pos += 1
            else:
                break
        raw = self.text[start:self.pos]
        keyword = _KEYWORDS.get(raw.lower())
        if keyword is not None:
            return _Token(keyword, raw, start)
        return _Token("IDENT", raw, start)

    def _read_string(self) -> _Token:
        start = self.pos
        quote = self.text[self.pos]
        self.pos += 1
        chars = []
        while self.pos < self.length:
            char = self.text[self.pos]
            if char == quote:
                self.pos += 1
                return _Token("STRING", "".join(chars), start)
            if char == "\\" and self.pos + 1 < self.length:
                escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"'}
                self.pos += 1
                chars.append(escapes.get(self.text[self.pos], self.text[self.pos]))
                self.pos += 1
                continue
            chars.append(char)
            self.pos += 1
        raise self.error("Unterminated string literal", start)

    def _read_operator(self) -> _Token:
        start = self.pos
        if self.text.startswith(("==", "!=", "<=", ">="), self.pos):
            raw = self.text[self.pos:self.pos + 2]
            self.pos += 2
            return _Token("OP", raw, start)
        raw = self.text[self.pos]
        self.pos += 1
        if raw in "()":
            return _Token(raw, raw, start)
        if raw in "<>":
            return _Token("OP", raw, start)
        raise self.error("Unexpected character %r" % raw, start)


class _Parser:
    def __init__(self, tokens: List[_Token], source: str):
        self.tokens = tokens
        self.index = 0
        self.source = source
        self._line_offsets = [0]
        for index, char in enumerate(source):
            if char == "\n":
                self._line_offsets.append(index + 1)

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def advance(self) -> _Token:
        token = self.tokens[self.index]
        if self.index < len(self.tokens) - 1:
            self.index += 1
        return token

    def _error(self, message: str, token: _Token) -> ConditionSyntaxError:
        position = min(token.position, len(self.source))
        line_index = bisect_right(self._line_offsets, position) - 1
        if line_index < 0:
            line_index = 0
        line = line_index + 1
        column = position - self._line_offsets[line_index] + 1
        return ConditionSyntaxError(message, line, column)

    def parse(self) -> Node:
        if self.current.kind == "EOF":
            raise self._error("Empty condition", self.current)
        node = self.parse_or()
        if self.current.kind != "EOF":
            raise self._error(
                "Unexpected token %r" % self.current.value, self.current
            )
        return node

    def parse_or(self) -> Node:
        node = self.parse_and()
        while self.current.kind == "OR":
            self.advance()
            node = Binary("OR", node, self.parse_and())
        return node

    def parse_and(self) -> Node:
        node = self.parse_not()
        while self.current.kind == "AND":
            self.advance()
            node = Binary("AND", node, self.parse_not())
        return node

    def parse_not(self) -> Node:
        if self.current.kind == "NOT":
            self.advance()
            return Not(self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self) -> Node:
        node = self.parse_primary()
        if self.current.kind == "OP":
            op_token = self.advance()
            right = self.parse_primary()
            node = Comparison(op_token.value, node, right)
            if self.current.kind == "OP":
                raise self._error(
                    "Chained comparisons are not supported", self.current
                )
        return node

    def parse_primary(self) -> Node:
        token = self.current
        if token.kind == "(":
            self.advance()
            node = self.parse_or()
            if self.current.kind != ")":
                raise self._error("Expected ')'", self.current)
            self.advance()
            return node
        if token.kind == "IDENT":
            self.advance()
            return Variable(token.value)
        if token.kind == "NUMBER":
            self.advance()
            if "." in token.value:
                return Literal(float(token.value))
            return Literal(int(token.value))
        if token.kind == "STRING":
            self.advance()
            return Literal(token.value)
        if token.kind in ("AND", "OR", "NOT"):
            raise self._error(
                "Expected expression, got keyword %r" % token.value, token
            )
        raise self._error("Expected expression, got %r" % (token.value or "end of input"), token)


def parse_condition(text: str) -> Node:
    """Разбирает логическое условие в AST."""
    tokenizer = _Tokenizer(text)
    tokens = tokenizer.tokens()
    parser = _Parser(tokens, text)
    try:
        return parser.parse()
    except ConditionSyntaxError as exc:
        raise exc


def normalize_condition(text: str) -> str:
    """Возвращает нормализованное текстовое представление условия."""
    return parse_condition(text).to_text()


def negate(node: Node) -> Node:
    """Строит отрицание условия."""
    return Not(node)
