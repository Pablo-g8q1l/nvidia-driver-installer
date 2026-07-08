# -*- coding: utf-8 -*-
"""Ustawienia użytkownika (język, motyw) zapisywane w pliku JSON."""
from __future__ import annotations

import json
import os

from app.core.utils import CONFIG_DIR

CONFIG_FILE = CONFIG_DIR / "config.json"


def _system_language() -> str:
    """Język interfejsu z ustawień systemu: polski → "pl", inny → "en".

    Sprawdzane są zmienne locale w kolejności obowiązywania (LC_ALL nadpisuje
    LC_MESSAGES, ta — LANG). Wartość jak "pl_PL.UTF-8" → polski; wszystko
    inne (en_US, de_DE, "C"…) → angielski. Działa tylko jako wartość
    DOMYŚLNA — język wybrany w Ustawieniach jest zapisany w config.json
    i zawsze ma pierwszeństwo.
    """
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var)
        if val:
            return "pl" if val.lower().startswith("pl") else "en"
    # Brak zmiennych locale (np. Windows w trybie podglądu) — locale Pythona
    try:
        import locale
        loc = (locale.getlocale()[0] or "").lower()
        return "pl" if loc.startswith(("pl", "polish")) else "en"
    except Exception:
        return "en"


# Wartości domyślne — język wykrywany z systemu (polskie locale → polski,
# inne → angielski), ciemny motyw, raport rozruchu wyłączony (opt-in:
# usługa diagnostyczna zostaje na systemie, więc wymaga zgody w Ustawieniach)
DEFAULTS = {"language": _system_language(), "theme": "dark", "boot_report": False}


def load_config() -> dict:
    """Wczytuje ustawienia; przy braku lub uszkodzeniu pliku zwraca domyślne."""
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg.update(data)
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg: dict) -> None:
    """Zapisuje ustawienia na dysk (błędy zapisu ignorowane — nie są krytyczne)."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass
