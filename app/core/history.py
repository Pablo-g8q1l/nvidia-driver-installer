# -*- coding: utf-8 -*-
"""Installation history: entries in a JSON file + full logs in separate files."""
from __future__ import annotations

import json
from datetime import datetime

from app.i18n import tr

from .utils import DATA_DIR, LOG_DIR, ensure_dirs

HISTORY_FILE = DATA_DIR / "history.json"

# Human-readable installation method names for display
METHOD_NAMES = {
    "nvk": "NVK / Mesa (open source)",
    "repo": "Repozytorium dystrybucji",
    "run": "Plik .run NVIDIA",
}


def load_history() -> list[dict]:
    """Loads history entries (newest at the beginning of the list)."""
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, ValueError):
        pass
    return []


def _save_history(entries: list[dict]) -> None:
    ensure_dirs()
    HISTORY_FILE.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def add_entry(metoda: str, wersja: str, dystrybucja: str, status: str,
              log_text: str) -> dict:
    """Adds a history entry and saves the full log to a separate file."""
    ensure_dirs()
    ts = datetime.now()
    log_name = f"instalacja-{ts.strftime('%Y%m%d-%H%M%S')}.log"
    log_path = LOG_DIR / log_name
    try:
        log_path.write_text(log_text, encoding="utf-8")
    except OSError:
        log_name = ""  # log not saved, but the history entry is created anyway

    entry = {
        "data": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "metoda": METHOD_NAMES.get(metoda, metoda),
        "wersja": wersja,
        "dystrybucja": dystrybucja,
        "status": status,
        "log": log_name,
    }
    entries = load_history()
    entries.insert(0, entry)  # newest on top
    _save_history(entries)
    return entry


def read_log(entry: dict) -> str:
    """Returns the full log for a history entry (or a not-found message)."""
    name = entry.get("log", "")
    if not name:
        return tr("Brak zapisanego logu dla tego wpisu.")
    try:
        return (LOG_DIR / name).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return tr("Nie można odczytać pliku logu:") + f" {LOG_DIR / name}"


def clear_history() -> None:
    """Removes all history entries along with their log files."""
    for entry in load_history():
        name = entry.get("log", "")
        if name:
            (LOG_DIR / name).unlink(missing_ok=True)
    _save_history([])
