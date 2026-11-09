#!/usr/bin/env python3
"""Генератор большого входного файла и замер производительности.

Формирует диаграмму деятельности из 10 000 шагов и 30 000 переходов,
замеряет разбор JSON, анализ графа и рендеринг (time.perf_counter).
"""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from activity_diagram import ActivityDiagram  # noqa: E402
from graph_analysis import analyze_steps  # noqa: E402
from json_parser import parse_json  # noqa: E402
from markdown_writer import activity_markdown  # noqa: E402

STEPS = 10000
TRANSITIONS = 30000
LIMIT_SECONDS = 2.0


def build_adjacency(steps=STEPS, transitions=TRANSITIONS):
    """Строит список смежности ациклического графа с заданным числом рёбер."""
    adjacency = [set() for _ in range(steps)]

    def add(source, target):
        if source != target and target < steps:
            adjacency[source].add(target)

    for index in range(steps - 1):
        add(index, index + 1)
    current = sum(len(targets) for targets in adjacency)
    shift = 2
    while current < transitions:
        added = False
        for index in range(steps):
            if current >= transitions:
                break
            if index + shift < steps:
                before = len(adjacency[index])
                add(index, index + shift)
                if len(adjacency[index]) != before:
                    current += 1
                    added = True
        if not added and shift >= steps:
            break
        shift += 1
    return adjacency


def step_name(index):
    return "End%d" % index if index == STEPS - 1 else "Step%05d" % index


def build_json(steps=STEPS, transitions=TRANSITIONS):
    adjacency = build_adjacency(steps, transitions)
    parts = []
    for index in range(steps):
        targets = sorted(adjacency[index])
        if targets:
            rendered = ", ".join('"%s"' % step_name(target) for target in targets)
            parts.append(
                '    {"step": "%s", "next": [%s]}' % (step_name(index), rendered)
            )
        else:
            parts.append('    {"step": "%s", "next": []}' % step_name(index))
    return '{\n  "activity": [\n' + ",\n".join(parts) + "\n  ]\n}\n"


def count_edges(document):
    total = 0
    for step in document["activity"]:
        value = step.get("next")
        if isinstance(value, list):
            total += len(value)
        elif value is not None:
            total += 1
    return total


def run(steps=STEPS, transitions=TRANSITIONS, output=None):
    output = Path(output) if output else BASE_DIR / "samples" / "benchmark_activity.json"
    text = build_json(steps, transitions)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    size_mb = len(text.encode("utf-8")) / (1024 * 1024)

    start = time.perf_counter()
    document = parse_json(text)
    parse_time = time.perf_counter() - start

    start = time.perf_counter()
    analysis = analyze_steps(document["activity"])
    analysis_time = time.perf_counter() - start

    start = time.perf_counter()
    diagram = ActivityDiagram.from_document(document)
    render_time = time.perf_counter() - start

    start = time.perf_counter()
    report = activity_markdown(document, analysis)
    report_time = time.perf_counter() - start

    total = parse_time + analysis_time + render_time + report_time
    edges = count_edges(document)

    print("Файл: %s (%.2f МБ)" % (output, size_mb))
    print("Шагов: %d, переходов: %d" % (len(document["activity"]), edges))
    print("Разбор JSON:        %.4f с" % parse_time)
    print("Анализ графа:       %.4f с" % analysis_time)
    print("Рендеринг:          %.4f с" % render_time)
    print("Markdown-отчёт:     %.4f с" % report_time)
    print("Итого:              %.4f с (лимит %.1f с)" % (total, LIMIT_SECONDS))
    print("Циклы: %d, недостижимые: %d, тупиковые: %d"
          % (len(analysis.cycles), len(analysis.unreachable), len(analysis.dead_ends)))
    print("Строк диаграммы: %d, строк отчёта: %d"
          % (len(diagram.lines()), report.count("\n")))
    if total >= LIMIT_SECONDS:
        print("ТРЕБОВАНИЕ НЕ ВЫПОЛНЕНО: время превышает %.1f с" % LIMIT_SECONDS)
        return 1
    print("Требование по производительности выполнено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
