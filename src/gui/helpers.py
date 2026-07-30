"""Shared UI helpers for the Anarchy Radio FM GUI."""

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from gui.theme import FONT_FAMILY, PRIMARY, PRIMARY_DIM, BORDER


def paint_own_background(widget):
    """Make a QWidget subclass actually paint its stylesheet background.

    Qt honours `background-color` from a stylesheet on stock QWidgets, but NOT
    on a QWidget *subclass* — a subclass is assumed to do its own painting, so
    the rule is silently ignored unless WA_StyledBackground is set.

    Every window here is a QWidget subclass, so without this they never clear
    their background: the window looks right while it sits still, then smears
    stale pixels the moment you drag it, with fields going blank and labels
    truncating mid-sentence.

    Call once per top-level window, before the stylesheet is applied.
    """
    widget.setAttribute(Qt.WA_StyledBackground, True)


def make_divider():
    line = QFrame()
    line.setObjectName("divider")
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    return line


def path_row(parent_layout, label_text, tooltip, browse_fn, initial="", browse_label="Browse..."):
    """Create a label + line edit + browse button row. Returns the QLineEdit."""
    lbl = QLabel(label_text)
    lbl.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
    lbl.setStyleSheet(f"color: {PRIMARY};")
    parent_layout.addWidget(lbl)

    if tooltip:
        hint = QLabel(tooltip)
        hint.setFont(QFont(FONT_FAMILY, 10))
        hint.setStyleSheet(f"color: {PRIMARY_DIM};")
        hint.setWordWrap(True)
        parent_layout.addWidget(hint)

    row = QHBoxLayout()
    row.setSpacing(6)
    field = QLineEdit()
    field.setText(initial)
    field.setPlaceholderText("Select a path...")
    row.addWidget(field)

    btn = QPushButton(browse_label)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFixedWidth(90)
    btn.clicked.connect(lambda: browse_fn(field))
    row.addWidget(btn)
    parent_layout.addLayout(row)
    parent_layout.addSpacing(10)
    return field


def html_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;")
