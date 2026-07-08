# -*- coding: utf-8 -*-
"""Installation history page — a table of entries with full log preview."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from app.core import history
from app.i18n import tr


class LogDialog(QDialog):
    """A window with the full log of the selected installation."""

    def __init__(self, title: str, log_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 560)
        lay = QVBoxLayout(self)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(log_text)
        lay.addWidget(view)
        btn = QPushButton(tr("Zamknij"))
        btn.clicked.connect(self.accept)
        lay.addWidget(btn, alignment=Qt.AlignRight)


class HistoryPage(QWidget):
    """All past installations with date, method, version and status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(tr("Podwójne kliknięcie wpisu otwiera pełny log instalacji."))
        info.setObjectName("dim")
        layout.addWidget(info)

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton(tr("Odśwież"))
        btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(btn_refresh)
        btn_clear = QPushButton(tr("Wyczyść historię"))
        btn_clear.clicked.connect(self._clear)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            tr("Data"), tr("Metoda"), tr("Wersja"), tr("Dystrybucja"), tr("Status"),
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 190)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 190)
        self.table.itemDoubleClicked.connect(self._show_log)
        layout.addWidget(self.table, stretch=1)

    def showEvent(self, event) -> None:  # noqa: N802 — Qt API
        """The history refreshes every time the tab is entered."""
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        self._entries = history.load_history()
        self.table.setRowCount(len(self._entries))
        for row, e in enumerate(self._entries):
            # Method, version and status are stored in Polish — translated when
            # displayed (tr() leaves version numbers and packages unchanged)
            values = [
                e.get("data", ""), tr(e.get("metoda", "")),
                tr(e.get("wersja", "")),
                e.get("dystrybucja", ""), tr(e.get("status", "")),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if col == 4:  # status coloring (by the stored value)
                    item.setForeground(
                        QColor("#76b900") if e.get("status") == "sukces"
                        else QColor("#f44336")
                    )
                self.table.setItem(row, col, item)

    def _show_log(self, item: QTableWidgetItem) -> None:
        entry = self._entries[item.row()]
        title = f"{tr('Log instalacji')} — {entry.get('data', '')}"
        LogDialog(title, history.read_log(entry), self).exec()

    def _clear(self) -> None:
        if not self._entries:
            return
        odp = QMessageBox.question(
            self, tr("Wyczyść historię"),
            tr("Usunąć wszystkie wpisy historii wraz z plikami logów?"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if odp == QMessageBox.Yes:
            history.clear_history()
            self.refresh()
