# -*- coding: utf-8 -*-
"""Real-time GPU monitor — polls nvidia-smi every 2 seconds."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.i18n import tr

from .utils import run

# Fields fetched from nvidia-smi (order must match the parsing)
_QUERY_FIELDS = (
    "name,driver_version,temperature.gpu,utilization.gpu,"
    "memory.used,memory.total,power.draw,power.limit,fan.speed"
)


def _to_float(value: str) -> float | None:
    """Converts an nvidia-smi field to a number; '[N/A]' and junk → None."""
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return None


def query_gpu_stats() -> dict | None:
    """One-off read of the first GPU's stats. None when unavailable."""
    code, out, _ = run(
        ["nvidia-smi", f"--query-gpu={_QUERY_FIELDS}",
         "--format=csv,noheader,nounits"],
        timeout=10,
    )
    if code != 0 or not out:
        return None
    fields = [f.strip() for f in out.splitlines()[0].split(",")]
    if len(fields) < 9:
        return None
    return {
        "name": fields[0],
        "driver": fields[1],
        "temp": _to_float(fields[2]),        # °C
        "util": _to_float(fields[3]),        # %
        "mem_used": _to_float(fields[4]),    # MiB
        "mem_total": _to_float(fields[5]),   # MiB
        "power": _to_float(fields[6]),       # W
        "power_limit": _to_float(fields[7]),  # W
        "fan": _to_float(fields[8]),         # %
    }


class MonitorThread(QThread):
    """Periodically reads GPU stats and sends them to the GUI via a signal."""

    sig_data = Signal(dict)   # fresh GPU stats
    sig_error = Signal(str)   # message when monitoring is impossible

    INTERVAL_MS = 2000  # interval between reads

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def stop(self) -> None:
        """Stops the monitoring loop (called when switching tabs)."""
        self._running = False

    def run(self):  # noqa: D102 — QThread method
        error_sent = False
        while self._running:
            stats = query_gpu_stats()
            if stats:
                self.sig_data.emit(stats)
                error_sent = False
            elif not error_sent:
                # The message is sent once — e.g. with NVK nvidia-smi does not exist
                self.sig_error.emit(
                    tr("Monitor wymaga sterownika NVIDIA (nvidia-smi). Przy NVK /"
                       " nouveau statystyki nie są dostępne.")
                )
                error_sent = True
            # Short naps so that stop() works without delays
            for _ in range(self.INTERVAL_MS // 100):
                if not self._running:
                    break
                self.msleep(100)
