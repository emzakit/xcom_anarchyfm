"""Anarchy Radio FM Setup GUI — Avenger-style config wizard."""

import os
import sys
import subprocess

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog,
    QFrame, QMessageBox, QSizePolicy, QSpinBox, QScrollArea,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap

from setup import (
    config_exists, load_config, save_config,
    _create_state_folders, _find_game_config_folder,
    find_log_path_silent, find_workshop_folder,
    log_folder_candidates, log_path_from_folder,
    default_music_folder, default_addon_test_folder, create_addon_test_folder,
)
import console
import launcher
import mms_packs

# Kept in step with gui/main_window.py, which offers the same link.
AML_RELEASES_URL = "https://github.com/X2CommunityCore/xcom2-launcher/releases"
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

        # Kept so _on_launch can write back onto it rather than building a
        # fresh dict. The wizard asks about six paths; the config holds a good
        # deal more than that — Spotify credentials, the addon enable map,
        # volume and crossfade — and re-running setup on an existing install
        # must not be a way to lose any of it.
        self._existing_cfg = dict(existing_cfg or {})

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

        # --- The one step nobody can skip -------------------------------- #
        # Moved to the very top from the bottom of the form. It's the single
        # most important thing on this window and it was the last thing anyone
        # read, if they read it at all. Without the flag, music talks over
        # every cinematic — which is the loudest, most obvious way this app can
        # appear broken.
        #
        # (It replaced "turn XCOM's Music volume down to 0", the old workaround
        # for the game's soundtrack bleeding through. That's fixed properly
        # now, and muting the game also silences MMS and any music packs, so
        # the old advice actively costs people music.)
        flush_warn = QLabel(
            "⚠   BEFORE YOU PLAY\n\n"
            "XCOM 2 needs  -forcelogflush  in its launch options, or music "
            "plays straight over your cinematics.\n\n"
            "★  Recommended:  use the Alternative Mod Launcher. It keeps its "
            "own argument list, so this gets set once and stays set — and I "
            "can check it for you on every launch.\n\n"
            "Otherwise:  Steam → right-click XCOM 2 → Properties → Launch "
            "Options. Or pick XCOM's own exe below and I'll pass the flag "
            "myself whenever you launch from here."
        )
        flush_warn.setWordWrap(True)
        flush_warn.setFont(QFont(FONT_FAMILY, 10))
        flush_warn.setStyleSheet(
            f"color: {AMBER}; border: 1px solid {AMBER}; "
            "border-radius: 3px; padding: 12px;")
        form.addWidget(flush_warn)
        form.addSpacing(10)

        aml_row = QHBoxLayout()
        aml_row.setSpacing(8)
        get_aml = QPushButton("Get the Alternative Mod Launcher")
        get_aml.setCursor(Qt.PointingHandCursor)
        get_aml.setToolTip(AML_RELEASES_URL)
        get_aml.clicked.connect(self._on_get_aml)
        aml_row.addWidget(get_aml)
        aml_row.addStretch()
        form.addLayout(aml_row)
        form.addSpacing(18)

        # --- 1. Game Executable ---
        form.addWidget(self._section_label(
            "Step 1 — Game Launcher",
            "Pick your game .exe or mod manager (Alternative Mod Launcher, etc.)."
        ))
        self.exe_field = self._path_row(form, "Browse...", self._browse_exe)

        # Offered as a button rather than sprung as a dialog. It edits somebody
        # else's launcher config, and a modal that appears unbidden the moment
        # setup opens is exactly the sort of thing people click through without
        # reading. A button waits to be asked.
        self.flush_btn = QPushButton(f"Add {launcher.FLAG} to AML")
        self.flush_btn.setCursor(Qt.PointingHandCursor)
        self.flush_btn.clicked.connect(self._on_add_forcelogflush)
        self.flush_btn.setVisible(False)
        form.addWidget(self.flush_btn)

        self.flush_note = QLabel("")
        self.flush_note.setWordWrap(True)
        self.flush_note.setFont(QFont(FONT_FAMILY, 9))
        self.flush_note.setStyleSheet(f"color: {PRIMARY_DIM};")
        self.flush_note.setVisible(False)
        form.addWidget(self.flush_note)

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
            "Only if you're building a music pack. Defaults to ModBuddy's "
            "output folder, so a pack is playable the moment it builds."
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

        # The music folder lives next to the app by default, so a first run has
        # nothing to think about. Only pre-filled when empty, so an existing
        # config's choice is never overwritten.
        if not self.music_field.text().strip():
            self.music_field.setText(os.path.normpath(default_music_folder()))

        # What default_addon_test_folder falls back to when it can't find the
        # SDK. Held so autofill can tell its own guess apart from a path the
        # user chose, and only ever replace the former.
        self._addon_test_fallback = os.path.normpath(default_addon_test_folder())

        self._autofill_from_exe()

        # On open as well as on browse. Anyone with an existing config never
        # touches the Browse button, so a browse-only check missed exactly the
        # people most likely to have skipped the flag in the first place.
        self._refresh_flush_button()

    def _autofill_from_exe(self):
        """Fill in every path the game exe lets us work out.

        Ordered by dependency, because these are derived from each other: the
        workshop folder comes from the exe, and the addon test folder comes
        from the steamapps root that either of them reveals.

        Getting that order wrong is what made ModBuddy detection look broken.
        The addon test default used to be computed BEFORE the workshop
        auto-detect, so on a first run it was asked the question while both
        inputs were still blank, failed to find the SDK every time, and settled
        on the folder beside the app.

        Runs again whenever the exe changes, since that's the point at which
        the answers become knowable. Never overwrites anything the user typed.
        """
        exe = self.exe_field.text().strip()

        # Required now, so filling it in beats making the user go hunting.
        if not self.workshop_field.text().strip():
            auto_ws = find_workshop_folder(exe)
            if auto_ws:
                self.workshop_field.setText(os.path.normpath(auto_ws))

        if not self.config_field.text().strip():
            auto_config = _find_game_config_folder()
            if auto_config:
                self.config_field.setText(auto_config)

        # Left BLANK until there's a game exe to derive it from. Without one
        # there is no steamapps root, so the answer would be the folder beside
        # the app — which is not where anyone's SDK builds land, and which
        # looked for all the world like broken detection. An empty box that
        # fills itself in the moment you pick the launcher is honest; a
        # confidently wrong path is not.
        if not exe:
            return

        # Prefers ModBuddy's output folder, so a freshly built pack is testable
        # without copying it anywhere. Replaced only when it's empty or still
        # holding our own fallback — a path the user picked always stands.
        current = self.addon_test_field.text().strip()
        if not current or os.path.normpath(current) == self._addon_test_fallback:
            self.addon_test_field.setText(os.path.normpath(
                default_addon_test_folder(
                    game_exe=exe,
                    workshop_folder=self.workshop_field.text().strip())))

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
            # On a genuine first run this is the moment everything downstream
            # becomes knowable — before it, there's no steamapps root to find
            # the workshop folder or the SDK from.
            self._autofill_from_exe()
            self._refresh_flush_button()

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

    def _browse_addon_test(self, field):
        path = QFileDialog.getExistingDirectory(self, "Select Addon Testing Folder")
        if path:
            field.setText(os.path.normpath(path))

    def _open_music_folder(self):
        path = self.music_field.text().strip()
        if path and os.path.isdir(path):
            subprocess.Popen(["explorer", os.path.normpath(path)])
        else:
            self._flash("SHEN:  Pick a music folder first, Commander.")

    def _refresh_flush_button(self):
        """Show the -forcelogflush button only when it has something to do.

        `-forcelogflush` is the step people skip, and skipping it is why music
        talks over cinematics: the app reads the game's log, and without the
        flag XCOM buffers it so hard that "a cinematic started" can land 27
        seconds late. AML keeps its arguments in a settings.json we can read,
        so nobody needs to edit it by hand.

        Three states, and the button says which: not AML (hidden), already set
        (shown, disabled, so "it checked and you're fine" doesn't look like
        "it never checked"), or missing (offered).
        """
        exe = self.exe_field.text().strip()
        try:
            info = launcher.status(exe) if exe else {"is_aml": False}
        except Exception as e:
            console.debug(f"Launcher check failed: {e}")
            info = {"is_aml": False}

        if info["is_aml"]:
            self.flush_btn.setVisible(True)
            self.flush_note.setVisible(True)
            if info["has_flag"]:
                self.flush_btn.setEnabled(False)
                self.flush_btn.setText(f"{launcher.FLAG} is already set")
                self.flush_note.setText(
                    "Alternative Mod Launcher detected, and it already has the "
                    "flag. Nothing to do here — you're set.")
            else:
                self.flush_btn.setEnabled(True)
                self.flush_btn.setText(f"Add {launcher.FLAG} to AML")
                self.flush_note.setText(
                    "Alternative Mod Launcher detected, and it's MISSING "
                    f"{launcher.FLAG}. This adds it to the end of your argument "
                    "list, changes nothing else, and backs up settings.json "
                    "first. Ignore this if you'd rather do it yourself.")
            return

        if launcher.is_game_exe(exe):
            # Nothing to offer here any more. There's no arguments field to
            # edit and no settings file to patch — but there's also nothing to
            # fix, because the app passes the flag itself when you launch the
            # game from its panel. A note, not a button.
            self.flush_btn.setVisible(False)
            self.flush_note.setVisible(True)
            self.flush_note.setText(
                f"That's XCOM's own exe, so I'll pass {launcher.FLAG} myself "
                "whenever you use the Launch Game button. Starting the game "
                "from Steam or a desktop icon instead? Then set it in Steam's "
                "Launch Options, or use the Alternative Mod Launcher above — "
                "it's the tidiest answer.")
            return

        self.flush_btn.setVisible(False)
        self.flush_note.setVisible(False)

    def _on_add_forcelogflush(self):
        """Confirm, then add the flag. Their launcher, their call — and
        declinable by simply not pressing the button."""
        exe = self.exe_field.text().strip()
        info = launcher.status(exe)
        if not info["is_aml"] or info["has_flag"]:
            self._refresh_flush_button()
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Add -forcelogflush?")
        msg.setStyleSheet(STYLESHEET)
        msg.setText(f"Add {launcher.FLAG} to the Alternative Mod Launcher?")
        msg.setInformativeText(
            "It goes on the end of your argument list. Nothing already in "
            "there is changed or reordered, and settings.json is backed up "
            "next to itself first so you can undo it.\n\n"
            f"Now:\n  {' '.join(info['args']) or '(none)'}\n\n"
            f"After:\n  {' '.join(info['args'] + [launcher.FLAG]).strip()}")
        yes = msg.addButton("Add it", QMessageBox.AcceptRole)
        msg.addButton("Cancel", QMessageBox.RejectRole)
        msg.exec()

        if msg.clickedButton() is not yes:
            self._flash("SHEN:  Left your launcher alone.")
            return

        ok, message, saved = launcher.add_forcelogflush(exe)
        self._flash(("SHEN:  " if ok else "WARN:  ") + message)
        if ok and saved:
            console.shen(f"Launcher backup: {saved}")
        self._refresh_flush_button()

    def _on_get_aml(self):
        """Open AML's releases page. Recommended, not required."""
        import webbrowser
        console.shen("Opening the Alternative Mod Launcher releases page.")
        webbrowser.open(AML_RELEASES_URL)
        self._flash("SHEN:  Grab the latest .zip, unpack it, then point Step 1 "
                    "at XCOM2 Launcher.exe.")

    # ------------------------------------------------------------ #
    #  Launch / Validate
    # ------------------------------------------------------------ #

    def _on_launch(self):
        game_exe = self.exe_field.text().strip()
        music_folder = self.music_field.text().strip()
        workshop_folder = self.workshop_field.text().strip()
        game_config_folder = self.config_field.text().strip()
        addon_test_folder = self.addon_test_field.text().strip()

        if not game_exe:
            self._flash("SHEN:  I need a game executable, Commander.")
            return
        if not os.path.isfile(game_exe):
            self._flash(f"SHEN:  Can't find that file:  {game_exe}")
            return
        if not music_folder:
            self._flash("SHEN:  I need a music library folder, Commander.")
            return

        if not os.path.isdir(music_folder):
            try:
                os.makedirs(music_folder)
            except Exception as e:
                self._flash(f"SHEN:  Couldn't create folder:  {e}")
                return

        _create_state_folders(music_folder)

        # Optional, so an empty box just means "not a pack author" — but if a
        # path is set, make it real and drop the explainer in it.
        if addon_test_folder:
            create_addon_test_folder(addon_test_folder)

        # Workshop is required: it's how we reach the installed mod's own
        # Config folder, which is the only place MMS reads our silencing from.
        # Get this wrong and everything appears to work while the game's music
        # plays straight over the top.
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

        # Answered by the Logs FOLDER existing, not the log file — the folder
        # ships with the game, the file only appears once it has run. Asking
        # only happens when neither is there.
        log_path = find_log_path_silent()
        if not log_path:
            log_path = self._ask_log_path()
            if not log_path:
                return

        if not game_config_folder:
            game_config_folder = _find_game_config_folder(log_path) or ""
        if not game_config_folder and log_path:
            # Same folder as the log, one level up and along: Logs/Launch.log
            # becomes Config. Derived rather than hardcoded under Documents,
            # because OneDrive moves Documents on a great many machines.
            game_config_folder = os.path.join(
                os.path.dirname(os.path.dirname(log_path)), "Config")

        # Written onto the existing config, not in place of it. Everything the
        # wizard didn't ask about — Spotify, the addon enable map, volume,
        # crossfade — belongs to the user and survives a re-run untouched.
        cfg = dict(self._existing_cfg)
        cfg.update({
            "game_exe": game_exe,
            "music_folder": music_folder,
            "log_path": log_path,
            "game_config_folder": game_config_folder,
            "workshop_folder": workshop_folder,
            "addon_test_folder": addon_test_folder,
            "radio_chunk_minutes": int(self.chunk_spin.value()),
        })
        # First run only. setdefault, so a returning user's own numbers stand.
        for key, fallback in (("auto_close_with_game", True),
                              ("default_volume", 0.8),
                              ("shuffle", True),
                              ("crossfade_ms", 2500)):
            cfg.setdefault(key, fallback)

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
        """Last resort when the Logs folder can't be found. Returns a path, or
        "" if the user closed the dialog without choosing.

        Asks for the FOLDER, not Launch.log. The file doesn't exist until the
        game has run once, so a file picker on a fresh install shows an empty
        directory and no way to proceed — which is precisely the situation
        this dialog exists to get someone out of. log_path_from_folder still
        accepts the file itself, for anyone who browses to it out of habit.
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("XCOM 2 Log Folder")
        msg.setStyleSheet(STYLESHEET)
        msg.setText(
            "Couldn't find your XCOM 2 Logs folder.\n\n"
            "It's created when XCOM 2 is installed, and the log inside it "
            "appears the first time the game runs. Launch the game once, then "
            "click Retry.\n\n"
            "Or click Browse to point me at it:\n"
            "%USERPROFILE%\\Documents\\my games\\"
            "XCOM2 War of the Chosen\\XComGame\\Logs"
        )
        retry_btn = msg.addButton("Retry Auto-Detect", QMessageBox.AcceptRole)
        browse_btn = msg.addButton("Browse...", QMessageBox.ActionRole)
        msg.addButton("Use Default Path", QMessageBox.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()

        if clicked == retry_btn:
            path = find_log_path_silent()
            if path:
                return path
            self._flash("SHEN:  Still not there. Launch XCOM 2 once first.")
            return ""

        if clicked == browse_btn:
            folder = QFileDialog.getExistingDirectory(self, "Select the XCOM 2 Logs folder")
            if folder:
                return log_path_from_folder(os.path.normpath(folder))
            return ""

        # The best guess, whether or not it's there yet — the app copes with a
        # log that hasn't appeared, and says so rather than failing.
        candidates = log_folder_candidates()
        return log_path_from_folder(candidates[0]) if candidates else ""

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
