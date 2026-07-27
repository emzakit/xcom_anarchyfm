"""Shared UI helpers for the Anarchy Radio FM GUI."""

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from gui.theme import FONT_FAMILY, PRIMARY, PRIMARY_DIM, BORDER


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
