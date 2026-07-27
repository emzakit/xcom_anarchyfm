"""Anarchy Radio FM Main Window — playback controls, state toggles, comms log."""

import os
import subprocess

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QTextEdit,
    QSizePolicy, QFileDialog, QMessageBox,
    QSystemTrayIcon, QMenu,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor, QIcon, QAction, QPixmap

from audio_engine import XiPodEngine
from log_watcher import Bridge
from setup import import_workshop_mods, _create_state_folders
from gui.theme import FONT_FAMILY, GREEN, GREEN_DIM, CYAN, STYLESHEET
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
_ICON_PATH = resource_path("AnarchyFM.png")
_BANNER_PATH = resource_path("AnarchyFM.png")


class XiPodWindow(QWidget):

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.engine = None
        self.bridge = None
        self._auto_close = cfg.get("auto_close_with_game", True)
        self._xcom_was_running = False
        self._options_dialog = None
        self._effects_dialog = None
        self._web_window = None
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
            header.setStyleSheet(f"color: {GREEN};")
        root.addWidget(header)

        subtitle = QLabel("Local & Spotify soundtracks for XCOM 2")
        subtitle.setFont(QFont(FONT_FAMILY, 10))
        subtitle.setStyleSheet(f"color: {GREEN_DIM};")
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

        # Web Player (experimental) — only enabled while on the Avenger.
        # Streaming music (e.g. YouTube) in an embedded browser, for base
        # downtime. Gated to the Avenger state; enabled in _refresh_ui.
        self._web_btn = QPushButton("Web Player")
        self._web_btn.setObjectName("panelBtn")
        self._web_btn.setCursor(Qt.PointingHandCursor)
        self._web_btn.setEnabled(False)
        self._web_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._web_btn.setToolTip(
            "EXPERIMENTAL — open from the Avenger to stream music (e.g. YouTube)\n"
            "in an embedded browser. Available only while you're on the Avenger."
        )
        self._web_btn.clicked.connect(self._on_web_player)
        panel_grid.addWidget(self._web_btn, 1, 2)  # row 2, last column

        root.addLayout(panel_grid)
        root.addWidget(make_divider())

        # --- Now Playing ---
        self.state_label = QLabel("Waiting for XCOM...")
        self.state_label.setFont(QFont(FONT_FAMILY, 10))
        self.state_label.setStyleSheet(f"color: {GREEN_DIM};")
        root.addWidget(self.state_label)

        self.track_label = QLabel("")
        self.track_label.setFont(QFont(FONT_FAMILY, 13, QFont.Bold))
        self.track_label.setStyleSheet(f"color: {CYAN};")
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
        vol_lbl.setStyleSheet(f"color: {GREEN_DIM};")
        transport.addWidget(vol_lbl)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(cfg.get("default_volume", 0.8) * 100))
        self.vol_slider.valueChanged.connect(self._on_volume)
        transport.addWidget(self.vol_slider)

        self.vol_pct = QLabel(f"{self.vol_slider.value()}%")
        self.vol_pct.setFont(QFont(FONT_FAMILY, 10))
        self.vol_pct.setStyleSheet(f"color: {GREEN_DIM};")
        self.vol_pct.setFixedWidth(40)
        transport.addWidget(self.vol_pct)

        root.addLayout(transport)
        root.addWidget(make_divider())

        # --- State Toggles ---
        toggle_header = QLabel("State Toggles  (takes effect on next game launch)")
        toggle_header.setFont(QFont(FONT_FAMILY, 10))
        toggle_header.setStyleSheet(f"color: {GREEN_DIM};")
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
        log_lbl.setStyleSheet(f"color: {GREEN_DIM};")
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

        if self._auto_close:
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

    def _on_web_player(self):
        # Experimental, Avenger-only. The button is disabled off-Avenger,
        # but guard here too in case of a stale click.
        if not self.engine or self.engine.current_top != "state_avenger":
            console.warn("Web Player is an Avenger-only feature. Head to the Avenger first.")
            return
        if self._web_window and self._web_window.isVisible():
            self._web_window.raise_()
            self._web_window.activateWindow()
            return
        try:
            from gui.browser import WebPlayerWindow
        except Exception as e:
            console.warn(f"Web Player needs QtWebEngine (PySide6-Addons): {e}")
            QMessageBox.warning(
                self, "Web Player unavailable",
                "The in-app browser needs QtWebEngine, which ships with "
                "PySide6-Addons.\n\nInstall it with:\n    pip install PySide6-Addons",
            )
            return
        console.shen("Opening Web Player (experimental) — Avenger downtime jukebox.")
        self._web_window = WebPlayerWindow()
        self._web_window.setStyleSheet(STYLESHEET)
        self._web_window.setWindowIcon(self.windowIcon())
        self._web_window.closed.connect(lambda: setattr(self, '_web_window', None))
        self._web_window.show()

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

        # Web Player is an experimental, Avenger-only feature — enable the
        # button only while on the Avenger. An already-open window keeps
        # working regardless (you can keep listening past the Avenger).
        self._web_btn.setEnabled(state == "state_avenger")

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
        """Dual-gate lifecycle: stay alive while EITHER the game or the
        configured launcher (AML) is running, so the user can relaunch
        after a crash without restarting Anarchy Radio FM. Quit when both are gone."""
        watched = process_utils.watched_names(self.cfg.get("game_exe", ""))
        running = process_utils.running_processes(watched)
        if running is None:
            return  # tasklist hiccup — never shut down on "unknown"
        if process_utils.GAME_PROCESS in running:
            self._xcom_was_running = True
        elif self._xcom_was_running and not running:
            console.divider()
            console.shen("XCOM has signed off. Powering down Anarchy Radio FM.")
            console.divider()
            self._shutdown()
        # else: game closed but launcher still open — standby for relaunch

    def _shutdown(self):
        if self._shutting_down:
            return
        self._shutting_down = True
        if self._web_window:
            self._web_window.close()
            self._web_window = None
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
