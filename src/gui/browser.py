"""In-app Web Player — an embedded Chromium browser for streaming music.

Lets players pull up YouTube / YouTube Music (and stay logged in — cookies
persist between sessions) and play music straight inside XiPod. This is a
convenience panel: it is NOT wired into the state engine. The browser just
plays whatever you point it at, mixing over the game like any other app, so
you'd typically leave the state folders empty (or toggle states off) and DJ
manually here.

Note: QtWebEngine ships WITHOUT Widevine, so DRM-gated services (and some
music videos) won't play here. YouTube / YouTube Music work fine. For Spotify,
use the dedicated per-state Spotify integration instead (see spotify.py).

QtWebEngine is part of PySide6-Addons. If it isn't installed the import here
fails and the caller (main window) shows a friendly message instead.
"""

import os
from urllib.parse import quote

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
)
from PySide6.QtCore import Qt, QUrl, Signal, QStandardPaths
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings, QWebEnginePage

from gui.theme import AMBER


HOME_URL = "https://music.youtube.com"

QUICK_LINKS = [
    ("YouTube",   "https://www.youtube.com"),
    ("YT Music",  "https://music.youtube.com"),
]

# A mainstream desktop Chrome UA — some music sites nag or gate on the default
# "...QtWebEngine..." string. Purely cosmetic; the engine is still Chromium.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _profile_dir():
    """A persistent, user-writable folder for cookies/cache so logins stick.

    Pinned to an explicit "XiPod" folder rather than AppDataLocation (which
    derives from the executable name, e.g. a generic "python" folder).
    """
    base = (
        os.environ.get("APPDATA")
        or QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)
        or os.path.expanduser("~")
    )
    path = os.path.join(base, "XiPod", "web_profile")
    os.makedirs(path, exist_ok=True)
    return path


def _make_profile():
    """Build the shared persistent profile (cookies + disk cache)."""
    profile = QWebEngineProfile("XiPodWeb")  # named -> persistent
    path = _profile_dir()
    profile.setPersistentStoragePath(path)
    profile.setCachePath(path)
    profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
    profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
    profile.setHttpUserAgent(_USER_AGENT)
    s = profile.settings()
    # Let music start without a per-track click — it's a player, after all.
    s.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
    s.setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)
    return profile


class WebPlayerWindow(QWidget):
    """Standalone window: toolbar + address bar + embedded browser."""

    closed = Signal()
    _profile = None  # shared across opens so logins/cache persist

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AFM — Web Player")
        self.setMinimumSize(900, 640)

        if WebPlayerWindow._profile is None:
            WebPlayerWindow._profile = _make_profile()

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # --- Navigation toolbar ---
        nav = QHBoxLayout()
        nav.setSpacing(4)

        self.back_btn = self._nav_button("<", "Back", lambda: self.view.back())
        self.fwd_btn = self._nav_button(">", "Forward", lambda: self.view.forward())
        self.reload_btn = self._nav_button("R", "Reload", lambda: self.view.reload())
        self.home_btn = self._nav_button("Home", "Home", lambda: self.navigate(HOME_URL))
        for b in (self.back_btn, self.fwd_btn, self.reload_btn, self.home_btn):
            nav.addWidget(b)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search YouTube, or type an address…")
        self.url_bar.returnPressed.connect(self._on_url_entered)
        nav.addWidget(self.url_bar, 1)

        go_btn = self._nav_button("Go", "Go", self._on_url_entered)
        nav.addWidget(go_btn)
        root.addLayout(nav)

        # --- Experimental banner ---
        banner = QLabel(
            "EXPERIMENTAL · Avenger-only downtime feature — stream YouTube "
            "music while you potter around the base."
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(f"color: {AMBER}; font-size: 10px;")
        root.addWidget(banner)

        # --- Quick links ---
        quick = QHBoxLayout()
        quick.setSpacing(4)
        for label, url in QUICK_LINKS:
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, u=url: self.navigate(u))
            quick.addWidget(b)
        quick.addStretch()
        root.addLayout(quick)

        # --- The browser ---
        self.view = QWebEngineView()
        self.view.setPage(QWebEnginePage(WebPlayerWindow._profile, self.view))
        self.view.urlChanged.connect(self._on_view_url_changed)
        root.addWidget(self.view, 1)

        self.navigate(HOME_URL)

    # ------------------------------------------------------------------ #

    def _nav_button(self, text, tip, handler):
        b = QPushButton(text)
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedHeight(28)
        b.setMaximumWidth(64)
        b.clicked.connect(lambda: handler())
        return b

    def navigate(self, url):
        self.view.setUrl(QUrl(url))

    def _on_url_entered(self):
        text = self.url_bar.text().strip()
        if not text:
            return
        if "://" in text:
            url = text
        elif "." in text and " " not in text:
            url = "https://" + text
        else:
            # No dot / has spaces -> treat as a YouTube search
            url = "https://www.youtube.com/results?search_query=" + quote(text)
        self.navigate(url)

    def _on_view_url_changed(self, qurl):
        self.url_bar.setText(qurl.toString())
        self.url_bar.setCursorPosition(0)

    def closeEvent(self, event):
        # Stop any playing media so audio doesn't linger after the window closes.
        try:
            self.view.stop()
            self.view.setPage(None)
        except Exception:
            pass
        self.closed.emit()
        event.accept()
