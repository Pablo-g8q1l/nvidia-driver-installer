#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NVIDIA Driver Installer — application entry point.

Launching: ./NVIDIA-Installer.run (the script creates a virtual environment)
or manually: python3 main.py (requires PySide6 and requests to be installed).
"""
import sys

from PySide6.QtWidgets import QApplication

from app import config, i18n
from app.core import utils
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme


def main() -> int:
    """Creates the Qt application, applies the theme and shows the main window."""
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
