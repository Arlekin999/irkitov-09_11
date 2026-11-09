"""Основная логика приложения и разбор аргументов командной строки."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from activity_diagram import ActivityDiagram
from graph_analysis import AnalysisResult, analyze_steps
from json_parser import JsonParseError, load_json_file
from markdown_writer import activity_markdown, sequence_markdown
from plugin_loader import call_exporter, load_plugins, new_registry
from schema_validator import ValidationError, kind_of, validate_document
from sequence_diagram import SequenceDiagram

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLUGIN_DIR = ROOT / "plugins"

USAGE = """Использование:
  python run.py --repl
  python run.py --file <путь> [--render sequence|activity] [--report]
  python run.py --file <путь> --analyze
  python run.py --file <путь> --export mermaid

Параметры:
  --repl                 интерактивный режим (REPL)
  --file <путь>          входной JSON-файл (можно указывать несколько раз)
  --render <тип>         вывести диаграмму (sequence или activity)
  --analyze              выполнить анализ графа деятельности
  --report               сохранить Markdown-отчёты
  --export <формат>      экспорт через плагин (например, mermaid)
  --output <каталог>     каталог для отчётов (по умолчанию текущий)
  --plugins-dir <путь>   каталог плагинов
  --no-plugins           не загружать плагины
  -h, --help             показать справку
"""


class Document:
    """Загруженный и провалидированный документ."""

    def __init__(self, path: Path, data: Any, kind: str):
        self.path = path
        self.data = data
        self.kind = kind


def load_document(path) -> Document:
    """Загружает, разбирает и валидирует документ."""
    file_path = Path(path)
    data = load_json_file(file_path)
    issues = validate_document(data)
    if issues:
        raise ValidationError(issues)
    return Document(file_path, data, kind_of(data))


def render_sequence(document: Document) -> str:
    return SequenceDiagram.from_document(document.data).render()


def render_activity(document: Document) -> str:
    return ActivityDiagram.from_document(document.data).render()


def analyze_document(document: Document) -> AnalysisResult:
    if document.kind != "activity":
        raise ValueError("анализ графа доступен только для диаграммы деятельности")
    return analyze_steps(document.data["activity"])


def report_markdown(document: Document) -> str:
    if document.kind == "sequence":
        return sequence_markdown(document.data)
    return activity_markdown(document.data)


def parse_arguments(argv: List[str]) -> Dict[str, Any]:
    """Ручной разбор аргументов командной строки (без argparse)."""
    options: Dict[str, Any] = {
        "repl": False,
        "files": [],
        "render": None,
        "analyze": False,
        "report": False,
        "export": None,
        "output": None,
        "plugins_dir": None,
        "no_plugins": False,
        "help": False,
    }
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in ("-h", "--help"):
            options["help"] = True
        elif argument == "--repl":
            options["repl"] = True
        elif argument in ("--file", "--render", "--export", "--output", "--plugins-dir"):
            if index + 1 >= len(argv):
                raise SystemExit("Ошибка: для %s требуется значение" % argument)
            value = argv[index + 1]
            index += 1
            if argument == "--file":
                options["files"].append(value)
            elif argument == "--render":
                if value not in ("sequence", "activity"):
                    raise SystemExit("Ошибка: --render ожидает sequence или activity")
                options["render"] = value
            elif argument == "--export":
                options["export"] = value
            elif argument == "--output":
                options["output"] = value
            else:
                options["plugins_dir"] = value
        elif argument == "--analyze":
            options["analyze"] = True
        elif argument == "--report":
            options["report"] = True
        elif argument == "--no-plugins":
            options["no_plugins"] = True
        else:
            raise SystemExit("Ошибка: неизвестный аргумент %r\n\n%s" % (argument, USAGE))
        index += 1
    return options


def _extension_for(format_name: str) -> str:
    return {"mermaid": ".mmd", "plantuml": ".puml"}.get(format_name.lower(), ".txt")


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    options = parse_arguments(argv)
    output_dir = Path(options["output"]) if options["output"] else Path.cwd()
    plugin_dir = Path(options["plugins_dir"]) if options["plugins_dir"] else DEFAULT_PLUGIN_DIR

    if options["help"] or (not options["repl"] and not options["files"]):
        print(USAGE.rstrip())
        return 0

    if options["repl"]:
        from repl import Repl

        repl = Repl(plugin_dir=plugin_dir, output_dir=output_dir)
        if not options["no_plugins"]:
            repl.load_plugins()
        repl.run()
        return 0

    registry = new_registry()
    loader = None
    if not options["no_plugins"]:
        loader = load_plugins(plugin_dir, registry=registry, logger=print)
        for error in loader.errors:
            print("[plugin] " + error, file=sys.stderr)

    exit_code = 0
    for raw_path in options["files"]:
        try:
            document = load_document(raw_path)
        except (JsonParseError, ValidationError) as exc:
            print("Ошибка в %s: %s" % (raw_path, exc), file=sys.stderr)
            exit_code = 1
            continue
        try:
            _process_document(document, options, registry, output_dir)
        except Exception as exc:  # noqa: BLE001 - CLI сообщает об ошибке
            print("Ошибка обработки %s: %s" % (raw_path, exc), file=sys.stderr)
            exit_code = 1
    return exit_code


def _process_document(
    document: Document,
    options: Dict[str, Any],
    registry: Dict[str, Any],
    output_dir: Path,
) -> None:
    rendered = False
    if options["render"] is None or options["render"] == document.kind:
        if document.kind == "sequence":
            print(render_sequence(document))
        else:
            print(render_activity(document))
        rendered = True
        print("")

    if options["analyze"] and document.kind == "activity":
        analysis = analyze_document(document)
        print("Анализ %s:" % document.path.name)
        for line in analysis.summary_lines():
            print(line)
        print("")

    if options["report"] or rendered:
        text = report_markdown(document)
        target = output_dir / ("%s-diagram.md" % document.kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print("Отчёт сохранён: %s" % target)
        print("")

    if options["export"]:
        text = call_exporter(registry, options["export"], document.data, document.kind)
        print(text)
        target = output_dir / (
            "%s-diagram%s" % (document.kind, _extension_for(options["export"]))
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
        print("Экспорт сохранён: %s" % target)
        print("")


if __name__ == "__main__":
    raise SystemExit(main())
