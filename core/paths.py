"""Centralized path resolution: works both in dev mode and as a frozen PyInstaller bundle."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _data_root() -> Path:
    if getattr(sys, "frozen", False):
        p = Path(os.environ.get("APPDATA", str(Path.home()))) / "SciAnalyzer"
    else:
        p = Path(__file__).parent.parent
    p.mkdir(parents=True, exist_ok=True)
    return p


def bundled(relative: str) -> Path:
    """Path to a read-only resource bundled by PyInstaller (icon, etc.)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / relative  # type: ignore[attr-defined]
    return Path(__file__).parent.parent / relative


DATA_ROOT     = _data_root()
DB_PATH       = DATA_ROOT / "scianalyzer.db"
DOWNLOAD_DIR  = DATA_ROOT / "НайденныеСтатьи"
TEMPLATES_DIR = DATA_ROOT / "ШаблоныДокументов"
OUTPUT_DIR    = DATA_ROOT / "СозданныеДокументы"

for _d in (DOWNLOAD_DIR, TEMPLATES_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
