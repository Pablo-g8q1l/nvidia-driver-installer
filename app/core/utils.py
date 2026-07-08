# -*- coding: utf-8 -*-
"""Narzędzia wspólne: bezpieczne uruchamianie poleceń i ścieżki danych programu.

Wszystkie wywołania poleceń systemowych przechodzą przez run() — funkcja nigdy
nie rzuca wyjątku, dzięki czemu program działa też tam, gdzie polecenia nie
istnieją (np. podgląd GUI na Windows).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Katalogi programu (konfiguracja, dane, logi, pobrane pliki .run)
CONFIG_DIR = Path.home() / ".config" / "nvidia-installer-gui"
DATA_DIR = Path.home() / ".local" / "share" / "nvidia-installer-gui"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = Path.home() / ".cache" / "nvidia-installer-gui"


def ensure_dirs() -> None:
    """Tworzy katalogi programu, jeśli nie istnieją."""
    for d in (CONFIG_DIR, DATA_DIR, LOG_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def is_linux() -> bool:
    """Czy program działa na Linuksie (funkcje systemowe dostępne)."""
    return sys.platform.startswith("linux")


def which(cmd: str) -> str | None:
    """Zwraca ścieżkę polecenia lub None, gdy nie jest zainstalowane."""
    return shutil.which(cmd)


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Uruchamia polecenie i zwraca (kod, stdout, stderr).

    Nigdy nie rzuca wyjątku — błędy zamieniane są na niezerowy kod wyjścia,
    dzięki czemu wywołujący zawsze może bezpiecznie sprawdzić wynik.
    """
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"Nie znaleziono polecenia: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"Przekroczono limit czasu: {' '.join(cmd)}"
    except Exception as e:  # pragma: no cover — ostatnia linia obrony
        return 1, "", str(e)


def read_file(path: str) -> str:
    """Czyta plik tekstowy; zwraca pusty tekst, gdy plik nie istnieje."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
