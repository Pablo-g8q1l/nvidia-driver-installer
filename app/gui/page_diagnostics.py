# -*- coding: utf-8 -*-
"""Diagnostics page — system checks and saving the report to a file."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.core.diagnostics import CheckResult, build_report, run_diagnostics
from app.i18n import tr

# Colors and labels for the check statuses
_STATUS_STYLE = {
    "ok": ("OK", QColor("#76b900")),
    "uwaga": ("UWAGA", QColor("#ff9800")),
    "blad": ("BŁĄD", QColor("#f44336")),
    "info": ("INFO", QColor("#2196f3")),
}


class DiagThread(QThread):
    """Runs the diagnostic checks in the background so as not to block the GUI."""

    sig_done = Signal(list)

    def run(self):  # noqa: D102
        self.sig_done.emit(run_diagnostics())


class DiagnosticsPage(QWidget):
    """A list of checks with statuses and a detailed error report."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[CheckResult] = []
        self._thread: DiagThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(
            tr("Diagnostyka sprawdza stan sterownika, Secure Boot, nagłówki"
               " jądra, DKMS i logi. Uruchom ją, gdy coś nie działa.")
        )
        info.setObjectName("dim")
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_row = QHBoxLayout()
        self.btn_run = QPushButton(tr("Uruchom diagnostykę"))
        self.btn_run.setObjectName("primary")
        self.btn_run.clicked.connect(self._start)
        btn_row.addWidget(self.btn_run)
        self.btn_save = QPushButton(tr("Zapisz raport..."))
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_report)
        btn_row.addWidget(self.btn_save)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("Kontrola"), tr("Status"), tr("Szczegóły")])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 80)
        self.tree.setWordWrap(True)
        layout.addWidget(self.tree, stretch=1)

        self.lbl_summary = QLabel("")
        layout.addWidget(self.lbl_summary)

    def _start(self) -> None:
        self.btn_run.setEnabled(False)
        self.lbl_summary.setText(tr("Trwa sprawdzanie systemu..."))
        self._thread = DiagThread(self)
        self._thread.sig_done.connect(self._on_done)
        self._thread.start()

    def _on_done(self, results: list) -> None:
        self._results = results
        self.btn_run.setEnabled(True)
        self.btn_save.setEnabled(True)
        self.tree.clear()
        for r in results:
            label, color = _STATUS_STYLE.get(r.status, ("?", QColor("gray")))
            item = QTreeWidgetItem([r.kategoria, tr(label), r.opis])
            item.setForeground(1, color)
            item.setToolTip(2, r.opis)
            self.tree.addTopLevelItem(item)

        bledy = sum(1 for r in results if r.status == "blad")
        uwagi = sum(1 for r in results if r.status == "uwaga")
        if bledy:
            self.lbl_summary.setText(
                f"❌ {tr('Wykryto problemy:')} {bledy} {tr('błędów')},"
                f" {uwagi} {tr('ostrzeżeń')}"
            )
        elif uwagi:
            self.lbl_summary.setText(
                f"⚠ {tr('System działa, ale jest')} {uwagi} {tr('ostrzeżeń')}"
            )
        else:
            self.lbl_summary.setText("✅ " + tr("Wszystkie kontrole zakończone pomyślnie"))

    def _save_report(self) -> None:
        """Saves the full text report to a location chosen by the user."""
        if not self._results:
            return
        domyslna = str(Path.home() / "raport-nvidia.txt")
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Zapisz raport diagnostyczny"), domyslna,
            tr("Pliki tekstowe (*.txt)"),
        )
        if not path:
            return
        try:
            Path(path).write_text(build_report(self._results), encoding="utf-8")
            QMessageBox.information(
                self, tr("Zapisano"), tr("Raport zapisany w:") + f"\n{path}"
            )
        except OSError as e:
            QMessageBox.critical(
                self, tr("Błąd zapisu"), tr("Nie udało się zapisać raportu:") + f"\n{e}"
            )
