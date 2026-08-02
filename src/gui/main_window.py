"""Anarchy Radio FM Main Window — playback controls, state toggles, comms log."""

import os
import subprocess
import time
import threading
import webbrowser

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QTextEdit, QButtonGroup,
    QSizePolicy, QFileDialog, QMessageBox, QInputDialog,
    QSystemTrayIcon, QMenu,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QTextCursor, QIcon, QAction, QPixmap

from audio_engine import XiPodEngine, DEFAULT_RADIO_CHUNK_MIN
from library import RADIO_SOURCE_RADIO, RADIO_SOURCE_STATE, RADIO_SOURCE_BOTH
from log_watcher import Bridge
from setup import discover_addons, save_config, _create_state_folders
from gui.theme import FONT_FAMILY, PRIMARY, PRIMARY_DIM, ACCENT, STYLESHEET
from gui.helpers import make_divider, html_escape, paint_own_background
from gui.log_hooks import log_signal
from gui.options import OptionsDialog
from gui.effects import EffectsDialog
import console
import dialogue
import launcher
import process_utils
import updater
import version

# The Alternative Mod Launcher. Recommended over launching XCOM directly
# because it keeps its own argument list — set -forcelogflush once and it
# stays set, and this app can verify it on every launch rather than hoping.
AML_RELEASES_URL = "https://github.com/X2CommunityCore/xcom2-launcher/releases"

from paths import resource_path

# Where the "Make a Music Pack" button sends people. Building a pack is a
# manual job through the XCOM 2 SDK now — see _on_create_music_mod.
MUSIC_PACK_GUIDE_URL = (
    "https://github.com/emzakit/xcom_anarchyfm/wiki/Making-a-music-pack"
)

# Bundled artwork (frozen-build aware — see paths.py). The banner doubles
# as the window/tray icon — it's square, and Qt scales it down cleanly.
# This is the 512px copy, not the 2048px AnarchyFM.png in the project root:
# it's never drawn wider than ~240px, and the full-size original cost 9.6 MB
# of the build for nothing.
# Tall enough that 13px bold text plus its padding can never clip.
_ACTION_BTN_HEIGHT = 38

_ICON_PATH = resource_path("assets", "banner.png")
_BANNER_PATH = resource_path("assets", "banner.png")


class XiPodWindow(QWidget):

    # Emitted from the update-check worker thread — Qt widgets may only be
    # touched on the GUI thread, so the dialog is opened via this signal.
    _update_found = Signal(object)

    def __init__(self, cfg):
        super().__init__()
        paint_own_background(self)
        self.cfg = cfg
        self.engine = None
        self.bridge = None
        self._auto_close = cfg.get("auto_close_with_game", True)
        self._xcom_was_running = False
        self._game_exit_handled = False
        # Auto-shutdown guards — see _check_xcom for why both exist.
        self._launch_grace_until = 0.0
        self._xcom_gone_polls = 0
        self._options_dialog = None
        self._effects_dialog = None
        self._spotify_dialog = None
        self._addons_dialog = None
        self._update_dialog = None
        self._shutting_down = False
        self._update_found.connect(self._on_update_found)

        self.setWindowTitle("AFM")
        self.setMinimumSize(540, 700)
        self.resize(540, 800)
        if os.path.isfile(_ICON_PATH):
            self.setWindowIcon(QIcon(_ICON_PATH))

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        # --- Header (banner image, falls back to text) ---
        header = QLabel()
        header.setAlignment(Qt.AlignCenter)
        banner = QPixmap(_BANNER_PATH) if os.path.isfile(_BANNER_PATH) else QPixmap()
        if not banner.isNull():
            header.setPixmap(banner.scaledToWidth(240, Qt.SmoothTransformation))
        else:
            header.setText("Anarchy Radio FM")
            header.setFont(QFont(FONT_FAMILY, 18, QFont.Bold))
            header.setStyleSheet(f"color: {PRIMARY};")
        root.addWidget(header)

        subtitle = QLabel("Local & Spotify soundtracks for XCOM 2")
        subtitle.setFont(QFont(FONT_FAMILY, 10))
        subtitle.setStyleSheet(f"color: {PRIMARY_DIM};")
        subtitle.setAlignment(Qt.AlignCenter)
        root.addWidget(subtitle)
        root.addWidget(make_divider())

        # --- Panel Buttons ---
        # Six buttons, 3x2. Exactly two full rows, which leaves row 2 free
        # for the -forcelogflush strip below without anything sharing a cell.
        # 'Make a Pack' moved into the Music Addons window — it's a
        # once-in-a-while authoring job, not a per-session control.
        panel_grid = QGridLayout()
        panel_grid.setSpacing(10)
        panel_grid.setContentsMargins(0, 4, 0, 4)

        for i, (label, handler) in enumerate([
            ("Options",       self._on_options),
            ("Effects",       self._on_effects),
            ("Music Folder",  self._on_open_music_folder),
            ("Spotify",       self._on_spotify),
            ("Music Addons",  self._on_addons),
            ("Check Updates", self._on_check_updates),
        ]):
            btn = QPushButton(label)
            btn.setObjectName("panelBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(handler)
            panel_grid.addWidget(btn, i // 3, i % 3)

        # --- -forcelogflush status, its own strip, always on screen -------- #
        # Sits above Radio Mode because it outranks it: without the flag, XCOM
        # buffers its log so hard that "a cinematic started" can arrive 27
        # seconds late, and the music talks straight over the film. It's the
        # one setup step that silently ruins the thing this app exists to do,
        # so its state is stated permanently rather than mentioned once during
        # setup and never again.
        flush_row = QHBoxLayout()
        flush_row.setSpacing(6)

        self._flush_lbl = QLabel(f"Checking {launcher.FLAG}...")
        self._flush_lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self._flush_lbl.setWordWrap(True)
        flush_row.addWidget(self._flush_lbl, 1)

        self._flush_fix_btn = QPushButton("Fix it")
        self._flush_fix_btn.setCursor(Qt.PointingHandCursor)
        self._flush_fix_btn.setFixedWidth(90)
        self._flush_fix_btn.setVisible(False)
        self._flush_fix_btn.clicked.connect(self._on_fix_forcelogflush)
        flush_row.addWidget(self._flush_fix_btn)

        # A second line under the status, for whichever action fits: launching
        # the game ourselves (which adds the flag), or getting hold of AML.
        self._launch_btn = QPushButton("▶  Launch Game")
        self._launch_btn.setObjectName("panelBtn")
        self._launch_btn.setCursor(Qt.PointingHandCursor)
        self._launch_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._launch_btn.setMinimumHeight(_ACTION_BTN_HEIGHT)
        self._launch_btn.setToolTip(
            "Starts XCOM 2.\n\n"
            "When it's XCOM's own exe, -forcelogflush is added automatically.")
        self._launch_btn.clicked.connect(self._on_launch_game)

        # Short label: the full name doesn't fit beside Launch Game at the
        # default window width, and it clipped rather than eliding.
        self._aml_btn = QPushButton("Get Mod Launcher")
        self._aml_btn.setObjectName("panelBtn")
        self._aml_btn.setCursor(Qt.PointingHandCursor)
        self._aml_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._aml_btn.setMinimumHeight(_ACTION_BTN_HEIGHT)
        self._aml_btn.setToolTip(
            "Opens the Alternative Mod Launcher's releases page.\n\n"
            "It's the best way to run a modded XCOM 2: it keeps its own\n"
            "argument list, so -forcelogflush can be set once and stays set,\n"
            "and this app can check it for you afterwards.")
        self._aml_btn.clicked.connect(self._on_get_aml)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self._launch_btn)
        action_row.addWidget(self._aml_btn)

        flush_box = QVBoxLayout()
        flush_box.setSpacing(8)
        flush_box.setContentsMargins(0, 6, 0, 6)
        flush_box.addLayout(flush_row)
        flush_box.addLayout(action_row)

        self._flush_frame = QWidget()
        self._flush_frame.setLayout(flush_box)
        # Row 3, NOT row 2. Seven panel buttons at (i//3, i%3) put "Check
        # Updates" at (2, 0), so a full-width widget on row 2 lands on top of
        # it — two widgets fighting over the same cell, drawn over each other,
        # with clicks going wherever Qt feels like. Directly above Radio Mode
        # either way.
        panel_grid.addWidget(self._flush_frame, 2, 0, 1, 3)
        # Fill it in now, not when the engine finishes starting — the
        # window paints long before that, and an empty label with a
        # border is just a mystery box.
        self._refresh_flush_status()

        # Radio Mode — the fun one. Avenger ONLY: long-form radio content is
        # downtime atmosphere, and it actively hurts everywhere else. Off by
        # default and not persisted; it's a mood you switch on for a session,
        # not a setting.
        self._radio_btn = QPushButton("Radio Mode (Off)")
        self._radio_btn.setObjectName("panelBtn")
        self._radio_btn.setCheckable(True)
        self._radio_btn.setCursor(Qt.PointingHandCursor)
        self._radio_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._radio_btn.setToolTip(
            "AVENGER ONLY — tune the Avenger to a station, with a random\n"
            "start on each track, as if you'd caught a broadcast part-way\n"
            "through. Every other screen is left completely alone.\n\n"
            "Leaves the per-state Radio Source checkboxes in Effects\n"
            "untouched; turn this off and they apply again."
        )
        self._radio_btn.toggled.connect(self._on_radio_mode)
        # Full width on its own row, directly above the Radio Source buttons —
        # the two read as one grouped control that way.
        panel_grid.addWidget(self._radio_btn, 3, 0, 1, 3)

        root.addLayout(panel_grid)

        # --- Radio Mode source (which folder the Avenger draws from) ---
        source_row = QHBoxLayout()
        source_row.setSpacing(4)
        src_lbl = QLabel("Radio Source:")
        src_lbl.setFont(QFont(FONT_FAMILY, 10))
        src_lbl.setStyleSheet(f"color: {PRIMARY_DIM};")
        source_row.addWidget(src_lbl)

        self._radio_source_group = QButtonGroup(self)
        self._radio_source_group.setExclusive(True)
        for key, label, tip in [
            (RADIO_SOURCE_RADIO, "Radio Only",
             "Play only from STATE_RESISTANCE_RADIO.\n"
             "Falls back to STATE_AVENGER if that folder is empty."),
            (RADIO_SOURCE_STATE, "Avenger Only",
             "Play only from STATE_AVENGER — your normal Avenger tracks,\n"
             "but with Radio Mode's random start points."),
            (RADIO_SOURCE_BOTH, "Mix Both",
             "Pool STATE_RESISTANCE_RADIO and STATE_AVENGER together.\n"
             "When a track finishes, the next one can come from either."),
        ]:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(26)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setToolTip(tip)
            b.setProperty("radioSource", key)
            if key == RADIO_SOURCE_RADIO:
                b.setChecked(True)
            self._radio_source_group.addButton(b)
            source_row.addWidget(b)
        self._radio_source_group.buttonClicked.connect(self._on_radio_source)
        self._set_source_buttons_enabled(False)

        root.addLayout(source_row)
        root.addWidget(make_divider())

        # --- Now Playing ---
        self.state_label = QLabel("Waiting for XCOM...")
        self.state_label.setFont(QFont(FONT_FAMILY, 10))
        self.state_label.setStyleSheet(f"color: {PRIMARY_DIM};")
        root.addWidget(self.state_label)

        self.track_label = QLabel("")
        self.track_label.setFont(QFont(FONT_FAMILY, 13, QFont.Bold))
        self.track_label.setStyleSheet(f"color: {ACCENT};")
        self.track_label.setWordWrap(True)
        root.addWidget(self.track_label)
        root.addSpacing(4)

        # --- Transport Controls ---
        transport = QHBoxLayout()
        transport.setSpacing(8)

        self.prev_btn = QPushButton("<<")
        self.prev_btn.setFixedWidth(50)
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.clicked.connect(self._on_prev)
        transport.addWidget(self.prev_btn)

        self.play_btn = QPushButton("||")
        self.play_btn.setObjectName("playBtn")
        self.play_btn.setFixedWidth(60)
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.clicked.connect(self._on_play_pause)
        transport.addWidget(self.play_btn)

        self.next_btn = QPushButton(">>")
        self.next_btn.setFixedWidth(50)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.clicked.connect(self._on_next)
        transport.addWidget(self.next_btn)

        transport.addSpacing(16)

        vol_lbl = QLabel("VOL")
        vol_lbl.setFont(QFont(FONT_FAMILY, 10))
        vol_lbl.setStyleSheet(f"color: {PRIMARY_DIM};")
        transport.addWidget(vol_lbl)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(cfg.get("default_volume", 0.8) * 100))
        self.vol_slider.valueChanged.connect(self._on_volume)
        transport.addWidget(self.vol_slider)

        self.vol_pct = QLabel(f"{self.vol_slider.value()}%")
        self.vol_pct.setFont(QFont(FONT_FAMILY, 10))
        self.vol_pct.setStyleSheet(f"color: {PRIMARY_DIM};")
        self.vol_pct.setFixedWidth(40)
        transport.addWidget(self.vol_pct)

        root.addLayout(transport)
        root.addWidget(make_divider())

        # --- State Toggles ---
        toggle_header = QLabel("State Toggles  (takes effect on next game launch)")
        toggle_header.setFont(QFont(FONT_FAMILY, 10))
        toggle_header.setStyleSheet(f"color: {PRIMARY_DIM};")
        root.addWidget(toggle_header)

        toggle_grid = QHBoxLayout()
        toggle_grid.setSpacing(4)
        self._toggle_btns = {}

        for key, label, tip in [
            ("shell_menu",  "Shell",   "Toggle Anarchy Radio FM music for the main menu.\nWhen OFF, MMS plays its own shell music."),
            ("avenger",     "Avenger", "Toggle Anarchy Radio FM music for the Avenger base.\nWhen OFF, MMS plays its own Avenger music."),
            ("geoscape",    "Geo",     "Toggle Anarchy Radio FM music for the Geoscape.\nWhen OFF, MMS plays its own Geoscape music."),
            ("battle",      "Battle",  "Toggle Anarchy Radio FM music for tactical missions.\nCovers both explore and combat phases."),
            ("squadselect", "Squad",   "Toggle Anarchy Radio FM music for squad loadout.\nWhen OFF, MMS plays its own squad select music."),
            ("victory",     "Victory", "Toggle Anarchy Radio FM victory stinger after missions.\nWhen OFF, MMS plays its own victory music."),
            ("defeat",      "Defeat",  "Toggle Anarchy Radio FM defeat stinger after missions.\nWhen OFF, MMS plays its own defeat music."),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked, k=key: self._on_toggle(k, checked))
            toggle_grid.addWidget(btn)
            self._toggle_btns[key] = btn

        root.addLayout(toggle_grid)
        root.addWidget(make_divider())

        # --- Log View ---
        log_header_row = QHBoxLayout()
        log_lbl = QLabel("COMMS LOG")
        log_lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        log_lbl.setStyleSheet(f"color: {PRIMARY_DIM};")
        log_header_row.addWidget(log_lbl)
        log_header_row.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(22)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(lambda: self.log_view.clear())
        log_header_row.addWidget(clear_btn)
        root.addLayout(log_header_row)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont(FONT_FAMILY, 11))
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.log_view)

        # --- Signals + Timers ---
        log_signal.message.connect(self._append_log)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_ui)
        self._refresh_timer.start(1000)

        # Always runs, even with auto-close off: _check_xcom pauses playback
        # when the game exits regardless, and only the shutdown half of it
        # depends on auto_close_with_game.
        self._xcom_timer = QTimer(self)
        self._xcom_timer.timeout.connect(self._check_xcom)
        self._xcom_timer.start(3000)

        # --- System Tray ---
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            icon = QIcon(_ICON_PATH) if os.path.isfile(_ICON_PATH) else self.windowIcon()
            self.tray = QSystemTrayIcon(icon, self)
            self.tray.setToolTip("Anarchy Radio FM")
            menu = QMenu()
            show_action = QAction("Show Anarchy Radio FM", menu)
            show_action.triggered.connect(self._restore_from_tray)
            menu.addAction(show_action)
            hide_action = QAction("Hide to Tray", menu)
            hide_action.triggered.connect(self.hide)
            menu.addAction(hide_action)
            menu.addSeparator()
            quit_action = QAction("Exit Anarchy Radio FM", menu)
            quit_action.triggered.connect(self._shutdown)
            menu.addAction(quit_action)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self._on_tray_activated)
            self.tray.show()

    def _restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # left click
            if self.isVisible():
                self.hide()
            else:
                self._restore_from_tray()

    # ------------------------------------------------------------ #
    #  Engine Lifecycle
    # ------------------------------------------------------------ #

    def start_engine(self):
        cfg = self.cfg
        music_path = cfg.get("music_folder", "")
        log_path = cfg.get("log_path", "")
        game_config_folder = cfg.get("game_config_folder", "")
        default_vol = float(cfg.get("default_volume", 0.8))
        shuffle = cfg.get("shuffle", True)
        crossfade_ms = int(cfg.get("crossfade_ms", 2500))

        if not music_path:
            console.error("No music folder configured. Open Options to set one.")
            return

        if not os.path.exists(music_path):
            try:
                os.makedirs(music_path)
            except Exception as e:
                console.error(f"Couldn't create music folder: {e}")
                return
        _create_state_folders(music_path)

        if not log_path:
            console.error("No log path configured. Open Options to set one.")
            return

        if not os.path.exists(log_path):
            console.warn(f"Log file not found yet: {log_path}")
            console.shen("I'll keep an eye out. XCOM will create it when it launches.")

        console.init_file_log(music_path)

        dialogue.say("boot.calibrating")
        self.engine = XiPodEngine()
        self.engine.load_library(
            music_path, log_path,
            game_config_folder=game_config_folder,
            shuffle=shuffle,
            addons=discover_addons(cfg),
            workshop_folder=cfg.get("workshop_folder", ""),
            mod_config_folders=cfg.get("mod_config_folder", ""),
            game_exe=cfg.get("game_exe", ""),
        )
        self.engine.set_volume(default_vol)
        self.engine.set_crossfade(crossfade_ms)
        self.engine.set_radio_chunk_minutes(
            cfg.get("radio_chunk_minutes", DEFAULT_RADIO_CHUNK_MIN))

        # Spotify remote control (experimental) — controller reads its own
        # config from xipod_config.json; inert unless the user enables it.
        try:
            from spotify import SpotifyController
            from setup import CONFIG_PATH
            cache_path = os.path.join(os.path.dirname(CONFIG_PATH), ".spotify_cache.json")
            self.engine.spotify = SpotifyController(CONFIG_PATH, cache_path)
        except Exception as e:
            console.warn(f"Spotify controller unavailable: {e}")

        for key, btn in self._toggle_btns.items():
            btn.setChecked(self.engine.settings.toggles.get(key, False))

        # Checked every launch. The flag gets removed by launcher updates, by
        # someone tidying their arguments, or by following another guide — and
        # when it goes, music silently starts talking over cinematics again.
        launcher.warn_if_flag_missing(cfg.get("game_exe", ""))
        self._refresh_flush_status()

        self._restore_radio_state()
        self._offer_old_install_cleanup()
        self._start_update_check()

        dialogue.say("boot.patching_in")
        self.bridge = Bridge(log_path, self.engine,
                             debug_flush=cfg.get("debug_log_flush", False))
        self.bridge.start()

        # Deliberately does NOT launch the game. Starting XCOM was a side
        # effect of opening a music player, which is presumptuous at the best
        # of times — and actively harmful when the configured exe is XCOM's
        # own, because launching that directly makes the process flicker in and
        # out, which the watcher below then read as "the game has been played
        # and closed" and shut the whole app down a few seconds after start.
        # It looked exactly like a crash.
        #
        # The Launch Game button does it now, when asked.
        if process_utils.is_game_running(default=False):
            dialogue.say("boot.game_already_running")
        else:
            dialogue.say("boot.waiting_for_launch")

        console.divider()
        dialogue.say("boot.online")
        console.divider()

    # How long after launching the game we refuse to believe it has "exited".
    # XCOM can take a while to appear, and launching its exe directly makes it
    # flicker in and out first.
    LAUNCH_GRACE_SECONDS = 90

    def _launch_game(self):
        self._launch_grace_until = time.monotonic() + self.LAUNCH_GRACE_SECONDS
        self._xcom_gone_polls = 0
        process_utils.launch_game(self.cfg)

    # ------------------------------------------------------------ #
    #  Panel Buttons
    # ------------------------------------------------------------ #

    def _on_options(self):
        if self._options_dialog and self._options_dialog.isVisible():
            self._options_dialog.raise_()
            self._options_dialog.activateWindow()
            return
        self._options_dialog = OptionsDialog(self.cfg, engine=self.engine)
        self._options_dialog.setStyleSheet(STYLESHEET)
        self._options_dialog.closed.connect(lambda: setattr(self, '_options_dialog', None))
        self._options_dialog.show()

    def _on_effects(self):
        if self._effects_dialog and self._effects_dialog.isVisible():
            self._effects_dialog.raise_()
            self._effects_dialog.activateWindow()
            return
        if not self.engine:
            console.warn("Engine not running yet. Effects will be available after startup.")
            return
        self._effects_dialog = EffectsDialog(self.engine)
        self._effects_dialog.setStyleSheet(STYLESHEET)
        self._effects_dialog.closed.connect(lambda: setattr(self, '_effects_dialog', None))
        self._effects_dialog.show()

    def _set_source_buttons_enabled(self, enabled):
        for b in self._radio_source_group.buttons():
            b.setEnabled(enabled)

    def _on_radio_mode(self, checked):
        self._radio_btn.setText(f"Radio Mode ({'On' if checked else 'Off'})")
        if not self.engine:
            # Engine still starting — put the button back so the label never
            # claims a mode the engine isn't actually in.
            if checked:
                console.warn("Engine not running yet. Radio Mode will be available after startup.")
                self._radio_btn.setChecked(False)
            return
        self._set_source_buttons_enabled(checked)
        self.engine.set_radio_override(checked)
        self._persist_radio_state()

    def _on_radio_source(self, button):
        if not self.engine:
            return
        self.engine.set_radio_source(button.property("radioSource"))
        self._persist_radio_state()

    def _persist_radio_state(self):
        """Remember the Radio Mode switch and source between sessions."""
        self.cfg["radio_mode"] = bool(self._radio_btn.isChecked())
        checked = self._radio_source_group.checkedButton()
        if checked is not None:
            self.cfg["radio_source"] = checked.property("radioSource")
        save_config(self.cfg)

    def _restore_radio_state(self):
        """Put the Radio Mode controls back where they were left.

        Runs after the engine exists — the toggle handler refuses to engage
        without one, so restoring earlier would silently snap back to Off.
        """
        source = self.cfg.get("radio_source", RADIO_SOURCE_RADIO)
        for b in self._radio_source_group.buttons():
            if b.property("radioSource") == source:
                b.blockSignals(True)
                b.setChecked(True)
                b.blockSignals(False)
                break
        self.engine.set_radio_source(source)

        was_on = bool(self.cfg.get("radio_mode", False))
        self._set_source_buttons_enabled(was_on)
        if was_on:
            self._radio_btn.setChecked(True)   # fires _on_radio_mode
            console.shen("Radio Mode restored from your last session.")

    # ------------------------------------------------------------ #
    #  Updates
    # ------------------------------------------------------------ #

    def _refresh_flush_status(self):
        """Keep the -forcelogflush strip honest. Three states, always shown.

        Always visible on purpose, including when everything is fine. "It's
        detected" and "nobody ever checked" look identical if the good case is
        silent, and that ambiguity is precisely what makes this setting so
        maddening to diagnose from the outside.
        """
        exe = self.cfg.get("game_exe", "")
        try:
            info = launcher.status(exe) if exe else {"is_aml": False}
        except Exception as e:
            console.debug(f"Flag status check failed: {e}")
            info = {"is_aml": False}

        if info["is_aml"] and info["has_flag"]:
            self._flush_lbl.setText(f"✔  {launcher.FLAG} detected")
            self._flush_lbl.setStyleSheet(
                f"color: {PRIMARY}; padding: 6px; "
                f"border: 1px solid {PRIMARY_DIM}; border-radius: 3px;")
            self._flush_fix_btn.setVisible(False)
            self._flush_fix_btn.setToolTip("")
        elif info["is_aml"]:
            self._flush_lbl.setText(
                f"✖  {launcher.FLAG} MISSING — music will play over cinematics")
            self._flush_lbl.setStyleSheet(
                "color: #ff5f56; padding: 6px; "
                "border: 1px solid #ff5f56; border-radius: 3px;")
            self._flush_fix_btn.setVisible(True)
            self._flush_fix_btn.setToolTip(
                "Adds it to your Alternative Mod Launcher arguments.\n"
                "Backs up settings.json first, and changes nothing else.")
        elif launcher.is_game_exe(exe):
            # We launch this one ourselves and add the flag on the way, so
            # starting the game from the button below is genuinely covered.
            self._flush_lbl.setText(
                f"✔  {launcher.FLAG} added when you Launch Game here")
            self._flush_lbl.setStyleSheet(
                f"color: {PRIMARY}; padding: 6px; "
                f"border: 1px solid {PRIMARY_DIM}; border-radius: 3px;")
            self._flush_fix_btn.setVisible(False)
            self._flush_frame.setToolTip(
                "Starting the game from Steam or a desktop icon instead? Then "
                f"you need {launcher.FLAG} set there too.\n"
                "The Alternative Mod Launcher handles this properly — see "
                "Options.")
        else:
            # No launcher we can read, so we genuinely don't know — and saying
            # so is better than a reassuring tick we haven't earned.
            self._flush_lbl.setText(
                f"?  {launcher.FLAG} — can't check this launcher, set it "
                "yourself")
            self._flush_lbl.setStyleSheet(
                f"color: {PRIMARY_DIM}; padding: 6px; "
                f"border: 1px solid {PRIMARY_DIM}; border-radius: 3px;")
            self._flush_fix_btn.setVisible(False)

    def _on_launch_game(self):
        """Start the game on demand — and, for XCOM's own exe, with the flag.

        A button as well as the automatic launch, because launching from here
        is the one route where we control the command line. Anyone who starts
        the game from Steam instead is on their own for -forcelogflush, which
        is exactly why AML gets recommended next to it.
        """
        self._launch_game()

    def _on_get_aml(self):
        """Point people at the Alternative Mod Launcher.

        Recommended rather than merely supported: it holds its own argument
        list, so the flag is set once and stays set, and this app can then
        verify it on every launch instead of hoping.
        """
        console.shen("Opening the Alternative Mod Launcher releases page — "
                     "grab the latest .zip and unpack it anywhere.")
        webbrowser.open(AML_RELEASES_URL)

    def _on_fix_forcelogflush(self):
        """Add the flag from the main window, with the same confirmation and
        the same backup as setup does."""
        exe = self.cfg.get("game_exe", "")
        info = launcher.status(exe)
        if not info["is_aml"] or info["has_flag"]:
            self._refresh_flush_status()
            return

        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setWindowTitle("Add -forcelogflush?")
        box.setStyleSheet(STYLESHEET)
        box.setText(f"Add {launcher.FLAG} to the Alternative Mod Launcher?")
        box.setInformativeText(
            "It goes on the end of your argument list. Nothing already there "
            "is changed, and settings.json is backed up first.\n\n"
            f"Now:\n  {' '.join(info['args']) or '(none)'}\n\n"
            f"After:\n  {' '.join(info['args'] + [launcher.FLAG]).strip()}")
        yes = box.addButton("Add it", QMessageBox.AcceptRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not yes:
            return

        ok, message, saved = launcher.add_forcelogflush(exe)
        (console.shen if ok else console.warn)(message)
        if ok and saved:
            console.faint(f"(backup: {saved})")
        self._refresh_flush_status()

    def _offer_old_install_cleanup(self):
        """Mention any kept previous version, and how to go back to it.

        Reported, never prompted. The backup exists so reverting is always
        possible, which means it has to still be there when someone reaches
        for it — a dialog asking to delete it on every launch would defeat the
        entire point of keeping it.
        """
        try:
            kept = updater.describe_backups()
        except Exception as e:
            console.debug(f"Backup check failed: {e}")
            return
        if not kept:
            return
        console.shen(
            f"Previous version kept: {kept}. It's in a _previous_v folder "
            "next to the app, with a note inside on how to go back to it. "
            "Delete that folder any time you want the space.")

    def _on_check_updates(self):
        """Check on demand. Says something either way, unlike the quiet
        startup check — a button that appears to do nothing is worse than no
        button."""
        console.shen(f"Checking for updates (you have {version.__version__})...")

        def worker():
            try:
                release = updater.check()
            except Exception as e:
                console.warn(f"Couldn't reach GitHub: {e}")
                return
            if not release:
                console.warn("Couldn't read the release list. Try again shortly.")
                return
            if not release.is_newer():
                console.shen(f"You're running the latest ({version.__version__}). Nothing to do.")
                return
            self._update_found.emit(release)

        threading.Thread(target=worker, daemon=True,
                         name="AFMUpdateCheckManual").start()

    def _start_update_check(self):
        """Ask GitHub about newer releases, off-thread.

        Opt-out via config, and entirely best-effort: a failed check must never
        get between the user and their music, so everything here swallows
        errors and simply does nothing.
        """
        if not self.cfg.get("check_for_updates", True):
            return

        def worker():
            try:
                release = updater.check()
            except Exception:
                return
            if not release or not release.is_newer():
                return
            # Deliberately NOT checked against a persisted "skipped" version
            # any more. That key was written on every close of the update
            # window — including the close that happens as the app quits to
            # install — so installing an update permanently suppressed it, and
            # a failed swap left the app hiding the very release it needed.
            # Anyone carrying that value gets it cleared here.
            if self.cfg.pop("skipped_update", None) is not None:
                save_config(self.cfg)
            self._update_found.emit(release)

        threading.Thread(target=worker, daemon=True, name="AFMUpdateCheck").start()

    def _on_update_found(self, release):
        console.shen(f"Update available: {release.version} "
                     f"(you have {version.__version__}).")
        if self._update_dialog and self._update_dialog.isVisible():
            return
        from gui.update_dialog import UpdateDialog
        self._update_dialog = UpdateDialog(release, on_skip=self._remember_update_choice)
        self._update_dialog.setStyleSheet(STYLESHEET)
        self._update_dialog.setWindowIcon(self.windowIcon())
        self._update_dialog.closed.connect(lambda: setattr(self, '_update_dialog', None))
        self._update_dialog.show()

    def _remember_update_choice(self, release_version, auto_check):
        """Honour the auto-check opt-out. Only that.

        This used to also record the release as skipped forever. "Later" now
        means later: the offer comes back next launch, which is what someone
        clicking a button labelled Later expects.
        """
        self.cfg["check_for_updates"] = bool(auto_check)
        save_config(self.cfg)

    def _on_addons(self):
        if self._addons_dialog and self._addons_dialog.isVisible():
            self._addons_dialog.raise_()
            self._addons_dialog.activateWindow()
            return
        if not self.engine:
            console.warn("Engine not running yet. Music Addons will be available after startup.")
            return
        from gui.addons_dialog import AddonsDialog
        from setup import CONFIG_PATH
        self._addons_dialog = AddonsDialog(self.engine, CONFIG_PATH)
        self._addons_dialog.setStyleSheet(STYLESHEET)
        self._addons_dialog.setWindowIcon(self.windowIcon())
        self._addons_dialog.closed.connect(lambda: setattr(self, '_addons_dialog', None))
        self._addons_dialog.show()

    def _on_spotify(self):
        if self._spotify_dialog and self._spotify_dialog.isVisible():
            self._spotify_dialog.raise_()
            self._spotify_dialog.activateWindow()
            return
        if not self.engine or not self.engine.spotify:
            console.warn("Spotify controller not ready yet. Try again after startup.")
            return
        from gui.spotify_dialog import SpotifyDialog
        self._spotify_dialog = SpotifyDialog(self.engine.spotify)
        self._spotify_dialog.setStyleSheet(STYLESHEET)
        self._spotify_dialog.setWindowIcon(self.windowIcon())
        self._spotify_dialog.closed.connect(lambda: setattr(self, '_spotify_dialog', None))
        self._spotify_dialog.show()

    def _on_open_music_folder(self):
        path = self.cfg.get("music_folder", "")
        if path and os.path.isdir(path):
            subprocess.Popen(["explorer", os.path.normpath(path)])
        else:
            console.warn("Music folder not found. Set it in Options first.")

    def _on_create_music_mod(self):
        """Open the guide rather than stamping a mod project out.

        This used to scaffold a complete, ready-to-publish ModBuddy project in
        one click. Two reasons it doesn't any more: the scaffolding was flaky,
        and a button that packages someone's mp3s for redistribution is a very
        different thing from a page explaining how to do it yourself. Making
        the packs is still entirely possible — it's just a deliberate act by
        the person doing it, with their own SDK and their own judgement about
        what they're allowed to upload.
        """
        console.shen("Opening the music pack guide in your browser.")
        webbrowser.open(MUSIC_PACK_GUIDE_URL)

    # ------------------------------------------------------------ #
    #  Transport + Toggles
    # ------------------------------------------------------------ #

    def _on_play_pause(self):
        if not self.engine:
            return
        # In Spotify mode the local stream is idle; toggle Spotify instead.
        if self.engine.is_spotify_active():
            if self.engine.spotify_is_paused():
                self.engine.play()
            else:
                self.engine.pause()
            return
        if self.engine.playback.is_playing:
            self.engine.pause()
        else:
            self.engine.play()

    def _on_next(self):
        if self.engine:
            self.engine.next_track()

    def _on_prev(self):
        if self.engine:
            self.engine.prev_track()

    def _on_volume(self, val):
        self.vol_pct.setText(f"{val}%")
        if self.engine:
            self.engine.set_volume(val / 100.0)

    def _on_toggle(self, key, checked):
        if self.engine:
            self.engine.set_toggle(key, checked)

    # ------------------------------------------------------------ #
    #  UI Updates
    # ------------------------------------------------------------ #

    def _refresh_ui(self):
        if not self.engine:
            return

        spotify_active = self.engine.is_spotify_active()
        if spotify_active:
            self.play_btn.setText(">" if self.engine.spotify_is_paused() else "||")
            self.track_label.setText("♫ Spotify")
        else:
            self.play_btn.setText("||" if self.engine.playback.is_playing else ">")
            track_name = self.engine.get_now_playing()
            self.track_label.setText(os.path.splitext(track_name)[0] if track_name else "")

        state = self.engine.current_top
        if state:
            nice = state.replace("state_", "").replace("_", " ").title()
            if spotify_active:
                self.state_label.setText(f"State: {nice}  (Spotify)")
            elif self.engine._silent_override:
                self.state_label.setText(f"State: {nice}  (MMS active)")
            else:
                self.state_label.setText(f"State: {nice}")
        else:
            self.state_label.setText("Waiting for XCOM...")

    def _append_log(self, text, color):
        self.log_view.moveCursor(QTextCursor.End)
        self.log_view.insertHtml(
            f'<span style="color:{color};">{html_escape(text)}</span><br>'
        )
        self.log_view.moveCursor(QTextCursor.End)
        if self.log_view.document().blockCount() > 500:
            cursor = self.log_view.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, 100)
            cursor.removeSelectedText()

    def _check_xcom(self):
        """Watch the game process. Two separate jobs:

        1. Pause playback the moment XCOM itself exits. The app deliberately
           outlives the game while a launcher (AML) is still open, so you can
           relaunch without restarting it — but it used to keep playing to an
           empty desktop for as long as the launcher stayed up. It doesn't now.
        2. Shut down once BOTH the game and the launcher are gone — and only
           when auto_close_with_game is on.

        The pause is not gated on auto_close: that setting is about whether
        the app quits, not about serenading a desktop with no game on it.
        """
        watched = process_utils.watched_names(self.cfg.get("game_exe", ""))
        running = process_utils.running_processes(watched)
        if running is None:
            return  # tasklist hiccup — never act on "unknown"

        if process_utils.GAME_PROCESS in running:
            self._xcom_was_running = True
            self._game_exit_handled = False   # armed again for the next exit
            self._xcom_gone_polls = 0
            return

        if not self._xcom_was_running:
            return  # game hasn't been seen yet — nothing to react to

        # Launching XCOM's own exe directly starts a process that appears for
        # a moment and then hands off (it wants to come up through Steam). The
        # watcher used to see that flicker as "the game has been played and
        # closed" and shut the whole app down about six seconds after start —
        # which looked exactly like a crash, because nothing said otherwise.
        #
        # So: a grace period after WE launched it, and the game has to be
        # missing for two consecutive polls before it counts as gone.
        if time.monotonic() < self._launch_grace_until:
            console.debug("Game not up yet — still inside the launch grace "
                          "period, not treating this as an exit.")
            return

        self._xcom_gone_polls += 1
        if self._xcom_gone_polls < 2:
            return  # one miss is a hiccup, not a shutdown

        # XCOM has gone. Silence the music once (the timer keeps firing, and
        # re-pausing every 3s would stomp a manual play).
        if not self._game_exit_handled:
            self._game_exit_handled = True
            if self.engine:
                self.engine.pause()
            dialogue.say("game.closed_pausing")

        if self._auto_close and not running:
            console.divider()
            dialogue.say("game.signed_off")
            console.divider()
            self._shutdown()
        # else: launcher still open (or auto-close off) — standby for relaunch

    def _shutdown(self):
        if self._shutting_down:
            return
        self._shutting_down = True
        if self._spotify_dialog:
            self._spotify_dialog.close()
            self._spotify_dialog = None
        if self._addons_dialog:
            self._addons_dialog.close()
            self._addons_dialog = None
        if self.tray:
            self.tray.hide()
        if self.bridge:
            self.bridge.stop()
        if self.engine:
            self.engine.shutdown()
        console.shen("Anarchy Radio FM offline. Shen out.")
        QApplication.instance().quit()

    def closeEvent(self, event):
        self._shutdown()
        event.accept()
