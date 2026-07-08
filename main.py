#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NVIDIA Driver Installer — punkt wejścia aplikacji.

Uruchamianie: ./NVIDIA-Installer.run (skrypt tworzy środowisko wirtualne)
lub ręcznie: python3 main.py (wymaga zainstalowanego PySide6 i requests).
"""
import sys

from PySide6.QtWidgets import QApplication

from app import config, i18n
from app.core import utils
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme


def main() -> int:
    """Tworzy aplikację Qt, nakłada motyw i pokazuje główne okno."""
    utils.ensure_dirs()
    cfg = config.load_config()
    i18n.set_language(cfg.get("language", "pl"))

    app = QApplication(sys.argv)
    app.setApplicationName("NVIDIA Driver Installer")
    app.setOrganizationName("nvidia-installer-gui")
    apply_theme(app, cfg.get("theme", "dark"))

    window = MainWindow(cfg)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
