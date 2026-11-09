"""Построение текстового представления диаграммы деятельности."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from condition_parser import Node, negate, parse_condition
from schema_validator import ValidationError, validate_or_raise


class Transition:
    """Переход между двумя шагами деятельности."""

    __slots__ = ("source", "target", "label")

    def __init__(self, source: str, target: str, label: str = ""):
        self.source = source
        self.target = target
        self.label = label

    def as_tuple(self) -> Tuple[str, str, str]:
        return self.source, self.target, self.label


class ActivityDiagram:
    """Диаграмма деятельности: шаги, условия и переходы."""

    def __init__(self, steps: List[Dict[str, Any]]):
        self.steps = list(steps)
        self._conditions: Dict[int, Node] = {}
        self.transitions = list(self._build_transitions())

    @classmethod
    def from_document(cls, document: Any) -> "ActivityDiagram":
        kind = validate_or_raise(document)
        if kind != "activity":
            raise ValidationError(["<root>: expected activity diagram, got %s" % kind])
        return cls(document["activity"])

    def _condition_node(self, index: int, text: str) -> Node:
        node = parse_condition(text)
        self._conditions[index] = node
        return node

    def _next_targets(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]

    def _build_transitions(self) -> List[Transition]:
        result: List[Transition] = []
        for index, step in enumerate(self.steps):
            name = step["step"]
            if "next" in step:
                for target in self._next_targets(step["next"]):
                    result.append(Transition(name, target))
                continue
            condition_text = step["condition"]
            node = self._condition_node(index, condition_text)
            result.append(Transition(name, step["true"], node.to_text()))
            negated = negate(node).to_text()
            result.append(Transition(name, step["false"], negated))
        return result

    def step_names(self) -> List[str]:
        return [step["step"] for step in self.steps]

    def lines(self) -> List[str]:
        result = ["Activity Diagram:"]
        for transition in self.transitions:
            if transition.label:
                result.append(
                    "%s -> %s (if %s)"
                    % (transition.source, transition.target, transition.label)
                )
            else:
                result.append("%s -> %s" % (transition.source, transition.target))
        return result

    def render(self) -> str:
        return "\n".join(self.lines())
