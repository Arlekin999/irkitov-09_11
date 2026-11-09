"""Загрузчик плагинов из каталога plugins/.

Плагин - файл .py, который обязан определять NAME: str и функцию
register(registry: dict) -> None. Ошибки импорта и регистрации не должны
останавливать приложение: они логируются и попадают в отчёт.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


def new_registry() -> Dict[str, Dict[str, Callable]]:
    """Создаёт пустой реестр расширений."""
    return {"exporters": {}, "validators": {}}


class PluginLoader:
    """Изолированная загрузка плагинов с уникальными именами модулей."""

    def __init__(
        self,
        directory,
        registry: Optional[Dict[str, Dict[str, Callable]]] = None,
        logger: Optional[Callable[[str], None]] = None,
    ):
        self.directory = Path(directory)
        self.registry = registry if registry is not None else new_registry()
        self.logger = logger or (lambda message: None)
        self.loaded: List[Tuple[str, Path]] = []
        self.errors: List[str] = []
        self._names: Dict[str, Path] = {}

    def discover(self) -> List[Path]:
        """Возвращает список .py-файлов плагинов (отсортированный)."""
        if not self.directory.is_dir():
            return []
        return sorted(
            path
            for path in self.directory.iterdir()
            if path.is_file() and path.suffix == ".py" and not path.name.startswith("_")
        )

    def _module_name(self, path: Path) -> str:
        digest = hashlib.md5(str(path.resolve()).encode("utf-8")).hexdigest()[:8]
        return "_plugin_%s_%s" % (path.stem, digest)

    def _fail(self, path: Path, message: str) -> None:
        text = "Плагин %s: %s" % (path.name, message)
        self.errors.append(text)
        self.logger("[plugin] " + text)

    def load_file(self, path) -> bool:
        """Загружает один плагин. Возвращает True при успехе."""
        path = Path(path)
        if path.suffix != ".py":
            self._fail(path, "ожидался .py-файл")
            return False
        module_name = self._module_name(path)
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            if spec is None or spec.loader is None:
                self._fail(path, "не удалось создать спецификацию модуля")
                return False
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - изоляция плагинов
            sys.modules.pop(module_name, None)
            self._fail(path, "ошибка импорта: %s" % exc)
            self.logger(traceback.format_exc().rstrip())
            return False

        name = getattr(module, "NAME", None)
        register = getattr(module, "register", None)
        if not isinstance(name, str) or not name:
            self._fail(path, "не задан NAME: str")
            return False
        if not callable(register):
            self._fail(path, "не определена функция register(registry)")
            return False
        if name in self._names:
            self._fail(
                path,
                "конфликт имён: плагин %r уже загружен из %s"
                % (name, self._names[name]),
            )
            return False
        try:
            register(self.registry)
        except Exception as exc:  # noqa: BLE001 - изоляция плагинов
            self._fail(path, "ошибка регистрации: %s" % exc)
            return False
        for key in ("exporters", "validators"):
            if not isinstance(self.registry.get(key), dict):
                self._fail(path, "реестр повреждён: %r должен быть dict" % key)
                return False
        self._names[name] = path
        self.loaded.append((name, path))
        self.logger("[plugin] загружен %s (%s)" % (name, path.name))
        return True

    def load_all(self) -> List[str]:
        """Загружает все найденные плагины и возвращает имена успешных."""
        for path in self.discover():
            self.load_file(path)
        return [name for name, _ in self.loaded]

    def plugin_names(self) -> List[str]:
        return [name for name, _ in self.loaded]


def load_plugins(directory, registry=None, logger=None) -> PluginLoader:
    """Удобная обёртка: создаёт загрузчик и загружает все плагины."""
    loader = PluginLoader(directory, registry=registry, logger=logger)
    loader.load_all()
    return loader


def call_exporter(registry, format_name: str, document: Any, kind: str) -> str:
    """Вызывает экспортёр из реестра по имени формата."""
    exporters = registry.get("exporters", {})
    if format_name not in exporters:
        raise KeyError(
            "Экспортёр %r не найден. Доступны: %s"
            % (format_name, ", ".join(sorted(exporters)) or "нет")
        )
    return exporters[format_name](document, kind)


def run_validators(registry, document: Any) -> List[str]:
    """Запускает все дополнительные валидаторы из реестра."""
    messages: List[str] = []
    for name, validator in registry.get("validators", {}).items():
        try:
            result = validator(document)
        except Exception as exc:  # noqa: BLE001 - изоляция плагинов
            messages.append("validator %s: exception %s" % (name, exc))
            continue
        if result:
            messages.extend(str(item) for item in result)
    return messages
