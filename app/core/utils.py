# -*- coding: utf-8 -*-
"""Shared utilities: safe command execution and program data paths.

All system command calls go through run() — the function never raises an
exception, so the program also works where the commands do not exist
(e.g. GUI preview on Windows).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Program directories (configuration, data, logs, downloaded .run files)
CONFIG_DIR = Path.home() / ".config" / "nvidia-installer-gui"
DATA_DIR = Path.home() / ".local" / "share" / "nvidia-installer-gui"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = Path.home() / ".cache" / "nvidia-installer-gui"


def ensure_dirs() -> None:
    """Creates the program directories if they do not exist."""
    for d in (CONFIG_DIR, DATA_DIR, LOG_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def is_linux() -> bool:
    """Whether the program runs on Linux (system functions available)."""
    return sys.platform.startswith("linux")


def which(cmd: str) -> str | None:
    """Returns the command path or None if it is not installed."""
    return shutil.which(cmd)


def system_env() -> dict[str, str]:
    """Environment for launching system tools from the program.

    The release binary (PyInstaller via pyforge) points LD_LIBRARY_PATH at its
    bundled libraries so the APP loads them — but child system tools must load
    the SYSTEM libraries, or they fail to start (the 2026-07-10 case: "restart
    now" after installation from the binary silently did nothing, because
    systemctl crashed on the bundled libs; setuid pkexec/sudo ignore the
    variable, which is why the installation itself worked). PyInstaller keeps
    the original value in LD_LIBRARY_PATH_ORIG — restore it; in a frozen build
    without the original the variable is dropped. Running from source returns
    the environment unchanged.
    """
    env = dict(os.environ)
    orig = env.get("LD_LIBRARY_PATH_ORIG")
    if orig is not None:
        env["LD_LIBRARY_PATH"] = orig
    elif getattr(sys, "frozen", False):
        env.pop("LD_LIBRARY_PATH", None)
    return env


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Runs a command and returns (code, stdout, stderr).

    Never raises an exception — errors are converted into a non-zero exit
    code, so the caller can always safely check the result.
    """
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env=system_env())
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"Nie znaleziono polecenia: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"Przekroczono limit czasu: {' '.join(cmd)}"
    except Exception as e:  # pragma: no cover — last line of defense
        return 1, "", str(e)


def read_file(path: str) -> str:
    """Reads a text file; returns an empty string if the file does not exist."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
