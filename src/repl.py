"""Интерактивная оболочка (REPL) для работы с диаграммами."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from activity_diagram import ActivityDiagram
from condition_parser import ConditionSyntaxError
from graph_analysis import AnalysisResult, analyze_steps
from json_parser import JsonParseError
from markdown_writer import activity_markdown, sequence_markdown
from plugin_loader import (
    PluginLoader,
    call_exporter,
    load_plugins,
    new_registry,
    run_validators,
)
from schema_validator import ValidationError, kind_of, validate_document
from sequence_diagram import SequenceDiagram

HELP_TEXT = """Доступные команды:
  load <файл>...          загрузить и разобрать JSON-файлы
  validate                проверить загруженные документы по схеме
  render sequence         вывести диаграмму последовательности
  render activity         вывести диаграмму деятельности
  analyze                 выполнить анализ графа деятельности
  export <формат> [тип]   экспортировать в формат плагина (например, mermaid)
  report                  сохранить Markdown-отчёты
  plugins                 список загруженных плагинов и экспортёров
  clear                   очистить загруженные документы
  help                    эта справка
  quit                    выход
"""


class ReplError(Exception):
    pass


class LoadedDocument:
    """Документ, загруженный в REPL."""

    def __init__(self, path: Path, data: Any, kind: str):
        self.path = path
        self.data = data
        self.kind = kind


def tokenize(line: str) -> List[str]:
    """Собственный токенизатор команд с поддержкой кавычек."""
    tokens: List[str] = []
    buffer: List[str] = []
    quote: Optional[str] = None
    has_token = False
    index = 0
    length = len(line)
    while index < length:
        char = line[index]
        if quote is not None:
            if char == "\\" and index + 1 < length:
                next_char = line[index + 1]
                mapping = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}
                buffer.append(mapping.get(next_char, next_char))
                index += 2
                continue
            if char == quote:
                quote = None
                index += 1
                continue
            buffer.append(char)
            index += 1
            continue
        if char in " \t\r\n":
            if has_token:
                tokens.append("".join(buffer))
                buffer = []
                has_token = False
            index += 1
            continue
        if char in "\"'":
            quote = char
            has_token = True
            index += 1
            continue
        buffer.append(char)
        has_token = True
        index += 1
    if quote is not None:
        raise ReplError("Незакрытая кавычка в команде")
    if has_token:
        tokens.append("".join(buffer))
    return tokens


class Repl:
    """Интерактивная оболочка с историей команд в history.txt."""

    def __init__(
        self,
        plugin_dir=None,
        output_dir=None,
        registry: Optional[Dict[str, Dict[str, Callable]]] = None,
        history_path=None,
        out: Optional[Callable[[str], None]] = print,
    ):
        self.registry = registry if registry is not None else new_registry()
        self.plugin_dir = Path(plugin_dir) if plugin_dir else Path("plugins")
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.history_path = (
            Path(history_path) if history_path else self.output_dir / "history.txt"
        )
        self.out = out or (lambda message: None)
        self.loader: Optional[PluginLoader] = None
        self.documents: List[LoadedDocument] = []
        self.running = True

    def load_plugins(self) -> None:
        self.loader = load_plugins(
            self.plugin_dir, registry=self.registry, logger=self.out
        )

    def _history(self, line: str) -> None:
        try:
            with self.history_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError as exc:  # pragma: no cover - сбой записи истории
            self.out("[history] не удалось сохранить команду: %s" % exc)

    def run(self) -> None:
        if self.loader is None:
            self.load_plugins()
        self.out("REPL диаграмм. Введите help для списка команд.")
        while self.running:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                self.out("")
                break
            line = line.strip()
            if not line:
                continue
            try:
                self.execute(line)
            except ReplError as exc:
                self.out("Ошибка: %s" % exc)
            except (JsonParseError, ValidationError, ConditionSyntaxError) as exc:
                self.out("Ошибка: %s" % exc)
            except Exception as exc:  # noqa: BLE001 - REPL не должен падать
                self.out("Непредвиденная ошибка: %s" % exc)

    def execute(self, line: str) -> None:
        """Выполняет одну команду REPL."""
        tokens = tokenize(line)
        if not tokens:
            return
        self._history(line)
        command = tokens[0].lower()
        arguments = tokens[1:]
        handler = getattr(self, "_cmd_%s" % command, None)
        if command in ("quit", "exit"):
            self.running = False
            self.out("Выход.")
            return
        if handler is None:
            raise ReplError("неизвестная команда %r (см. help)" % tokens[0])
        handler(arguments)

    def _cmd_help(self, arguments: List[str]) -> None:
        self.out(HELP_TEXT.rstrip())

    def _cmd_load(self, arguments: List[str]) -> None:
        if not arguments:
            raise ReplError("использование: load <файл> [<файл>...]")
        for raw_path in arguments:
            path = Path(raw_path)
            data = _read_document(path)
            kind = kind_of(data)
            self.documents.append(LoadedDocument(path, data, kind))
            self.out("Загружен %s (%s)" % (path.name, kind))

    def _cmd_validate(self, arguments: List[str]) -> None:
        documents = self._require_documents()
        has_errors = False
        for document in documents:
            issues = validate_document(document.data)
            issues.extend(run_validators(self.registry, document.data))
            if issues:
                has_errors = True
                self.out("%s: найдено ошибок - %d" % (document.path.name, len(issues)))
                for issue in issues:
                    self.out("  " + issue)
            else:
                self.out("%s: документ корректен" % document.path.name)
        if has_errors:
            self.out("Валидация завершена с ошибками")

    def _cmd_render(self, arguments: List[str]) -> None:
        if len(arguments) != 1 or arguments[0] not in ("sequence", "activity"):
            raise ReplError("использование: render sequence | render activity")
        kind = arguments[0]
        documents = [doc for doc in self._require_documents() if doc.kind == kind]
        if not documents:
            raise ReplError("нет загруженных документов типа %r" % kind)
        for document in documents:
            if kind == "sequence":
                self.out(SequenceDiagram.from_document(document.data).render())
            else:
                self.out(ActivityDiagram.from_document(document.data).render())
            self.out("")

    def _cmd_analyze(self, arguments: List[str]) -> None:
        documents = [doc for doc in self._require_documents() if doc.kind == "activity"]
        if not documents:
            raise ReplError("нет загруженных документов диаграммы деятельности")
        for document in documents:
            analysis = analyze_steps(document.data["activity"])
            self.out("Анализ %s:" % document.path.name)
            for line in analysis.summary_lines():
                self.out(line)
            self.out("")

    def _cmd_export(self, arguments: List[str]) -> None:
        if not arguments or len(arguments) > 2:
            raise ReplError("использование: export <формат> [sequence|activity]")
        format_name = arguments[0]
        kind_filter = arguments[1] if len(arguments) > 1 else None
        if kind_filter not in (None, "sequence", "activity"):
            raise ReplError("тип должен быть sequence или activity")
        documents = [
            doc
            for doc in self._require_documents()
            if kind_filter is None or doc.kind == kind_filter
        ]
        if not documents:
            raise ReplError("нет подходящих загруженных документов")
        for document in documents:
            text = call_exporter(self.registry, format_name, document.data, document.kind)
            self.out(text)
            extension = _extension_for(format_name)
            target = self.output_dir / ("%s-diagram%s" % (document.kind, extension))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text + "\n", encoding="utf-8")
            self.out("Сохранено: %s" % target)
            self.out("")

    def _cmd_report(self, arguments: List[str]) -> None:
        if len(arguments) > 1 or (arguments and arguments[0] not in ("sequence", "activity")):
            raise ReplError("использование: report [sequence|activity]")
        kind_filter = arguments[0] if arguments else None
        documents = [
            doc
            for doc in self._require_documents()
            if kind_filter is None or doc.kind == kind_filter
        ]
        if not documents:
            raise ReplError("нет подходящих загруженных документов")
        self._write_reports(documents)

    def _cmd_plugins(self, arguments: List[str]) -> None:
        if self.loader is None:
            self.out("Плагины не загружены")
            return
        names = self.loader.plugin_names()
        self.out("Загруженные плагины: %s" % (", ".join(names) if names else "нет"))
        for key in ("exporters", "validators"):
            values = sorted(self.registry.get(key, {}))
            self.out("%s: %s" % (key, ", ".join(values) if values else "нет"))
        if self.loader.errors:
            self.out("Ошибки загрузки плагинов:")
            for error in self.loader.errors:
                self.out("  " + error)

    def _cmd_clear(self, arguments: List[str]) -> None:
        self.documents = []
        self.out("Список загруженных документов очищен")

    def _require_documents(self) -> List[LoadedDocument]:
        if not self.documents:
            raise ReplError("нет загруженных документов (используйте load <файл>)")
        return self.documents

    def _write_reports(self, documents: List[LoadedDocument]) -> None:
        written = []
        for document in documents:
            if document.kind == "sequence":
                text = sequence_markdown(document.data)
            else:
                text = activity_markdown(document.data)
            name = "%s-diagram.md" % document.kind
            target = self.output_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            written.append(str(target))
        for path in written:
            self.out("Сохранено: %s" % path)


def _read_document(path: Path) -> Any:
    from json_parser import load_json_file

    return load_json_file(path)


def _extension_for(format_name: str) -> str:
    return {
        "mermaid": ".mmd",
        "plantuml": ".puml",
    }.get(format_name.lower(), ".txt")
