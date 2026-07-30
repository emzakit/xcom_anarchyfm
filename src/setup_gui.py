"""Anarchy Radio FM Setup GUI — Avenger-style config wizard."""

import os
import sys
import subprocess

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog,
    QFrame, QMessageBox, QSizePolicy, QSpinBox, QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap

from setup import (
    config_exists, load_config, save_config,
    _create_state_folders, _find_game_config_folder,
    find_log_path_silent, find_workshop_folder,
    default_music_folder, default_addon_test_folder, create_addon_test_folder,
)
import mms_packs
# Shared look & feel — one stylesheet for the whole app (see gui/theme.py).
from gui.theme import STYLESHEET, FONT_FAMILY, PRIMARY, PRIMARY_DIM, AMBER
from gui.helpers import paint_own_background


# ------------------------------------------------------------------ #
#  Header banner artwork (bundled resource)
# ------------------------------------------------------------------ #
from paths import resource_path

_BANNER_PATH = resource_path("assets", "banner.png")

# Fallback text if the banner image is missing
_FALLBACK_TITLE = "ANARCHY RADIO FM"


# ------------------------------------------------------------------ #
#  Setup Window
# ------------------------------------------------------------------ #
class SetupWindow(QWidget):

    closed = Signal()

    def __init__(self, existing_cfg=None):
        super().__init__()
        paint_own_background(self)
        self.setWindowTitle("AFM Setup")
        # Not a fixed size. The step descriptions are word-wrapped labels, so
        # their height depends on their width — pin the window shorter than
        # the content wants and the layout has two states it can settle into,
        # flipping between them on any relayout. 900px was also taller than a
        # 1080p screen comfortably allows once the taskbar is there.
        self.setMinimumSize(620, 520)
        self.resize(640, 880)
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
            art_label.setStyleSheet(f"color: {PRIMARY}; background: transparent;")
        root.addWidget(art_label)
        root.addSpacing(6)

        # --- Title ---
        title = QLabel("SHEN:  First time? Let me get you configured, Commander.")
        title.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY};")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        root.addSpacing(14)
        root.addWidget(self._divider())
        root.addSpacing(14)

        # The steps scroll; the Launch button and status stay pinned at the
        # bottom where they can always be reached.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        steps = QWidget()
        form = QVBoxLayout(steps)
        form.setContentsMargins(0, 0, 8, 0)   # room for the scrollbar
        form.setSpacing(0)
        scroll.setWidget(steps)
        root.addWidget(scroll, 1)

        # --- 1. Game Executable ---
        form.addWidget(self._section_label(
            "Step 1 — Game Launcher",
            "Pick your game .exe or mod manager (Alternative Mod Launcher, etc.)."
        ))
        self.exe_field = self._path_row(form, "Browse...", self._browse_exe)
        form.addSpacing(14)

        # --- 2. Music Folder ---
        form.addWidget(self._section_label(
            "Step 2 — Music Library Folder",
            "Where to set up the music folders. Drop your tracks inside them. "
            "Defaults to a 'music' folder next to this app — fine to leave as is."
        ))
        self.music_field = self._path_row(form, "Browse...", self._browse_music,
                                          extra_btn=("Open", self._open_music_folder))
        form.addSpacing(14)

        # --- 3. Workshop Folder ---
        form.addWidget(self._section_label(
            "Step 3 — Workshop Folder",
            "Needed to find the installed mod — without it the game's own music "
            "won't be silenced.  <Steam>\\steamapps\\workshop\\content\\268500"
        ))
        self.workshop_field = self._path_row(form, "Browse...", self._browse_workshop)
        form.addSpacing(14)

        # --- 4. Game Config Folder ---
        form.addWidget(self._section_label(
            "Step 4 — Game Config Folder",
            "Where XCOM 2 stores user settings, shared with the in-game MCM menu."
        ))
        self.config_field = self._path_row(form, "Browse...", self._browse_config)
        form.addSpacing(14)

        # --- 5. Addon Testing Folder ---
        form.addWidget(self._section_label(
            "Step 5 — Addon Testing Folder  (optional)",
            "Only if you're building a music pack. Drop an in-progress pack "
            "here and it plays in-game as though you'd subscribed to it."
        ))
        self.addon_test_field = self._path_row(form, "Browse...",
                                               self._browse_addon_test)
        form.addSpacing(14)

        # --- 5. Radio Mode chunk length ---
        form.addWidget(self._section_label(
            "Step 6 — Radio Mode station length",
            "How long a stretch Radio Mode plays before re-tuning."
        ))
        chunk_row = QHBoxLayout()
        chunk_row.setSpacing(8)
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(0, 120)
        self.chunk_spin.setSuffix(" min")
        self.chunk_spin.setSpecialValueText("No limit (play to the end)")
        self.chunk_spin.setValue(int((existing_cfg or {}).get("radio_chunk_minutes", 10)))
        self.chunk_spin.setFixedWidth(210)
        chunk_row.addWidget(self.chunk_spin)

        why_btn = QPushButton("Why?")
        why_btn.setCursor(Qt.PointingHandCursor)
        why_btn.setFixedWidth(70)
        why_btn.clicked.connect(self._explain_radio_length)
        chunk_row.addWidget(why_btn)
        chunk_row.addStretch()
        form.addLayout(chunk_row)
        form.addSpacing(12)

        # --- Launch option warning ---
        # This replaced "turn XCOM's Music volume down to 0", which was the
        # workaround for the game's soundtrack playing underneath everything.
        # That's fixed properly now, and muting the game also silences MMS and
        # any music packs — so the old advice actively costs people music.
        music_warn = QLabel(
            "One last thing, and it isn't optional: add  -forcelogflush  to "
            "XCOM 2's launch options. In Steam, right-click XCOM 2 → "
            "Properties → Launch Options. Using a mod launcher? Put it in that "
            "launcher's arguments field. Without it, music plays over your "
            "cinematics."
        )
        music_warn.setWordWrap(True)
        music_warn.setFont(QFont(FONT_FAMILY, 10))
        music_warn.setStyleSheet(f"color: {AMBER};")
        form.addWidget(music_warn)
        form.addSpacing(12)
        # Keeps the steps packed at the top of the scroll body.
        form.addStretch()

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
            self.addon_test_field.setText(existing_cfg.get("addon_test_folder", ""))

        # Both of these live next to the app by default, so a first run has
        # nothing to think about: accept the defaults and everything lands in
        # one portable folder. Only pre-filled when empty, so an existing
        # config's choices are never overwritten.
        if not self.music_field.text().strip():
            self.music_field.setText(os.path.normpath(default_music_folder()))
        if not self.addon_test_field.text().strip():
            self.addon_test_field.setText(
                os.path.normpath(default_addon_test_folder()))

        # Auto-detect the workshop folder if not pre-filled. It's required
        # now, so filling it in beats making the user go hunting for it.
        if not self.workshop_field.text().strip():
            auto_ws = find_workshop_folder(self.exe_field.text().strip())
            if auto_ws:
                self.workshop_field.setText(os.path.normpath(auto_ws))

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
        lbl_title.setStyleSheet(f"color: {PRIMARY};")
        lay.addWidget(lbl_title)

        lbl_desc = QLabel(desc_text)
        lbl_desc.setFont(QFont(FONT_FAMILY, 10))
        lbl_desc.setStyleSheet(f"color: {PRIMARY_DIM};")
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

    def _browse_addon_test(self, field):
        path = QFileDialog.getExistingDirectory(self, "Select Addon Testing Folder")
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
        addon_test_folder = self.addon_test_field.text().strip()

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

        # Optional, so an empty box just means "not a pack author" — but if a
        # path is set, make it real and drop the explainer in it.
        if addon_test_folder:
            create_addon_test_folder(addon_test_folder)

        # Validate workshop. Required: it's how we reach the installed mod's
        # own Config folder, which is the only place MMS reads our silencing
        # from. Get this wrong and everything appears to work while the game's
        # music plays straight over the top.
        if not workshop_folder:
            workshop_folder = find_workshop_folder(game_exe)
            if workshop_folder:
                self.workshop_field.setText(os.path.normpath(workshop_folder))

        if not workshop_folder:
            self._flash("SHEN:  I need the Workshop folder — it's how I find the "
                        "installed mod. Without it the game's music won't be silenced.")
            return
        if not os.path.isdir(workshop_folder):
            self._flash(f"SHEN:  Workshop folder not found:  {workshop_folder}")
            return

        # The folder existing isn't the point — reaching our own mod through
        # it is. Warn rather than block: a first-time setup can legitimately
        # run before the mod has finished downloading.
        if not mms_packs.find_own_config_dirs(workshop_folder):
            self._flash("SHEN:  Found the folder, but not the Anarchy Radio FM mod "
                        "inside it. Subscribe to the mod (or set mod_config_folder) "
                        "or the game's music will play over yours.")

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
            "addon_test_folder": addon_test_folder,
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

        # Music addons aren't imported here any more — they're discovered and
        # merged when the engine loads the library. See addons.py.
        self.result_cfg = cfg
        self.close()

    def _explain_radio_length(self):
        """The long version, on demand. It was inline once and dominated the
        whole wizard — most people just want to accept the default."""
        box = QMessageBox(self)
        box.setWindowTitle("Radio Mode station length")
        box.setIcon(QMessageBox.NoIcon)
        box.setText("Why we're asking")
        box.setInformativeText(
            "Radio Mode tunes the Avenger to your STATE_RESISTANCE_RADIO folder "
            "and starts every track at a random point, like catching a broadcast "
            "that was already running.\n\n"
            "People tend to fill that folder with hour-long station rips. Loading "
            "a whole hour costs a few hundred MB of memory and leaves you staring "
            "at silence for ten seconds before the first note.\n\n"
            "So it loads a slice at a time. When the slice ends, it re-tunes to a "
            "fresh random spot — which is what a radio station does anyway.\n\n"
            "10 minutes gets you playing in about two seconds. Set it to 0 to "
            "switch the limit off and play every track through to its end.\n\n"
            "You can change this any time in Options."
        )
        box.setStyleSheet(self.styleSheet())
        box.exec()

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
