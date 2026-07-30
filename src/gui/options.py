"""Options Dialog — path configuration (music folder, game exe, log, workshop, config)."""

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QSpinBox,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from gui.theme import FONT_FAMILY, PRIMARY, PRIMARY_DIM, PRIMARY_FAINT, AMBER, BORDER
from gui.helpers import make_divider, path_row, paint_own_background
from setup import save_config, _create_state_folders, _find_game_config_folder
from setup import find_log_path_silent, create_addon_test_folder
import console


class OptionsDialog(QWidget):

    closed = Signal()

    def __init__(self, cfg, engine=None, parent=None):
        super().__init__(parent)
        paint_own_background(self)
        self.cfg = cfg
        self.engine = engine
        self.setWindowTitle("AFM — Options")
        # Deliberately NOT a fixed height. Every description here is a
        # word-wrapped label, which means its height depends on its width; pin
        # the window shorter than the content needs and the layout has two
        # states it can settle into, flipping between them on any relayout —
        # which looks like the dialog scrambling itself when you drag it.
        # A scroll area plus a resizable window means adding another row later
        # can't bring that back.
        self.setMinimumSize(600, 480)
        self.resize(620, 760)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(4)

        title = QLabel("OPTIONS")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY};")
        root.addWidget(title)
        root.addWidget(make_divider())
        root.addSpacing(8)

        # Everything between the title and the buttons scrolls.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        form = QVBoxLayout(inner)
        form.setContentsMargins(0, 0, 8, 0)   # room for the scrollbar
        form.setSpacing(4)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # --- Music Folder ---
        self.music_field = path_row(
            form, "Music Library Folder",
            "Where Anarchy Radio FM stores your music. State folders are created automatically.",
            self._browse_music, cfg.get("music_folder", ""),
        )

        # --- Game Executable ---
        self.exe_field = path_row(
            form, "Game Launcher / AML",
            "Your game .exe or Alternative Mod Launcher.",
            self._browse_exe, cfg.get("game_exe", ""),
        )

        # --- Log Path ---
        default_log = r"%USERPROFILE%\Documents\my games\XCOM2 War of the Chosen\XComGame\Logs\Launch.log"
        self.log_field = path_row(
            form, "XCOM 2 Log File",
            f"Default: {default_log}",
            self._browse_log, cfg.get("log_path", ""),
        )

        # --- Workshop Folder ---
        self.workshop_field = path_row(
            form, "Workshop Folder  (required)",
            "How I find the installed mod — without it the game's own music "
            r"won't be silenced.  <Steam>\steamapps\workshop\content\268500",
            self._browse_folder, cfg.get("workshop_folder", ""),
        )

        # --- Game Config Folder ---
        self.config_field = path_row(
            form, "Game Config Folder",
            "Where XCOM 2 stores user settings, shared with the in-game MCM menu.",
            self._browse_folder, cfg.get("game_config_folder", ""),
        )

        # --- Addon Testing Folder ---
        self.addon_test_field = path_row(
            form, "Addon Testing Folder  (optional)",
            "Building a music pack? Drop the in-progress mod folder in here and "
            "it plays in-game as though you'd subscribed to it on the Workshop.",
            self._browse_folder, cfg.get("addon_test_folder", ""),
        )

        # --- Radio Mode chunk length ---
        form.addSpacing(10)
        chunk_lbl = QLabel("Radio Mode: minutes before re-tuning")
        chunk_lbl.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        chunk_lbl.setStyleSheet(f"color: {PRIMARY};")
        form.addWidget(chunk_lbl)

        chunk_desc = QLabel(
            "How long a stretch Radio Mode plays before jumping to a fresh "
            "random spot. Station rips run to an hour; decoding one whole "
            "costs hundreds of MB and a long pause before the first note. "
            "Set to 0 to play each track right to its end."
        )
        chunk_desc.setWordWrap(True)
        chunk_desc.setFont(QFont(FONT_FAMILY, 10))
        chunk_desc.setStyleSheet(f"color: {PRIMARY_DIM};")
        form.addWidget(chunk_desc)

        chunk_row = QHBoxLayout()
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(0, 120)
        self.chunk_spin.setSuffix(" min")
        self.chunk_spin.setSpecialValueText("No limit")
        self.chunk_spin.setValue(int(cfg.get("radio_chunk_minutes", 10)))
        self.chunk_spin.setFixedWidth(120)
        chunk_row.addWidget(self.chunk_spin)
        chunk_row.addStretch()
        form.addLayout(chunk_row)

        # Keeps the rows packed at the top of the scroll body instead of
        # spreading out when the window is taller than the content.
        form.addStretch()

        root.addWidget(make_divider())
        root.addSpacing(8)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        save_btn = QPushButton("Save")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFixedWidth(100)
        save_btn.setStyleSheet(
            f"background-color: {PRIMARY_FAINT}; border: 1px solid {PRIMARY_DIM}; "
            f"font-weight: bold; padding: 8px;"
        )
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

        # --- Status ---
        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {AMBER}; font-size: 11px;")
        self.status.setAlignment(Qt.AlignCenter)
        root.addWidget(self.status)

    # --- Browse handlers ---
    def _browse_music(self, field):
        path = QFileDialog.getExistingDirectory(self, "Select Music Library Folder")
        if path:
            field.setText(os.path.normpath(path))

    def _browse_exe(self, field):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Game Executable", "",
            "Executables (*.exe);;All Files (*.*)"
        )
        if path:
            field.setText(os.path.normpath(path))

    def _browse_log(self, field):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Launch.log", "",
            "Log Files (*.log);;All Files (*.*)"
        )
        if path:
            field.setText(os.path.normpath(path))

    def _browse_folder(self, field):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            field.setText(os.path.normpath(path))

    def _on_save(self):
        music = self.music_field.text().strip()
        exe = self.exe_field.text().strip()
        log = self.log_field.text().strip()
        workshop = self.workshop_field.text().strip()
        config_dir = self.config_field.text().strip()
        addon_test = self.addon_test_field.text().strip()

        if not music:
            self.status.setText("SHEN:  I need a music folder, Commander.")
            return
        if not exe:
            self.status.setText("SHEN:  I need a game executable, Commander.")
            return

        if not log:
            log = find_log_path_silent()
        if not log:
            self.status.setText("SHEN:  Couldn't find the log file. Browse for it.")
            return

        if not config_dir:
            config_dir = _find_game_config_folder(log) or ""
        if not config_dir:
            userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
            config_dir = os.path.join(
                userprofile, "Documents", "my games",
                "XCOM2 War of the Chosen", "XComGame", "Config"
            )

        # Create music folder + state subfolders
        if not os.path.isdir(music):
            try:
                os.makedirs(music)
            except Exception as e:
                self.status.setText(f"SHEN:  Couldn't create folder: {e}")
                return
        _create_state_folders(music)

        # Optional — an empty box means "not a pack author", not an error.
        if addon_test:
            create_addon_test_folder(addon_test)

        self.cfg["music_folder"] = music
        self.cfg["game_exe"] = exe
        self.cfg["log_path"] = log
        self.cfg["workshop_folder"] = workshop
        self.cfg["game_config_folder"] = config_dir
        self.cfg["addon_test_folder"] = addon_test
        self.cfg["radio_chunk_minutes"] = int(self.chunk_spin.value())
        save_config(self.cfg)

        # The chunk length applies to the next track Radio Mode loads, so
        # push it live rather than making it another restart-only setting.
        if self.engine:
            self.engine.set_radio_chunk_minutes(self.cfg["radio_chunk_minutes"])

        console.shen("Config saved. Restart Anarchy Radio FM for path changes to take effect.")
        self.close()

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
