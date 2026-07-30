"""Spotify dialog (EXPERIMENTAL) — credentials, account link, per-state playlists.

Lets the user paste their own Spotify app credentials, authorize their
account, and bind a Spotify playlist to each game state. See the Spotify setup
page in the wiki for how to get the credentials. Everything here drives the user's own Spotify
account through their own app registration — at their own risk.
"""

import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QGroupBox, QScrollArea, QSlider,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from gui.theme import FONT_FAMILY, PRIMARY, PRIMARY_DIM, PRIMARY_FAINT, AMBER, ACCENT
from gui.helpers import make_divider, paint_own_background
from spotify import BINDABLE_STATES, DEFAULT_REDIRECT, parse_context_uri
import console


STATE_LABELS = {
    "state_shell_menu":     "Main Menu",
    "state_avenger":        "Avenger",
    "state_geoscape":       "Geoscape",
    "state_squadselect":    "Squad Select",
    "state_mission_explore": "Tactical: Explore",
    "state_mission_combat":  "Tactical: Combat",
    "state_victory":        "Victory",
    "state_defeat":         "Defeat",
}


class SpotifyDialog(QWidget):

    closed = Signal()
    _auth_done = Signal(bool, str)  # (ok, message) from the auth worker thread

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        paint_own_background(self)
        self.sp = controller
        self.setWindowTitle("AFM — Spotify (Experimental)")
        self.setMinimumSize(620, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(6)

        title = QLabel("SPOTIFY  ·  EXPERIMENTAL")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY};")
        root.addWidget(title)

        warn = QLabel(
            "At your own risk. This drives your OWN Spotify account via your OWN "
            "API keys.\n"
            "• Requires Spotify PREMIUM.\n"
            "• The Spotify DESKTOP APP must be open and running (Anarchy Radio FM remote-"
            "controls it — it does not stream audio itself).\n"
            "• Playing starts on whichever device Spotify is active on.\n"
            "See the Spotify setup guide in the wiki for step-by-step key setup:\n"
            "github.com/emzakit/xcom_anarchyfm/wiki/Spotify-setup"
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color: {AMBER}; font-size: 11px;")
        root.addWidget(warn)
        root.addWidget(make_divider())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(8)

        # --- Enable ---
        self.enable_cb = QCheckBox("Enable Spotify mode (states with a playlist "
                                   "below are handed to Spotify)")
        self.enable_cb.setChecked(self.sp.enabled)
        lay.addWidget(self.enable_cb)

        self.shuffle_cb = QCheckBox("Shuffle playlists")
        self.shuffle_cb.setChecked(self.sp.shuffle)
        self.shuffle_cb.setToolTip(
            "Turns Spotify's own shuffle on before starting a playlist.\n\n"
            "Without it, Spotify starts every context from track 1 — so the\n"
            "same state plays the same song every single time."
        )
        lay.addWidget(self.shuffle_cb)

        # --- Startup volume ---
        vol_row = QHBoxLayout()
        vol_lbl = QLabel("Player volume:")
        vol_lbl.setToolTip(
            "Spotify often launches at full volume. Anarchy Radio FM sets this level the\n"
            "first time it starts Spotify playback each session."
        )
        vol_row.addWidget(vol_lbl)
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(self.sp.volume)
        vol_row.addWidget(self.vol_slider, 1)
        self.vol_val = QLabel(f"{self.sp.volume}%")
        self.vol_val.setFixedWidth(44)
        self.vol_slider.valueChanged.connect(
            lambda v: self.vol_val.setText(f"{v}%")
        )
        vol_row.addWidget(self.vol_val)
        lay.addLayout(vol_row)

        # --- Credentials ---
        creds = QGroupBox("Your Spotify App Credentials")
        cg = QGridLayout(creds)
        cg.setSpacing(6)

        cg.addWidget(QLabel("Client ID:"), 0, 0)
        self.client_id = QLineEdit(self.sp.client_id)
        cg.addWidget(self.client_id, 0, 1)

        cg.addWidget(QLabel("Client Secret:"), 1, 0)
        self.client_secret = QLineEdit(self.sp.client_secret)
        self.client_secret.setEchoMode(QLineEdit.Password)
        cg.addWidget(self.client_secret, 1, 1)

        cg.addWidget(QLabel("Redirect URI:"), 2, 0)
        self.redirect = QLineEdit(self.sp.redirect_uri or DEFAULT_REDIRECT)
        self.redirect.setToolTip(
            "Must match EXACTLY a Redirect URI you added in the Spotify "
            "Developer Dashboard.\nDefault: " + DEFAULT_REDIRECT
        )
        cg.addWidget(self.redirect, 2, 1)

        link_row = QHBoxLayout()
        self.link_btn = QPushButton("Link Spotify Account")
        self.link_btn.setCursor(Qt.PointingHandCursor)
        self.link_btn.setStyleSheet(
            f"background-color: {PRIMARY_FAINT}; border: 1px solid {PRIMARY_DIM}; "
            f"font-weight: bold; padding: 6px;"
        )
        self.link_btn.clicked.connect(self._on_link)
        link_row.addWidget(self.link_btn)
        self.link_status = QLabel(self._status_text())
        self.link_status.setStyleSheet(f"color: {ACCENT}; font-size: 11px;")
        link_row.addWidget(self.link_status, 1)
        cg.addLayout(link_row, 3, 0, 1, 2)
        lay.addWidget(creds)

        # --- Per-state playlists ---
        pl = QGroupBox("Playlist per State  (paste a Spotify playlist link or URI)")
        pg = QGridLayout(pl)
        pg.setSpacing(6)
        self.playlist_fields = {}
        for i, state in enumerate(BINDABLE_STATES):
            pg.addWidget(QLabel(STATE_LABELS.get(state, state) + ":"), i, 0)
            field = QLineEdit(self.sp.playlist_for(state))
            field.setPlaceholderText("https://open.spotify.com/playlist/…  (blank = use local files)")
            pg.addWidget(field, i, 1)
            self.playlist_fields[state] = field
        lay.addWidget(pl)

        lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # --- Buttons ---
        root.addWidget(make_divider())
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
        cancel_btn = QPushButton("Close")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {AMBER}; font-size: 11px;")
        self.status.setAlignment(Qt.AlignCenter)
        root.addWidget(self.status)

        self._auth_done.connect(self._on_auth_done)

    # ------------------------------------------------------------------ #

    def _status_text(self):
        if self.sp.is_authorized():
            return "Linked ✓"
        if self.sp.is_configured():
            return "Not linked yet."
        return "Enter credentials, then link."

    def _pull_credentials(self):
        """Copy the credential fields into the controller (without saving)."""
        self.sp.client_id = self.client_id.text().strip()
        self.sp.client_secret = self.client_secret.text().strip()
        self.sp.redirect_uri = self.redirect.text().strip() or DEFAULT_REDIRECT

    def _on_link(self):
        self._pull_credentials()
        if not self.sp.is_configured():
            self.status.setText("Enter your Client ID and Client Secret first.")
            return
        self.sp.save_config()  # persist creds before the browser round-trip
        self.link_btn.setEnabled(False)
        self.link_status.setText("Opening browser… approve access in Spotify.")

        def worker():
            ok, msg = self.sp.authorize()
            self._auth_done.emit(ok, msg)

        threading.Thread(target=worker, daemon=True, name="SpotifyAuth").start()

    def _on_auth_done(self, ok, msg):
        self.link_btn.setEnabled(True)
        self.link_status.setText("Linked ✓" if ok else "Not linked.")
        self.status.setText(msg)
        console.shen(f"Spotify: {msg}") if ok else console.warn(f"Spotify: {msg}")

    def _on_save(self):
        self._pull_credentials()
        self.sp.enabled = self.enable_cb.isChecked()
        self.sp.shuffle = self.shuffle_cb.isChecked()

        # Player volume — store it, and if a state is currently on Spotify,
        # apply it live so the change is audible immediately.
        new_vol = self.vol_slider.value()
        vol_changed = (new_vol != self.sp.volume)
        self.sp.volume = new_vol
        if vol_changed and self.sp.is_active():
            self.sp.set_volume_async(new_vol)

        # Validate + store playlists
        for state, field in self.playlist_fields.items():
            text = field.text().strip()
            try:
                uri = self.sp.set_playlist(state, text)
            except ValueError:
                self.status.setText(
                    f"{STATE_LABELS.get(state, state)}: not a valid Spotify "
                    f"playlist link/URI.")
                return
            if uri:
                field.setText(uri)

        self.sp.save_config()
        if self.sp.enabled and not self.sp.is_active():
            self.status.setText("Saved. Note: enable needs credentials + a linked "
                                "account to take effect.")
        else:
            self.status.setText("Saved.")
        console.shen("Spotify settings saved.")

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
