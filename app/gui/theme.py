# -*- coding: utf-8 -*-
"""Graphical themes: light and dark, with the NVIDIA green accent (#76b900)."""
from __future__ import annotations

# Accent color shared by both themes
ACCENT = "#76b900"
ACCENT_HOVER = "#8fd400"
ACCENT_PRESSED = "#5e9400"

# Color palettes for both themes
_DARK = {
    "bg": "#1e1f22",         # main background
    "bg_alt": "#26282c",     # panel / group background
    "bg_input": "#2d2f34",   # fields, lists
    "fg": "#e8e8e8",         # primary text
    "fg_dim": "#9a9a9a",     # secondary text
    "border": "#3c3f45",
    "sidebar": "#17181a",
    "selection_fg": "#101010",
}
_LIGHT = {
    "bg": "#f4f5f6",
    "bg_alt": "#ffffff",
    "bg_input": "#ffffff",
    "fg": "#1d1d1f",
    "fg_dim": "#6a6a6e",
    "border": "#c9ccd1",
    "sidebar": "#e6e8ea",
    "selection_fg": "#ffffff",
}


def build_qss(dark: bool) -> str:
    """Builds the QSS stylesheet for the selected theme."""
    c = _DARK if dark else _LIGHT
    return f"""
/* ---------- Base ---------- */
QWidget {{
    background-color: {c['bg']};
    color: {c['fg']};
    font-size: 13px;
}}
QLabel {{ background: transparent; }}
QLabel#header {{
    font-size: 20px;
    font-weight: bold;
    color: {ACCENT};
    background: transparent;
}}
QLabel#dim {{ color: {c['fg_dim']}; background: transparent; }}

/* ---------- Panels / groups ---------- */
QGroupBox {{
    background-color: {c['bg_alt']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {ACCENT};
}}

/* ---------- Buttons ---------- */
QPushButton {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 7px 16px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background-color: {c['bg_alt']}; }}
QPushButton:disabled {{ color: {c['fg_dim']}; border-color: {c['border']}; }}
QPushButton#primary {{
    background-color: {ACCENT};
    color: {c['selection_fg']};
    font-weight: bold;
    font-size: 15px;
    padding: 12px 24px;
    border: none;
}}
QPushButton#primary:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background-color: {ACCENT_PRESSED}; }}
QPushButton#primary:disabled {{ background-color: {c['border']}; color: {c['fg_dim']}; }}

/* ---------- Selection / edit fields ---------- */
QComboBox, QLineEdit {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 5px 10px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    selection-background-color: {ACCENT};
    selection-color: {c['selection_fg']};
}}
QRadioButton, QCheckBox {{ background: transparent; spacing: 8px; }}
QRadioButton:disabled, QCheckBox:disabled {{ color: {c['fg_dim']}; }}
QRadioButton:checked {{ color: {ACCENT}; font-weight: bold; }}

/* Clear selection indicators — a gray ring, a green dot when checked */
QRadioButton::indicator {{
    width: 16px; height: 16px;
    border-radius: 10px;
    border: 2px solid {c['fg_dim']};
    background-color: {c['bg_input']};
}}
QRadioButton::indicator:hover {{ border-color: {ACCENT}; }}
QRadioButton::indicator:checked {{
    border: 2px solid {ACCENT};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {ACCENT}, stop:0.55 {ACCENT},
        stop:0.62 {c['bg_input']}, stop:1 {c['bg_input']});
}}
QRadioButton::indicator:disabled {{
    border-color: {c['border']};
    background-color: {c['bg_alt']};
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border-radius: 5px;
    border: 2px solid {c['fg_dim']};
    background-color: {c['bg_input']};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:disabled {{
    border-color: {c['border']};
    background-color: {c['bg_alt']};
}}

/* Installation method frame — highlights the whole row of the selected method */
QFrame#methodRow {{
    border: 1px solid transparent;
    border-left: 4px solid transparent;
    border-radius: 8px;
}}
QFrame#methodRow[selected="true"] {{
    background-color: rgba(118, 185, 0, 40);
    border: 1px solid {ACCENT};
    border-left: 4px solid {ACCENT};
}}

/* Driver update notice — accent callout in the detected-system box */
QLabel#updateNotice {{
    background-color: rgba(118, 185, 0, 40);
    border: 1px solid {ACCENT};
    border-left: 4px solid {ACCENT};
    border-radius: 8px;
    padding: 8px 12px;
}}

/* ---------- Progress bar ---------- */
QProgressBar {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    text-align: center;
    height: 20px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

/* ---------- Log / tables / trees ---------- */
QTextEdit, QPlainTextEdit {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    font-family: "Monospace", "Consolas", monospace;
    font-size: 12px;
}}
QTableWidget, QTreeWidget {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    gridline-color: {c['border']};
    alternate-background-color: {c['bg_alt']};
}}
QHeaderView::section {{
    background-color: {c['bg_alt']};
    border: none;
    border-bottom: 1px solid {c['border']};
    padding: 6px;
    font-weight: bold;
}}
QTableWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {ACCENT};
    color: {c['selection_fg']};
}}

/* ---------- Sidebar ---------- */
QListWidget#sidebar {{
    background-color: {c['sidebar']};
    border: none;
    outline: none;
    font-size: 14px;
}}
QListWidget#sidebar::item {{
    padding: 14px 16px;
    border-left: 3px solid transparent;
}}
QListWidget#sidebar::item:hover {{ background-color: {c['bg_alt']}; }}
QListWidget#sidebar::item:selected {{
    background-color: {c['bg']};
    border-left: 3px solid {ACCENT};
    color: {ACCENT};
    font-weight: bold;
}}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {{
    background: {c['bg']};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c['border']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

QStatusBar {{ background-color: {c['sidebar']}; color: {c['fg_dim']}; }}
QToolTip {{
    background-color: {c['bg_alt']};
    color: {c['fg']};
    border: 1px solid {ACCENT};
    padding: 4px;
}}
"""


def apply_theme(app, name: str) -> None:
    """Applies the theme ("dark" or "light") to the whole application."""
    app.setStyleSheet(build_qss(dark=(name != "light")))
