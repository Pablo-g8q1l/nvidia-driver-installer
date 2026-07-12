# -*- coding: utf-8 -*-
"""User settings (language, theme) stored in a JSON file."""
from __future__ import annotations

import json
import os

from app.core.utils import CONFIG_DIR

CONFIG_FILE = CONFIG_DIR / "config.json"


def _system_language() -> str:
    """Interface language from system settings: Polish → "pl", other → "en".

    Locale variables are checked in order of precedence (LC_ALL overrides
    LC_MESSAGES, which overrides LANG). A value like "pl_PL.UTF-8" → Polish;
    everything else (en_US, de_DE, "C"…) → English. Used only as the DEFAULT
    value — the language chosen in Settings is stored in config.json and
    always takes precedence.
    """
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var)
        if val:
            return "pl" if val.lower().startswith("pl") else "en"
    # No locale variables (e.g. Windows in preview mode) — Python locale
    try:
        import locale
        loc = (locale.getlocale()[0] or "").lower()
        return "pl" if loc.startswith(("pl", "polish")) else "en"
    except Exception:
        return "en"


# Default values — language detected from the system (Polish locale → Polish,
# other → English), dark theme, boot report disabled (opt-in: the diagnostic
# service stays on the system, so it requires consent in Settings), Timeshift
# snapshot before installation disabled by default (the checkbox only appears
# when Timeshift is installed; the user opts in per installation)
DEFAULTS = {"language": _system_language(), "theme": "dark", "boot_report": False,
            "snapshot": False}


def load_config() -> dict:
    """Loads settings; returns defaults if the file is missing or corrupted."""
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg.update(data)
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg: dict) -> None:
    """Saves settings to disk (write errors are ignored — they are not critical)."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass
