"""Anarchy Radio FM GUI Theme — colours, fonts, and stylesheet."""

BG          = "#0a0a0a"
BG_FIELD    = "#0f1a0f"
BG_HOVER    = "#1a2e1a"
GREEN       = "#33ff33"
GREEN_DIM   = "#1a8c1a"
GREEN_FAINT = "#0d4d0d"
CYAN        = "#33ffcc"
AMBER       = "#ccaa33"
RED_DIM     = "#8c1a1a"
BORDER      = "#1a4d1a"

FONT_FAMILY = "Consolas"

STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {GREEN};
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QLabel {{
    background: transparent;
    padding: 0px;
}}
QLineEdit {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    border-radius: 3px;
    color: {GREEN};
    padding: 6px 8px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
    selection-background-color: {GREEN_DIM};
}}
QLineEdit:focus {{
    border: 1px solid {GREEN_DIM};
}}
QPushButton {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    border-radius: 3px;
    color: {GREEN};
    padding: 6px 14px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border: 1px solid {GREEN_DIM};
}}
QPushButton:pressed {{
    background-color: {GREEN_FAINT};
}}
QPushButton:checked {{
    background-color: {GREEN_FAINT};
    border: 1px solid {GREEN_DIM};
    color: {GREEN};
}}
QPushButton#playBtn {{
    font-size: 16px;
    font-weight: bold;
    padding: 6px 18px;
}}
QPushButton#panelBtn {{
    font-size: 13px;
    font-weight: bold;
    padding: 8px 20px;
    min-width: 100px;
}}
QPushButton#panelBtn:checked {{
    background-color: {GREEN_DIM};
    color: {BG};
}}
QPushButton#launchBtn {{
    background-color: {GREEN_FAINT};
    border: 1px solid {GREEN_DIM};
    color: {GREEN};
    font-size: 15px;
    font-weight: bold;
    padding: 10px 20px;
}}
QPushButton#launchBtn:hover {{
    background-color: {GREEN_DIM};
    color: {BG};
}}
QSlider::groove:horizontal {{
    background: {BG_FIELD};
    border: 1px solid {BORDER};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {GREEN};
    border: 1px solid {GREEN_DIM};
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {GREEN_DIM};
    border-radius: 3px;
}}
QTextEdit {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    border-radius: 3px;
    color: {GREEN};
    font-family: {FONT_FAMILY};
    font-size: 11px;
    padding: 4px;
    selection-background-color: {GREEN_DIM};
}}
QFrame#divider {{
    background-color: {BORDER};
    max-height: 1px;
}}
QGroupBox {{
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    margin-top: 14px;
    padding: 12px 8px 8px 8px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
    color: {GREEN};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    color: {GREEN};
    font-weight: bold;
}}
QComboBox {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    border-radius: 3px;
    color: {GREEN};
    padding: 4px 8px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QComboBox:hover {{
    border: 1px solid {GREEN_DIM};
}}
QComboBox QAbstractItemView {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    color: {GREEN};
    selection-background-color: {GREEN_DIM};
    font-family: {FONT_FAMILY};
}}
QCheckBox {{
    color: {GREEN};
    font-family: {FONT_FAMILY};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {BG_FIELD};
}}
QCheckBox::indicator:checked {{
    background-color: {GREEN_DIM};
    border: 1px solid {GREEN};
}}
QCheckBox::indicator:hover {{
    border: 1px solid {GREEN_DIM};
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {BG};
}}
QTabBar::tab {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    color: {GREEN_DIM};
    padding: 6px 16px;
    font-family: {FONT_FAMILY};
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background-color: {GREEN_FAINT};
    color: {GREEN};
    border-bottom: 1px solid {BG};
}}
QTabBar::tab:hover {{
    background-color: {BG_HOVER};
}}
QScrollArea {{
    border: none;
    background-color: {BG};
}}
"""
