"""
Управление фоновым процессом Ollama.

При запуске приложения вызови ensure_running() — она запустит `ollama serve`
используя bundled ollama.exe и указывая на модели в %APPDATA%/SciAnalyzer/models.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

_OLLAMA_URL   = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:3b"
_lock         = threading.Lock()
_launched     = False


def _models_dir() -> Path:
    """Where we store Ollama model files (inside our APPDATA folder)."""
    from core.paths import DATA_ROOT
    return DATA_ROOT / "models"


def _find_exe() -> str | None:
    """Locate ollama.exe: bundled next to our app first, then system fallbacks."""
    # Bundled alongside our frozen executable
    if getattr(sys, "frozen", False):
        candidate = Path(sys.executable).parent / "ollama.exe"
        if candidate.exists():
            return str(candidate)
    else:
        # Dev mode: project root
        candidate = Path(__file__).parent.parent / "ollama.exe"
        if candidate.exists():
            return str(candidate)

    # System-wide installation fallbacks
    exe = shutil.which("ollama")
    if exe:
        return exe
    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if local.exists():
            return str(local)
    return None


def is_running() -> bool:
    try:
        r = requests.get(f"{_OLLAMA_URL}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def ensure_running() -> None:
    """Start Ollama in background if not already running. Non-blocking."""
    threading.Thread(target=_ensure_worker, daemon=True).start()


def _ensure_worker() -> None:
    global _launched
    with _lock:
        if _launched:
            return
        if is_running():
            return

        exe = _find_exe()
        if not exe:
            print("[ollama] ollama.exe не найден", flush=True)
            return

        try:
            env = os.environ.copy()
            env["OLLAMA_MODELS"] = str(_models_dir())

            kwargs: dict = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "env":    env,
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            subprocess.Popen([exe, "serve"], **kwargs)
            _launched = True
            print("[ollama] запущен в фоне", flush=True)
        except Exception as e:
            print(f"[ollama] не удалось запустить: {e}", flush=True)
            return

    for _ in range(30):
        time.sleep(1)
        if is_running():
            print("[ollama] готова к работе", flush=True)
            return
    print("[ollama] не ответила за 30 сек", flush=True)
