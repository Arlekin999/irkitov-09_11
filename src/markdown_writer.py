"""Генерация Markdown-отчётов по диаграммам."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List

from activity_diagram import ActivityDiagram
from graph_analysis import AnalysisResult
from sequence_diagram import SequenceDiagram


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def sequence_markdown(document: Any) -> str:
    """Формирует Markdown-отчёт по диаграмме последовательности."""
    diagram = SequenceDiagram.from_document(document)
    lines: List[str] = []
    lines.append("# Диаграмма последовательности")
    lines.append("")
    lines.append("## Участники")
    lines.append("")
    for participant in diagram.participants():
        lines.append("- %s" % participant)
    lines.append("")
    lines.append("## Сообщения")
    lines.append("")
    lines.append("| № | Отправитель | Получатель | Действие | Параметры |")
    lines.append("|---|-------------|------------|----------|-----------|")
    for index, message in enumerate(diagram.messages, start=1):
        parameters = ", ".join(message.get("parameters") or [])
        lines.append(
            "| %d | %s | %s | %s | %s |"
            % (
                index,
                _escape(message["actor"]),
                _escape(message["target"]),
                _escape(message["action"]),
                _escape(parameters),
            )
        )
    lines.append("")
    lines.append("## Текстовое представление")
    lines.append("")
    lines.append("```text")
    lines.append(diagram.render())
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def activity_markdown(document: Any, analysis: AnalysisResult = None) -> str:
    """Формирует Markdown-отчёт по диаграмме деятельности с блоком «Анализ»."""
    diagram = ActivityDiagram.from_document(document)
    if analysis is None:
        from graph_analysis import analyze_steps

        analysis = analyze_steps(document["activity"])
    lines: List[str] = []
    lines.append("# Диаграмма деятельности")
    lines.append("")
    lines.append("## Переходы")
    lines.append("")
    lines.append("| Из | В | Условие |")
    lines.append("|----|---|---------|")
    for transition in diagram.transitions:
        lines.append(
            "| %s | %s | %s |"
            % (
                _escape(transition.source),
                _escape(transition.target),
                _escape(transition.label) if transition.label else "-",
            )
        )
    lines.append("")
    lines.append("## Текстовое представление")
    lines.append("")
    lines.append("```text")
    lines.append(diagram.render())
    lines.append("```")
    lines.append("")
    lines.append("## Анализ")
    lines.append("")
    warnings: List[str] = []
    for line in analysis.summary_lines():
        if line.startswith("  - "):
            warnings.append(line[4:])
        elif line == "Предупреждения:":
            continue
        else:
            lines.append("- %s" % line)
    if warnings:
        lines.append("")
        lines.append("### Предупреждения")
        lines.append("")
        for warning in warnings:
            lines.append("- %s" % warning)
    lines.append("")
    return "\n".join(lines)


def write_text(path, text: str) -> Path:
    """Записывает текст в файл (UTF-8) и возвращает путь."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def write_sequence_report(path, document: Any) -> Path:
    return write_text(path, sequence_markdown(document))


def write_activity_report(path, document: Any, analysis: AnalysisResult = None) -> Path:
    return write_text(path, activity_markdown(document, analysis))
