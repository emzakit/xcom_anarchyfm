"""Anarchy Radio FM GUI Theme — colours, fonts, and stylesheet.

Palette lifted from the XCOM 2 Avenger UI: cyan-teal on a near-black navy
for everything structural, with the amber/gold from the Geoscape status
lights as the secondary — used sparingly, for log lines that want to stand
out from the wall of teal (incoming signals and warnings).

The primary constants are named PRIMARY* rather than by colour so this can be
re-skinned without every call site reading like a lie.
"""

BG            = "#08141a"   # near-black navy — window background
BG_FIELD      = "#0e222b"   # panel / input fill
BG_HOVER      = "#163a47"
PRIMARY       = "#5fd3e3"   # main cyan — body text, icons, active borders
PRIMARY_DIM   = "#2b8998"   # dimmed labels, secondary captions
PRIMARY_FAINT = "#103641"   # button fill, pressed state
PRIMARY_ON    = "#17505f"   # checked/lit toggle fill — reads as ON at a glance
ACCENT        = "#a8e9f2"   # bright highlight — track names, selected rows
AMBER         = "#d9a441"   # secondary — incoming signals, warnings
RED_DIM       = "#a3502a"   # errors, kept brown-red so it sits in-palette
BORDER        = "#1d5a68"
MUTED         = "#3d5560"   # log noise — readable, but recedes into the panel

FONT_FAMILY = "Consolas"

# Checkbox tick mark. Qt wants forward slashes in stylesheet url()s even on
# Windows, and a bare drive-letter path with backslashes silently fails to
# load — leaving a checkbox that looks identical on and off.
from paths import resource_path

_CHECK_X = resource_path("assets", "check_x.svg").replace("\\", "/")

STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {PRIMARY};
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
    color: {PRIMARY};
    padding: 6px 8px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
    selection-background-color: {PRIMARY_DIM};
}}
QLineEdit:focus {{
    border: 1px solid {PRIMARY_DIM};
}}
QPushButton {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    border-radius: 3px;
    color: {PRIMARY};
    padding: 6px 14px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border: 1px solid {PRIMARY_DIM};
}}
QPushButton:pressed {{
    background-color: {PRIMARY_FAINT};
}}
/* Checked has to read as ON at a glance — the state toggles are the main
   thing you scan on this window. PRIMARY_FAINT alone sat too close to
   BG_FIELD to tell apart, so lit uses a brighter fill, a full-strength
   border and the accent text colour. */
QPushButton:checked {{
    background-color: {PRIMARY_ON};
    border: 1px solid {PRIMARY};
    color: {ACCENT};
    font-weight: bold;
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
    background-color: {PRIMARY_DIM};
    color: {BG};
}}
QPushButton#launchBtn {{
    background-color: {PRIMARY_FAINT};
    border: 1px solid {PRIMARY_DIM};
    color: {PRIMARY};
    font-size: 15px;
    font-weight: bold;
    padding: 10px 20px;
}}
QPushButton#launchBtn:hover {{
    background-color: {PRIMARY_DIM};
    color: {BG};
}}
QSlider::groove:horizontal {{
    background: {BG_FIELD};
    border: 1px solid {BORDER};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {PRIMARY};
    border: 1px solid {PRIMARY_DIM};
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {PRIMARY_DIM};
    border-radius: 3px;
}}
QTextEdit {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    border-radius: 3px;
    color: {PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: 11px;
    padding: 4px;
    selection-background-color: {PRIMARY_DIM};
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
    color: {PRIMARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    color: {PRIMARY};
    font-weight: bold;
}}
QComboBox {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    border-radius: 3px;
    color: {PRIMARY};
    padding: 4px 8px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QComboBox:hover {{
    border: 1px solid {PRIMARY_DIM};
}}
QComboBox QAbstractItemView {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    color: {PRIMARY};
    selection-background-color: {PRIMARY_DIM};
    font-family: {FONT_FAMILY};
}}
QCheckBox {{
    color: {PRIMARY};
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
/* Checked draws an X rather than a solid fill — a filled block reads as
   "disabled" or "greyed out" at a glance on a dark theme, where an X can only
   mean on. It has to come from an image file: Qt stylesheets can't stroke a
   shape, and they don't take data: URIs either. */
QCheckBox::indicator:checked {{
    background-color: {BG_FIELD};
    border: 1px solid {PRIMARY};
    image: url("{_CHECK_X}");
}}
QCheckBox::indicator:hover {{
    border: 1px solid {PRIMARY_DIM};
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {BG};
}}
QTabBar::tab {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    color: {PRIMARY_DIM};
    padding: 6px 16px;
    font-family: {FONT_FAMILY};
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background-color: {PRIMARY_FAINT};
    color: {PRIMARY};
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
