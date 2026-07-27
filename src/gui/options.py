"""Options Dialog — path configuration (music folder, game exe, log, workshop, config)."""

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from gui.theme import FONT_FAMILY, GREEN, GREEN_DIM, GREEN_FAINT, AMBER, BORDER
from gui.helpers import make_divider, path_row
from setup import save_config, import_workshop_mods, _create_state_folders, _find_game_config_folder
from setup import find_log_path_silent
import console


class OptionsDialog(QWidget):

    closed = Signal()

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("AFM — Options")
        self.setMinimumWidth(580)
        self.setFixedHeight(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(4)

        title = QLabel("OPTIONS")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setStyleSheet(f"color: {GREEN};")
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
            f"background-color: {GREEN_FAINT}; border: 1px solid {GREEN_DIM}; "
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
        save_config(self.cfg)

        if workshop:
            import_workshop_mods(self.cfg)

        console.shen("Config saved. Restart Anarchy Radio FM for path changes to take effect.")
        self.close()

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
