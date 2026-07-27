"""Anarchy Radio FM Main Window — playback controls, state toggles, comms log."""

import os
import subprocess

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QTextEdit, QButtonGroup,
    QSizePolicy, QFileDialog, QMessageBox,
    QSystemTrayIcon, QMenu,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor, QIcon, QAction, QPixmap

from audio_engine import XiPodEngine
from library import RADIO_SOURCE_RADIO, RADIO_SOURCE_STATE, RADIO_SOURCE_BOTH
from log_watcher import Bridge
from setup import import_workshop_mods, _create_state_folders
from gui.theme import FONT_FAMILY, PRIMARY, PRIMARY_DIM, ACCENT, STYLESHEET
from gui.helpers import make_divider, html_escape
from gui.log_hooks import log_signal
from gui.options import OptionsDialog
from gui.effects import EffectsDialog
from gui.mod_scaffold import scaffold_music_mod
import console
import process_utils

from paths import resource_path

# Bundled artwork (frozen-build aware — see paths.py). The banner doubles
# as the window/tray icon — it's square, and Qt scales it down cleanly.
# This is the 512px copy, not the 2048px AnarchyFM.png in the project root:
# it's never drawn wider than ~240px, and the full-size original cost 9.6 MB
# of the build for nothing.
_ICON_PATH = resource_path("assets", "banner.png")
_BANNER_PATH = resource_path("assets", "banner.png")


class XiPodWindow(QWidget):

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.engine = None
        self.bridge = None
        self._auto_close = cfg.get("auto_close_with_game", True)
        self._xcom_was_running = False
        self._game_exit_handled = False
        self._options_dialog = None
        self._effects_dialog = None
        self._spotify_dialog = None
        self._shutting_down = False

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
        # A 3x2 grid so six buttons fit without clipping at the default width.
        panel_grid = QGridLayout()
        panel_grid.setSpacing(8)

        for i, (label, handler) in enumerate([
            ("Options",       self._on_options),
            ("Effects",       self._on_effects),
            ("Music Folder",  self._on_open_music_folder),
            ("Create Mod",    self._on_create_music_mod),
            ("Spotify",       self._on_spotify),
        ]):
            btn = QPushButton(label)
            btn.setObjectName("panelBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(handler)
            panel_grid.addWidget(btn, i // 3, i % 3)

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
        panel_grid.addWidget(self._radio_btn, 1, 2)  # row 2, last column

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

        if cfg.get("workshop_folder"):
            import_workshop_mods(cfg)

        console.init_file_log(music_path)

        console.shen("Calibrating audio subsystems...")
        self.engine = XiPodEngine()
        self.engine.load_library(
            music_path, log_path,
            game_config_folder=game_config_folder,
            shuffle=shuffle,
        )
        self.engine.set_volume(default_vol)
        self.engine.set_crossfade(crossfade_ms)

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

        console.shen("Patching into XCOM's comms relay...")
        self.bridge = Bridge(log_path, self.engine)
        self.bridge.start()

        if not process_utils.is_game_running(default=True):
            self._launch_game()
        else:
            console.shen("XCOM is already running. Patching in.")

        console.divider()
        console.shen("All systems nominal, Commander. Anarchy Radio FM is online.")
        console.divider()

    def _launch_game(self):
        process_utils.launch_game(self.cfg)

    # ------------------------------------------------------------ #
    #  Panel Buttons
    # ------------------------------------------------------------ #

    def _on_options(self):
        if self._options_dialog and self._options_dialog.isVisible():
            self._options_dialog.raise_()
            self._options_dialog.activateWindow()
            return
        self._options_dialog = OptionsDialog(self.cfg)
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

    def _on_radio_source(self, button):
        if not self.engine:
            return
        self.engine.set_radio_source(button.property("radioSource"))

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
        folder = QFileDialog.getExistingDirectory(
            self, "Choose a folder for your music mod project"
        )
        if not folder:
            return
        if os.listdir(folder):
            reply = QMessageBox.question(
                self, "Folder Not Empty",
                "This folder already has files in it.\n"
                "Create the mod structure here anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        scaffold_music_mod(folder)
        console.shen(f"Music mod scaffolded at: {folder}")
        console.shen("Drop your audio files into the state folders, Commander.")
        subprocess.Popen(["explorer", os.path.normpath(folder)])

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
            return

        if not self._xcom_was_running:
            return  # game hasn't been seen yet — nothing to react to

        # XCOM has gone. Silence the music once (the timer keeps firing, and
        # re-pausing every 3s would stomp a manual play).
        if not self._game_exit_handled:
            self._game_exit_handled = True
            if self.engine:
                self.engine.pause()
            console.shen("XCOM has closed — pausing playback.")

        if self._auto_close and not running:
            console.divider()
            console.shen("XCOM has signed off. Powering down Anarchy Radio FM.")
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
