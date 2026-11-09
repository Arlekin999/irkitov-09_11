"""Построение текстового представления диаграммы последовательности."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from schema_validator import ValidationError, validate_or_raise


class SequenceDiagram:
    """Диаграмма последовательности, построенная по списку сообщений."""

    def __init__(self, messages: List[Dict[str, Any]]):
        self.messages = list(messages)

    @classmethod
    def from_document(cls, document: Any) -> "SequenceDiagram":
        kind = validate_or_raise(document)
        if kind != "sequence":
            raise ValidationError(["<root>: expected sequence diagram, got %s" % kind])
        return cls(document["sequence"])

    def participants(self) -> List[str]:
        seen = []
        for message in self.messages:
            for name in (message["actor"], message["target"]):
                if name not in seen:
                    seen.append(name)
        return seen

    @staticmethod
    def _format_parameters(parameters: Iterable[str]) -> str:
        return ", ".join(parameters)

    def message_text(self, message: Dict[str, Any]) -> str:
        parameters = self._format_parameters(message.get("parameters") or [])
        return "%s(%s)" % (message["action"], parameters)

    def lines(self) -> List[str]:
        result = ["Sequence Diagram:"]
        for message in self.messages:
            result.append(
                "%s -> %s: %s"
                % (message["actor"], message["target"], self.message_text(message))
            )
        return result

    def render(self) -> str:
        return "\n".join(self.lines())
