# -*- coding: utf-8 -*-
"""Settings page — language, theme and information about the program."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel,
    QVBoxLayout, QWidget,
)

from app import config
from app.gui.theme import apply_theme
from app.i18n import tr

APP_VERSION = "1.0.0"


class SettingsPage(QWidget):
    """Changing the language (PL/EN) and theme (light/dark) + the About section."""

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        box = QGroupBox(tr("Ustawienia programu"))
        form = QFormLayout(box)
        form.setSpacing(12)

        # Interface language
        self.combo_lang = QComboBox()
        self.combo_lang.addItem("Polski", "pl")
        self.combo_lang.addItem("English", "en")
        idx = self.combo_lang.findData(self._cfg.get("language", "pl"))
        self.combo_lang.setCurrentIndex(max(idx, 0))
        self.combo_lang.currentIndexChanged.connect(self._on_language)
        form.addRow(tr("Język interfejsu:"), self.combo_lang)

        # Graphical theme — applied immediately
        self.combo_theme = QComboBox()
        self.combo_theme.addItem(tr("Ciemny"), "dark")
        self.combo_theme.addItem(tr("Jasny"), "light")
        idx = self.combo_theme.findData(self._cfg.get("theme", "dark"))
        self.combo_theme.setCurrentIndex(max(idx, 0))
        self.combo_theme.currentIndexChanged.connect(self._on_theme)
        form.addRow(tr("Motyw:"), self.combo_theme)

        # Boot report — opt-in, disabled by default (the system service stays
        # on the computer and writes diagnostics on every startup)
        self.chk_report = QCheckBox(
            tr("Zapisuj diagnostykę grafiki po każdym rozruchu")
        )
        self.chk_report.setChecked(bool(self._cfg.get("boot_report", False)))
        self.chk_report.setToolTip(tr(
            "Instalacja włączy usługę systemową, która po każdym starcie"
            " komputera zapisuje raport o stanie grafiki (sterownik, moduły,"
            " błędy) do katalogu ~/.local/share/nvidia-installer-gui/raporty."
            " Pomaga zdiagnozować czarny ekran po instalacji sterownika."
            " Zmiana zadziała przy najbliższej instalacji; wyłączenie usunie"
            " usługę z systemu."
        ))
        self.chk_report.toggled.connect(self._on_report)
        form.addRow(tr("Raport rozruchu:"), self.chk_report)

        layout.addWidget(box)

        # Notice about the restart required after changing the language
        self.lbl_restart = QLabel("")
        self.lbl_restart.setObjectName("dim")
        self.lbl_restart.setWordWrap(True)
        layout.addWidget(self.lbl_restart)

        # About
        about = QGroupBox(tr("O programie"))
        a_lay = QVBoxLayout(about)
        a_text = QLabel(
            f"<b>NVIDIA Driver Installer</b> v{APP_VERSION}<br>"
            + tr("Instalator sterowników NVIDIA dla dystrybucji Linux.") + "<br><br>"
            + tr("Obsługiwane rodziny dystrybucji:") + "<br>"
            "• Arch: Arch Linux, CachyOS, EndeavourOS<br>"
            "• Fedora: Fedora 44, Nobara 43<br>"
            "• Debian: Debian, Kubuntu 26.04 LTS, Linux Mint 22.3<br><br>"
            + tr("Metody instalacji: NVK (Mesa), repozytorium dystrybucji,"
                 " plik .run z serwerów NVIDIA.")
        )
        a_text.setWordWrap(True)
        a_text.setTextFormat(Qt.RichText)
        a_lay.addWidget(a_text)
        layout.addWidget(about)
        layout.addStretch()

    def _on_language(self) -> None:
        """Saves the language; a full text change requires a restart."""
        self._cfg["language"] = self.combo_lang.currentData()
        config.save_config(self._cfg)
        self.lbl_restart.setText(
            "ℹ " + tr("Język zostanie zmieniony po ponownym uruchomieniu programu.")
        )

    def _on_theme(self) -> None:
        """The theme changes immediately and is saved permanently."""
        self._cfg["theme"] = self.combo_theme.currentData()
        config.save_config(self._cfg)
        apply_theme(QApplication.instance(), self._cfg["theme"])

    def _on_report(self, checked: bool) -> None:
        """Boot report: remembered immediately, applied by the next installation."""
        self._cfg["boot_report"] = bool(checked)
        config.save_config(self._cfg)
        self.lbl_restart.setText(
            "ℹ " + (tr("Usługa raportu rozruchu zostanie włączona przy"
                       " najbliższej instalacji.") if checked
                    else tr("Usługa raportu rozruchu zostanie usunięta przy"
                            " najbliższej instalacji."))
        )
