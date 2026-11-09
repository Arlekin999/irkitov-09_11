"""Мини-движок декларативной валидации схем (без сторонних библиотек)."""

from __future__ import annotations

from typing import Any, Dict, List

_TYPE_NAMES = {
    "object": "object",
    "array": "array",
    "str": "string",
    "int": "integer",
    "number": "number",
    "bool": "boolean",
    "null": "null",
    "any": "any",
}


class ValidationError(ValueError):
    """Ошибка валидации с путём до проблемного поля."""

    def __init__(self, issues: List[str]):
        self.issues = list(issues)
        super().__init__("; ".join(self.issues))


def _type_of(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def _matches_type(value: Any, expected: str) -> bool:
    actual = _type_of(value)
    if expected == "any":
        return True
    if expected == "number":
        return actual in ("int", "number")
    if expected == "int":
        return actual == "int"
    return actual == expected


def _join(path: str, key: str) -> str:
    return "%s.%s" % (path, key) if path else key


def _index(path: str, index: int) -> str:
    return "%s[%d]" % (path, index)


def validate(value: Any, schema: Dict[str, Any], path: str = "") -> List[str]:
    """Проверяет значение по схеме и возвращает список сообщений об ошибках."""
    issues: List[str] = []
    _validate(value, schema, path, issues)
    return issues


def _validate(value: Any, schema: Dict[str, Any], path: str, issues: List[str]) -> None:
    expected = schema.get("type", "any")
    expected_types = [expected] if isinstance(expected, str) else list(expected)
    if not any(_matches_type(value, item) for item in expected_types):
        wanted = " or ".join(_TYPE_NAMES.get(item, item) for item in expected_types)
        issues.append(
            "%s: expected %s, got %s" % (path or "<root>", wanted, _TYPE_NAMES.get(_type_of(value)))
        )
        return

    if "choices" in schema and value not in schema["choices"]:
        issues.append(
            "%s: expected one of %r, got %r" % (path or "<root>", schema["choices"], value)
        )

    if isinstance(value, str):
        if "min_length" in schema and len(value) < schema["min_length"]:
            issues.append(
                "%s: expected length >= %d, got %d"
                % (path or "<root>", schema["min_length"], len(value))
            )
        if "max_length" in schema and len(value) > schema["max_length"]:
            issues.append(
                "%s: expected length <= %d, got %d"
                % (path or "<root>", schema["max_length"], len(value))
            )
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if "min" in schema and value < schema["min"]:
            issues.append("%s: expected >= %r, got %r" % (path or "<root>", schema["min"], value))
        if "max" in schema and value > schema["max"]:
            issues.append("%s: expected <= %r, got %r" % (path or "<root>", schema["max"], value))
    elif isinstance(value, list):
        if "min_items" in schema and len(value) < schema["min_items"]:
            issues.append(
                "%s: expected at least %d item(s), got %d"
                % (path or "<root>", schema["min_items"], len(value))
            )
        if "max_items" in schema and len(value) > schema["max_items"]:
            issues.append(
                "%s: expected at most %d item(s), got %d"
                % (path or "<root>", schema["max_items"], len(value))
            )
        items_schema = schema.get("items")
        if items_schema is not None:
            for index, item in enumerate(value):
                _validate(item, items_schema, _index(path, index), issues)
    elif isinstance(value, dict):
        fields = schema.get("fields", {})
        for key, field_schema in fields.items():
            item_path = _join(path, key)
            if key not in value:
                if field_schema.get("required"):
                    issues.append("%s: required field is missing" % item_path)
                continue
            _validate(value[key], field_schema, item_path, issues)
        if schema.get("allow_extra") is False:
            for key in value:
                if key not in fields:
                    issues.append("%s: unexpected field" % _join(path, key))


_SEQUENCE_STEP = {
    "type": "object",
    "allow_extra": True,
    "fields": {
        "actor": {"type": "str", "required": True, "min_length": 1},
        "action": {"type": "str", "required": True, "min_length": 1},
        "target": {"type": "str", "required": True, "min_length": 1},
        "parameters": {
            "type": "array",
            "required": False,
            "min_items": 0,
            "items": {"type": "str", "min_length": 0},
        },
    },
}

SEQUENCE_SCHEMA = {
    "type": "object",
    "allow_extra": False,
    "fields": {
        "sequence": {
            "type": "array",
            "required": True,
            "min_items": 1,
            "items": _SEQUENCE_STEP,
        }
    },
}

_ACTIVITY_STEP = {
    "type": "object",
    "allow_extra": True,
    "fields": {
        "step": {"type": "str", "required": True, "min_length": 1},
        "next": {"type": ["str", "array"], "required": False},
        "condition": {"type": "str", "required": False, "min_length": 1},
        "true": {"type": "str", "required": False, "min_length": 1},
        "false": {"type": "str", "required": False, "min_length": 1},
    },
}

ACTIVITY_SCHEMA = {
    "type": "object",
    "allow_extra": False,
    "fields": {
        "activity": {
            "type": "array",
            "required": True,
            "min_items": 1,
            "items": _ACTIVITY_STEP,
        }
    },
}


def kind_of(document: Any) -> str:
    """Определяет тип диаграммы по корневому ключу."""
    if isinstance(document, dict):
        if "sequence" in document:
            return "sequence"
        if "activity" in document:
            return "activity"
    raise ValidationError(
        ["<root>: expected object with key 'sequence' or 'activity'"]
    )


def _extra_checks(document: Any, kind: str) -> List[str]:
    issues: List[str] = []
    if kind == "activity":
        steps = document["activity"]
        for index, step in enumerate(steps):
            path = _index("activity", index)
            if not isinstance(step, dict):
                continue
            has_next = "next" in step
            has_condition = "condition" in step
            if has_next and has_condition:
                issues.append(
                    "%s: fields 'next' and 'condition' are mutually exclusive" % path
                )
            if has_condition:
                for key in ("true", "false"):
                    if key not in step:
                        issues.append(
                            "%s: condition requires field '%s'" % (path, key)
                        )
            elif not has_next:
                issues.append(
                    "%s: expected 'next' or 'condition' with 'true'/'false'" % path
                )
            next_value = step.get("next")
            if isinstance(next_value, list):
                for item_index, item in enumerate(next_value):
                    if not isinstance(item, str) or not item:
                        issues.append(
                            "%s: expected non-empty string, got %s"
                            % (_index(_join(path, "next"), item_index), _type_of(item))
                        )
    elif kind == "sequence":
        for index, step in enumerate(document["sequence"]):
            if isinstance(step, dict) and "parameters" in step:
                for item_index, item in enumerate(step["parameters"]):
                    path = _join(_index("sequence", index), "parameters")
                    if not isinstance(item, str):
                        issues.append(
                            "%s: expected string, got %s"
                            % (_index(path, item_index), _type_of(item))
                        )
    return issues


def validate_document(document: Any) -> List[str]:
    """Валидирует документ по схеме, выбранной автоматически."""
    try:
        kind = kind_of(document)
    except ValidationError as exc:
        return exc.issues
    schema = SEQUENCE_SCHEMA if kind == "sequence" else ACTIVITY_SCHEMA
    issues = validate(document, schema)
    issues.extend(_extra_checks(document, kind))
    return issues


def validate_or_raise(document: Any) -> str:
    """Валидирует документ и возвращает его тип, либо бросает ValidationError."""
    issues = validate_document(document)
    if issues:
        raise ValidationError(issues)
    return kind_of(document)
