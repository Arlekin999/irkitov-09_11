#!/usr/bin/env python3
"""Единая точка входа: python run.py --repl | --file activity.json --render activity."""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from main import main  # noqa: E402  (путь добавляется выше)


if __name__ == "__main__":
    raise SystemExit(main())
