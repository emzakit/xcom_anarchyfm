"""Options Dialog — path configuration (music folder, game exe, log, workshop, config)."""

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QSpinBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from gui.theme import FONT_FAMILY, PRIMARY, PRIMARY_DIM, PRIMARY_FAINT, AMBER, BORDER
from gui.helpers import make_divider, path_row
from setup import save_config, _create_state_folders, _find_game_config_folder
from setup import find_log_path_silent
import console


class OptionsDialog(QWidget):

    closed = Signal()

    def __init__(self, cfg, engine=None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.engine = engine
        self.setWindowTitle("AFM — Options")
        self.setMinimumWidth(580)
        self.setFixedHeight(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(4)

        title = QLabel("OPTIONS")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY};")
        root.addWidget(title)
        root.addWidget(make_divider())
        root.addSpacing(8)

        # --- Music Folder ---
        self.music_field = path_row(
            root, "Music Library Folder",
            "Where Anarchy Radio FM stores your music. State folders are created automatically.",
            self._browse_music, cfg.get("music_folder", ""),
        )

        # --- Game Executable ---
        self.exe_field = path_row(
            root, "Game Launcher / AML",
            "Your game .exe or Alternative Mod Launcher.",
            self._browse_exe, cfg.get("game_exe", ""),
        )

        # --- Log Path ---
        default_log = r"%USERPROFILE%\Documents\my games\XCOM2 War of the Chosen\XComGame\Logs\Launch.log"
        self.log_field = path_row(
            root, "XCOM 2 Log File",
            f"Default: {default_log}",
            self._browse_log, cfg.get("log_path", ""),
        )

        # --- Workshop Folder ---
        self.workshop_field = path_row(
            root, "Workshop Folder  (optional)",
            r"For community music packs.  <Steam>\steamapps\workshop\content\268500",
            self._browse_folder, cfg.get("workshop_folder", ""),
        )

        # --- Game Config Folder ---
        self.config_field = path_row(
            root, "Game Config Folder",
            "Where XCOM 2 stores user settings. Anarchy Radio FM writes MMS overrides here.",
            self._browse_folder, cfg.get("game_config_folder", ""),
        )

        # --- Radio Mode chunk length ---
        root.addSpacing(10)
        chunk_lbl = QLabel("Radio Mode: minutes before re-tuning")
        chunk_lbl.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        chunk_lbl.setStyleSheet(f"color: {PRIMARY};")
        root.addWidget(chunk_lbl)

        chunk_desc = QLabel(
            "How long a stretch Radio Mode plays before jumping to a fresh "
            "random spot. Station rips run to an hour; decoding one whole "
            "costs hundreds of MB and a long pause before the first note. "
            "Set to 0 to play each track right to its end."
        )
        chunk_desc.setWordWrap(True)
        chunk_desc.setFont(QFont(FONT_FAMILY, 10))
        chunk_desc.setStyleSheet(f"color: {PRIMARY_DIM};")
        root.addWidget(chunk_desc)

        chunk_row = QHBoxLayout()
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(0, 120)
        self.chunk_spin.setSuffix(" min")
        self.chunk_spin.setSpecialValueText("No limit")
        self.chunk_spin.setValue(int(cfg.get("radio_chunk_minutes", 10)))
        self.chunk_spin.setFixedWidth(120)
        chunk_row.addWidget(self.chunk_spin)
        chunk_row.addStretch()
        root.addLayout(chunk_row)

        root.addStretch()
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

        self.cfg["music_folder"] = music
        self.cfg["game_exe"] = exe
        self.cfg["log_path"] = log
        self.cfg["workshop_folder"] = workshop
        self.cfg["game_config_folder"] = config_dir
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
