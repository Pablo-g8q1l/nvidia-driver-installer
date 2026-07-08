# -*- coding: utf-8 -*-
"""Main program window: sidebar with tabs + background system detection."""
from __future__ import annotations

from PySide6.QtCore import QSize, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QStackedWidget, QVBoxLayout, QWidget,
)

from app.core.distro import detect_distro
from app.core.gpu import detect_gpus, detect_installed_driver
from app.gui.page_diagnostics import DiagnosticsPage
from app.gui.page_history import HistoryPage
from app.gui.page_install import InstallPage
from app.gui.page_monitor import MonitorPage
from app.gui.page_settings import SettingsPage
from app.i18n import tr


class DetectThread(QThread):
    """Detects the distribution, GPU and driver in the background so the GUI starts immediately."""

    sig_done = Signal(dict)

    def run(self):  # noqa: D102
        self.sig_done.emit({
            "distro": detect_distro(),
            "gpus": detect_gpus(),
            "driver": detect_installed_driver(),
        })


class MainWindow(QMainWindow):
    """Main window: Installation / Monitor / Diagnostics / History / Settings."""

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self.setWindowTitle("NVIDIA Driver Installer")
        self.resize(1000, 720)
        self._build_ui()
        self._start_detection()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Sidebar ----------------------------------------------------------
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(210)
        self.sidebar.setIconSize(QSize(22, 22))
        zakladki = [
            ("🖥  " + tr("Instalacja")),
            ("📊  " + tr("Monitor GPU")),
            ("🩺  " + tr("Diagnostyka")),
            ("🕘  " + tr("Historia")),
            ("⚙  " + tr("Ustawienia")),
        ]
        for nazwa in zakladki:
            QListWidgetItem(nazwa, self.sidebar)
        root.addWidget(self.sidebar)

        # --- Right side: header + pages ----------------------------------------
        right = QVBoxLayout()
        right.setContentsMargins(16, 12, 16, 12)

        self.lbl_header = QLabel("NVIDIA Driver Installer")
        self.lbl_header.setObjectName("header")
        right.addWidget(self.lbl_header)

        self.pages = QStackedWidget()
        self.page_install = InstallPage(self._cfg)
        self.page_monitor = MonitorPage()
        self.page_diag = DiagnosticsPage()
        self.page_history = HistoryPage()
        self.page_settings = SettingsPage(self._cfg)
        for p in (self.page_install, self.page_monitor, self.page_diag,
                  self.page_history, self.page_settings):
            self.pages.addWidget(p)
        right.addWidget(self.pages, stretch=1)

        right_widget = QWidget()
        right_widget.setLayout(right)
        root.addWidget(right_widget, stretch=1)

        self.setCentralWidget(central)
        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        # After a successful installation we refresh the system information
        self.page_install.sig_system_changed.connect(self._start_detection)

        self.statusBar().showMessage(tr("Wykrywanie systemu..."))

    # ------------------------------------------------------------- detection
    def _start_detection(self) -> None:
        self._detect_thread = DetectThread(self)
        self._detect_thread.sig_done.connect(self._on_detected)
        self._detect_thread.start()

    def _on_detected(self, state: dict) -> None:
        self.page_install.set_system_state(state)
        distro = state["distro"]
        gpus = state["gpus"]
        gpu_txt = gpus[0].name if gpus else tr("brak karty NVIDIA")
        self.statusBar().showMessage(f"{distro.name}  |  {gpu_txt}")

    # ------------------------------------------------------------- closing
    def closeEvent(self, event) -> None:  # noqa: N802 — Qt API
        """Stops the monitor thread before the window closes."""
        self.page_monitor.stop_monitor()
        super().closeEvent(event)
