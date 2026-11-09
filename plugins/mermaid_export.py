"""Пример плагина: экспорт диаграмм в разметку Mermaid."""

import re

NAME = "mermaid"


def _safe_id(value):
    """Приводит имя к допустимому идентификатору Mermaid."""
    cleaned = re.sub(r"[^0-9A-Za-z_]", "_", value)
    if not cleaned or cleaned[0].isdigit():
        cleaned = "n_" + cleaned
    return cleaned


def _escape_label(value):
    return str(value).replace('"', "#quot;").replace("\n", " ")


def _sequence_mermaid(document):
    messages = document["sequence"]
    participants = []
    for message in messages:
        for name in (message["actor"], message["target"]):
            if name not in participants:
                participants.append(name)
    lines = ["sequenceDiagram"]
    for participant in participants:
        lines.append("    participant %s" % _safe_id(participant))
    for message in messages:
        parameters = ", ".join(message.get("parameters") or [])
        text = message["action"]
        if parameters:
            text = "%s(%s)" % (text, parameters)
        lines.append(
            "    %s->>%s: %s"
            % (_safe_id(message["actor"]), _safe_id(message["target"]), text)
        )
    return "\n".join(lines)


def _activity_mermaid(document):
    steps = document["activity"]
    lines = ["flowchart TD"]
    declared = set()
    for step in steps:
        name = step["step"]
        if name not in declared:
            declared.add(name)
            lines.append('    %s["%s"]' % (_safe_id(name), _escape_label(name)))
    for step in steps:
        name = step["step"]
        if "next" in step:
            targets = step["next"] if isinstance(step["next"], list) else [step["next"]]
            for target in targets:
                if target not in declared:
                    declared.add(target)
                    lines.append('    %s["%s"]' % (_safe_id(target), _escape_label(target)))
                lines.append("    %s --> %s" % (_safe_id(name), _safe_id(target)))
        else:
            condition = step["condition"]
            true_target = step["true"]
            false_target = step["false"]
            for target in (true_target, false_target):
                if target not in declared:
                    declared.add(target)
                    lines.append('    %s["%s"]' % (_safe_id(target), _escape_label(target)))
            lines.append(
                "    %s -->|%s| %s"
                % (_safe_id(name), _escape_label(condition), _safe_id(true_target))
            )
            lines.append(
                "    %s -.->|%s| %s"
                % (
                    _safe_id(name),
                    _escape_label("NOT (%s)" % condition),
                    _safe_id(false_target),
                )
            )
    return "\n".join(lines)


def export_mermaid(document, kind):
    """Генерирует Mermaid-разметку для диаграммы заданного типа."""
    if kind == "sequence":
        return _sequence_mermaid(document)
    if kind == "activity":
        return _activity_mermaid(document)
    raise ValueError("неизвестный тип диаграммы: %r" % kind)


def register(registry):
    registry["exporters"]["mermaid"] = export_mermaid
