# -*- coding: utf-8 -*-
"""Monitor GPU w czasie rzeczywistym — odpytuje nvidia-smi co 2 sekundy."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.i18n import tr

from .utils import run

# Pola pobierane z nvidia-smi (kolejność musi zgadzać się z parsowaniem)
_QUERY_FIELDS = (
    "name,driver_version,temperature.gpu,utilization.gpu,"
    "memory.used,memory.total,power.draw,power.limit,fan.speed"
)


def _to_float(value: str) -> float | None:
    """Zamienia pole nvidia-smi na liczbę; '[N/A]' i śmieci → None."""
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return None


def query_gpu_stats() -> dict | None:
    """Jednorazowy odczyt statystyk pierwszego GPU. None gdy niedostępne."""
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
    """Cyklicznie odczytuje statystyki GPU i wysyła je sygnałem do GUI."""

    sig_data = Signal(dict)   # świeże statystyki GPU
    sig_error = Signal(str)   # komunikat, gdy monitorowanie niemożliwe

    INTERVAL_MS = 2000  # odstęp między odczytami

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def stop(self) -> None:
        """Zatrzymuje pętlę monitorowania (wywoływane przy zmianie zakładki)."""
        self._running = False

    def run(self):  # noqa: D102 — metoda QThread
        error_sent = False
        while self._running:
            stats = query_gpu_stats()
            if stats:
                self.sig_data.emit(stats)
                error_sent = False
            elif not error_sent:
                # Komunikat wysyłamy raz — np. przy NVK nvidia-smi nie istnieje
                self.sig_error.emit(
                    tr("Monitor wymaga sterownika NVIDIA (nvidia-smi). Przy NVK /"
                       " nouveau statystyki nie są dostępne.")
                )
                error_sent = True
            # Krótkie drzemki, by stop() działał bez opóźnień
            for _ in range(self.INTERVAL_MS // 100):
                if not self._running:
                    break
                self.msleep(100)
