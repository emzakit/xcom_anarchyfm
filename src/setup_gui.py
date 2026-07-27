"""Anarchy Radio FM Setup GUI — green retro terminal-inspired config wizard."""

import os
import sys
import subprocess

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog,
    QFrame, QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap

from setup import (
    config_exists, load_config, save_config,
    _create_state_folders, _find_game_config_folder,
    find_log_path_silent, import_workshop_mods,
)
# Shared look & feel — one stylesheet for the whole app (see gui/theme.py).
from gui.theme import STYLESHEET, FONT_FAMILY, GREEN, GREEN_DIM, AMBER


# ------------------------------------------------------------------ #
#  Header banner artwork (bundled resource)
# ------------------------------------------------------------------ #
from paths import resource_path

_BANNER_PATH = resource_path("AnarchyFM.png")

# Fallback text if the banner image is missing
_FALLBACK_TITLE = "ANARCHY RADIO FM"


# ------------------------------------------------------------------ #
#  Setup Window
# ------------------------------------------------------------------ #
class SetupWindow(QWidget):

    closed = Signal()

    def __init__(self, existing_cfg=None):
        super().__init__()
        self.setWindowTitle("AFM Setup")
        self.setFixedSize(620, 740)
        self.result_cfg = None  # set on success

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(0)

        # --- Banner image (falls back to text) ---
        art_label = QLabel()
        art_label.setAlignment(Qt.AlignCenter)
        art_label.setStyleSheet("background: transparent;")
        banner = QPixmap(_BANNER_PATH) if os.path.isfile(_BANNER_PATH) else QPixmap()
        if not banner.isNull():
            art_label.setPixmap(banner.scaledToWidth(220, Qt.SmoothTransformation))
        else:
            art_label.setText(_FALLBACK_TITLE)
            art_label.setFont(QFont(FONT_FAMILY, 20, QFont.Bold))
            art_label.setStyleSheet(f"color: {GREEN}; background: transparent;")
        root.addWidget(art_label)
        root.addSpacing(6)

        # --- Title ---
        title = QLabel("SHEN:  First time? Let me get you configured, Commander.")
        title.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        title.setStyleSheet(f"color: {GREEN};")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        root.addSpacing(14)
        root.addWidget(self._divider())
        root.addSpacing(14)

        # --- 1. Game Executable ---
        root.addWidget(self._section_label(
            "Step 1 — Game Launcher",
            "Pick your game .exe or mod manager (Alternative Mod Launcher, etc.)."
        ))
        self.exe_field = self._path_row(root, "Browse...", self._browse_exe)
        root.addSpacing(14)

        # --- 2. Music Folder ---
        root.addWidget(self._section_label(
            "Step 2 — Music Library Folder",
            "Where to set up the music folders. Drop your tracks inside them."
        ))
        self.music_field = self._path_row(root, "Browse...", self._browse_music,
                                          extra_btn=("Open", self._open_music_folder))
        root.addSpacing(14)

        # --- 3. Workshop Folder ---
        root.addWidget(self._section_label(
            "Step 3 — Workshop Folder  (optional)",
            "For community music packs.  <Steam>\\steamapps\\workshop\\content\\268500"
        ))
        self.workshop_field = self._path_row(root, "Browse...", self._browse_workshop)
        root.addSpacing(14)

        # --- 4. Game Config Folder ---
        root.addWidget(self._section_label(
            "Step 4 — Game Config Folder",
            "Where XCOM 2 stores user settings. Anarchy Radio FM writes MMS overrides here."
        ))
        self.config_field = self._path_row(root, "Browse...", self._browse_config)
        root.addSpacing(20)

        root.addWidget(self._divider())
        root.addSpacing(16)

        # --- Launch button ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.launch_btn = QPushButton("LAUNCH  AFM")
        self.launch_btn.setObjectName("launchBtn")
        self.launch_btn.setCursor(Qt.PointingHandCursor)
        self.launch_btn.clicked.connect(self._on_launch)
        self.launch_btn.setFixedHeight(42)
        self.launch_btn.setMinimumWidth(200)
        btn_row.addWidget(self.launch_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        root.addStretch()

        # --- Status bar ---
        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {AMBER}; font-size: 11px;")
        self.status.setAlignment(Qt.AlignCenter)
        root.addWidget(self.status)

        # Pre-fill from existing config
        if existing_cfg:
            self.exe_field.setText(existing_cfg.get("game_exe", ""))
            self.music_field.setText(existing_cfg.get("music_folder", ""))
            self.workshop_field.setText(existing_cfg.get("workshop_folder", ""))
            self.config_field.setText(existing_cfg.get("game_config_folder", ""))

        # Auto-detect config folder if not pre-filled
        if not self.config_field.text().strip():
            auto_config = _find_game_config_folder()
            if auto_config:
                self.config_field.setText(auto_config)

    # ------------------------------------------------------------ #
    #  UI Builders
    # ------------------------------------------------------------ #

    def _section_label(self, title_text, desc_text):
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 4)
        lay.setSpacing(2)

        lbl_title = QLabel(title_text)
        lbl_title.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        lbl_title.setStyleSheet(f"color: {GREEN};")
        lay.addWidget(lbl_title)

        lbl_desc = QLabel(desc_text)
        lbl_desc.setFont(QFont(FONT_FAMILY, 10))
        lbl_desc.setStyleSheet(f"color: {GREEN_DIM};")
        lbl_desc.setWordWrap(True)
        lay.addWidget(lbl_desc)

        return container

    def _path_row(self, parent_layout, btn_text, browse_fn, extra_btn=None):
        row = QHBoxLayout()
        row.setSpacing(6)

        field = QLineEdit()
        field.setPlaceholderText("Select a path...")
        field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row.addWidget(field)

        btn = QPushButton(btn_text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedWidth(90)
        btn.clicked.connect(lambda: browse_fn(field))
        row.addWidget(btn)

        if extra_btn:
            label, callback = extra_btn
            eb = QPushButton(label)
            eb.setCursor(Qt.PointingHandCursor)
            eb.setFixedWidth(60)
            eb.clicked.connect(callback)
            row.addWidget(eb)

        parent_layout.addLayout(row)
        return field

    @staticmethod
    def _divider():
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        return line

    # ------------------------------------------------------------ #
    #  Browse Handlers
    # ------------------------------------------------------------ #

    def _browse_exe(self, field):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Game Executable", "",
            "Executables (*.exe);;All Files (*.*)"
        )
        if path:
            field.setText(os.path.normpath(path))

    def _browse_music(self, field):
        path = QFileDialog.getExistingDirectory(self, "Select Music Library Folder")
        if path:
            field.setText(os.path.normpath(path))

    def _browse_workshop(self, field):
        path = QFileDialog.getExistingDirectory(self, "Select Workshop Folder")
        if path:
            field.setText(os.path.normpath(path))

    def _browse_config(self, field):
        path = QFileDialog.getExistingDirectory(self, "Select Game Config Folder")
        if path:
            field.setText(os.path.normpath(path))

    def _open_music_folder(self):
        path = self.music_field.text().strip()
        if path and os.path.isdir(path):
            subprocess.Popen(["explorer", os.path.normpath(path)])
        else:
            self._flash("SHEN:  Pick a music folder first, Commander.")

    # ------------------------------------------------------------ #
    #  Launch / Validate
    # ------------------------------------------------------------ #

    def _on_launch(self):
        game_exe = self.exe_field.text().strip()
        music_folder = self.music_field.text().strip()
        workshop_folder = self.workshop_field.text().strip()
        game_config_folder = self.config_field.text().strip()

        # Validate required fields
        if not game_exe:
            self._flash("SHEN:  I need a game executable, Commander.")
            return
        if not os.path.isfile(game_exe):
            self._flash(f"SHEN:  Can't find that file:  {game_exe}")
            return
        if not music_folder:
            self._flash("SHEN:  I need a music library folder, Commander.")
            return

        # Create music folder if needed
        if not os.path.isdir(music_folder):
            try:
                os.makedirs(music_folder)
            except Exception as e:
                self._flash(f"SHEN:  Couldn't create folder:  {e}")
                return

        # Create state subfolders
        _create_state_folders(music_folder)

        # Validate workshop (optional)
        if workshop_folder and not os.path.isdir(workshop_folder):
            self._flash(f"SHEN:  Workshop folder not found:  {workshop_folder}")
            return

        # Find log path
        log_path = find_log_path_silent()

        # Auto-detect config folder if not provided
        if not game_config_folder:
            game_config_folder = _find_game_config_folder(log_path) or ""
        if not game_config_folder:
            # Fall back to default
            userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
            game_config_folder = os.path.join(
                userprofile, "Documents", "my games",
                "XCOM2 War of the Chosen", "XComGame", "Config"
            )

        # Build config
        cfg = {
            "game_exe": game_exe,
            "music_folder": music_folder,
            "log_path": log_path,
            "game_config_folder": game_config_folder,
            "workshop_folder": workshop_folder,
            "auto_close_with_game": True,
            "default_volume": 0.8,
            "shuffle": True,
            "crossfade_ms": 2500,
        }

        # If log path wasn't auto-detected, prompt
        if not log_path:
            log_path = self._ask_log_path()
            if not log_path:
                return
            cfg["log_path"] = log_path

        save_config(cfg)

        # Import workshop mods
        if workshop_folder:
            import_workshop_mods(cfg)

        self.result_cfg = cfg
        self.close()

    def _ask_log_path(self):
        """Show a dialog to get the log path manually."""
        msg = QMessageBox(self)
        msg.setWindowTitle("XCOM 2 Log File")
        msg.setStyleSheet(STYLESHEET)
        msg.setText(
            "Couldn't auto-detect your XCOM 2 log file.\n\n"
            "The log is created when XCOM 2 launches for the first time.\n"
            "Launch the game once, then click Retry.\n\n"
            "Or click Browse to find it manually:\n"
            "%USERPROFILE%\\Documents\\my games\\"
            "XCOM2 War of the Chosen\\XComGame\\Logs\\Launch.log"
        )
        retry_btn = msg.addButton("Retry Auto-Detect", QMessageBox.AcceptRole)
        browse_btn = msg.addButton("Browse...", QMessageBox.ActionRole)
        skip_btn = msg.addButton("Use Default Path", QMessageBox.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == retry_btn:
            path = find_log_path_silent()
            if path:
                return path
            self._flash("SHEN:  Still not found. Launch XCOM 2 first.")
            return self._ask_log_path()
        elif clicked == browse_btn:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Launch.log", "",
                "Log Files (*.log);;All Files (*.*)"
            )
            if path:
                return os.path.normpath(path)
            return self._ask_log_path()
        else:
            # Use default path even if it doesn't exist yet
            userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
            return os.path.join(
                userprofile, "Documents", "my games",
                "XCOM2 War of the Chosen", "XComGame", "Logs", "Launch.log"
            )

    def _flash(self, msg):
        self.status.setText(msg)

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()


# ------------------------------------------------------------------ #
#  Public API
# ------------------------------------------------------------------ #
def run_setup_gui(existing_cfg=None):
    """Show the setup GUI. Returns config dict or None if cancelled."""
    app = QApplication.instance()
    own_app = False
    if app is None:
        # Set before the QApplication exists so the Web Player's QtWebEngine
        # view (created later in the main window) has shared GL contexts.
        try:
            QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
        except Exception:
            pass
        app = QApplication(sys.argv)
        own_app = True

    window = SetupWindow(existing_cfg)
    window.setStyleSheet(STYLESHEET)
    window.show()

    if own_app:
        app.exec()
    else:
        # A QApplication exists but no loop is running here — block on a
        # local loop until the window closes. (window.destroyed never
        # fires for a merely-closed window, so use our closed signal.)
        from PySide6.QtCore import QEventLoop
        loop = QEventLoop()
        window.closed.connect(loop.quit)
        loop.exec()

    return window.result_cfg


if __name__ == "__main__":
    cfg = run_setup_gui()
    if cfg:
        print(f"Config saved: {cfg}")
    else:
        print("Setup cancelled.")
