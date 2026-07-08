# -*- coding: utf-8 -*-
"""GPU monitor page — live statistics from nvidia-smi (every 2 seconds)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout, QGroupBox, QLabel, QProgressBar, QVBoxLayout, QWidget,
)

from app.core.monitor import MonitorThread
from app.i18n import tr


class MonitorPage(QWidget):
    """Temperature, GPU usage, VRAM, power draw and fan."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: MonitorThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # GPU name and driver version
        self.lbl_gpu = QLabel(tr("Oczekiwanie na dane z GPU..."))
        self.lbl_gpu.setObjectName("header")
        layout.addWidget(self.lbl_gpu)
        self.lbl_driver = QLabel("")
        self.lbl_driver.setObjectName("dim")
        layout.addWidget(self.lbl_driver)

        box = QGroupBox(tr("Statystyki na żywo"))
        grid = QGridLayout(box)
        grid.setVerticalSpacing(14)

        # Temperature — a 0-100 °C bar, color depending on the value
        grid.addWidget(QLabel(tr("Temperatura:")), 0, 0)
        self.bar_temp = QProgressBar()
        grid.addWidget(self.bar_temp, 0, 1)

        # GPU usage
        grid.addWidget(QLabel(tr("Użycie GPU:")), 1, 0)
        self.bar_util = QProgressBar()
        grid.addWidget(self.bar_util, 1, 1)

        # VRAM
        grid.addWidget(QLabel(tr("Pamięć VRAM:")), 2, 0)
        self.bar_mem = QProgressBar()
        grid.addWidget(self.bar_mem, 2, 1)
        self.lbl_mem = QLabel("—")
        self.lbl_mem.setObjectName("dim")
        grid.addWidget(self.lbl_mem, 3, 1)

        # Power draw
        grid.addWidget(QLabel(tr("Pobór mocy:")), 4, 0)
        self.bar_power = QProgressBar()
        grid.addWidget(self.bar_power, 4, 1)
        self.lbl_power = QLabel("—")
        self.lbl_power.setObjectName("dim")
        grid.addWidget(self.lbl_power, 5, 1)

        # Fan
        grid.addWidget(QLabel(tr("Wentylator:")), 6, 0)
        self.bar_fan = QProgressBar()
        grid.addWidget(self.bar_fan, 6, 1)

        grid.setColumnStretch(1, 1)
        layout.addWidget(box)

        # Message shown when the monitor is unavailable (e.g. NVK without nvidia-smi)
        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("dim")
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)
        layout.addStretch()

    # ------------------------------------------------ start/stop on tab change
    def showEvent(self, event) -> None:  # noqa: N802 — Qt API
        """The monitor runs only while the tab is visible (to save resources)."""
        super().showEvent(event)
        if self._thread is None:
            self._thread = MonitorThread(self)
            self._thread.sig_data.connect(self._on_data)
            self._thread.sig_error.connect(self._on_error)
            self._thread.start()

    def hideEvent(self, event) -> None:  # noqa: N802 — Qt API
        super().hideEvent(event)
        self.stop_monitor()

    def stop_monitor(self) -> None:
        """Stops the monitor thread (also when the program is closing)."""
        if self._thread is not None:
            self._thread.stop()
            self._thread.wait(2000)
            self._thread = None

    # ------------------------------------------------ data update
    def _on_data(self, s: dict) -> None:
        self.lbl_info.setText("")
        self.lbl_gpu.setText(s.get("name") or "GPU")
        self.lbl_driver.setText(f"{tr('Sterownik')}: {s.get('driver', '—')}")

        # Temperature with color: green < 70°C, orange < 85°C, red above
        temp = s.get("temp")
        if temp is not None:
            kolor = "#76b900" if temp < 70 else ("#ff9800" if temp < 85 else "#f44336")
            self.bar_temp.setValue(min(int(temp), 100))
            self.bar_temp.setFormat(f"{temp:.0f} °C")
            self.bar_temp.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {kolor}; border-radius: 5px; }}"
            )
        else:
            self.bar_temp.setValue(0)
            self.bar_temp.setFormat(tr("brak danych"))

        util = s.get("util")
        self.bar_util.setValue(int(util) if util is not None else 0)
        self.bar_util.setFormat(f"{util:.0f}%" if util is not None else tr("brak danych"))

        used, total = s.get("mem_used"), s.get("mem_total")
        if used is not None and total:
            self.bar_mem.setValue(int(used * 100 / total))
            self.bar_mem.setFormat(f"{used * 100 / total:.0f}%")
            self.lbl_mem.setText(f"{used:.0f} MiB / {total:.0f} MiB")
        else:
            self.bar_mem.setValue(0)
            self.lbl_mem.setText(tr("brak danych"))

        power, limit = s.get("power"), s.get("power_limit")
        if power is not None and limit:
            self.bar_power.setValue(int(power * 100 / limit))
            self.bar_power.setFormat(f"{power * 100 / limit:.0f}%")
            self.lbl_power.setText(f"{power:.1f} W / {limit:.0f} W")
        elif power is not None:
            self.lbl_power.setText(f"{power:.1f} W")
        else:
            self.bar_power.setValue(0)
            self.lbl_power.setText(tr("brak danych"))

        fan = s.get("fan")
        if fan is not None:
            self.bar_fan.setValue(min(int(fan), 100))
            self.bar_fan.setFormat(f"{fan:.0f}%")
        else:
            self.bar_fan.setValue(0)
            self.bar_fan.setFormat(tr("brak danych"))

    def _on_error(self, message: str) -> None:
        self.lbl_gpu.setText(tr("Monitor niedostępny"))
        self.lbl_info.setText(message)
