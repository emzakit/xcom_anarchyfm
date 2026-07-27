"""Spotify remote control (EXPERIMENTAL) — assign a playlist to each game state.

IMPORTANT — what this does and does NOT do:
  * The Spotify Web API does NOT stream audio. It only *remote-controls* an
    already-running Spotify client. So this feature tells your open Spotify
    desktop app which playlist to switch to when the game changes state.
  * Playback control (play/pause/skip, set playlist) is **Spotify Premium
    only**. Free accounts cannot use it.
  * You must have the **Spotify desktop app running** (it's the playback
    device Anarchy Radio FM points at).
  * You supply your OWN API credentials (Client ID/Secret from the Spotify
    Developer Dashboard). You use this at your own risk — it drives your
    account through your own app registration.

No third-party packages: OAuth + API calls use only the standard library.
"""

import base64
import http.server
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

import console

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

# Playback control + reading the active device. Nothing else.
SCOPES = "user-modify-playback-state user-read-playback-state"

DEFAULT_REDIRECT = "http://127.0.0.1:8888/callback"

# Spotify tends to launch at full blast; start states here unless changed.
DEFAULT_VOLUME = 60

# The game states a playlist can be bound to (top-level state strings, as
# emitted by the engine). Explore and combat are kept separate here so you
# can score them differently.
BINDABLE_STATES = [
    "state_shell_menu",
    "state_avenger",
    "state_geoscape",
    "state_squadselect",
    "state_mission_explore",
    "state_mission_combat",
    "state_victory",
    "state_defeat",
]


# ------------------------------------------------------------------ #
#  URI parsing
# ------------------------------------------------------------------ #

def parse_context_uri(text):
    """Normalize a playlist/album/artist reference to a Spotify context URI.

    Accepts:
      - spotify:playlist:37i9dQ...             (URI, returned as-is)
      - https://open.spotify.com/playlist/37i9dQ...?si=...   (share link)
      - a bare playlist id (assumed to be a playlist)
    Returns "" if it can't be parsed. Tracks are not valid contexts.
    """
    if not text:
        return ""
    text = text.strip()

    if text.startswith("spotify:"):
        parts = text.split(":")
        if len(parts) == 3 and parts[1] in ("playlist", "album", "artist") and parts[2]:
            return f"spotify:{parts[1]}:{parts[2]}"
        return ""

    if "open.spotify.com" in text:
        try:
            path = urllib.parse.urlparse(text).path.strip("/").split("/")
            # e.g. ["playlist", "37i9dQ..."] or ["intl-xx", "playlist", "id"]
            if len(path) >= 2:
                kind, pid = path[-2], path[-1]
                if kind in ("playlist", "album", "artist") and pid:
                    return f"spotify:{kind}:{pid}"
        except Exception:
            return ""
        return ""

    # Bare id — assume playlist
    if all(c.isalnum() for c in text):
        return f"spotify:playlist:{text}"
    return ""


# ------------------------------------------------------------------ #
#  OAuth redirect catcher
# ------------------------------------------------------------------ #

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """One-shot handler that captures the ?code=... from the OAuth redirect."""

    server_version = "XiPodSpotifyAuth/1.0"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        error = params.get("error", [None])[0]
        self.server.auth_code = code
        self.server.auth_error = error

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if code:
            msg = "Anarchy Radio FM is now linked to Spotify. You can close this tab."
        else:
            msg = f"Spotify authorization failed: {error or 'no code returned'}."
        self.wfile.write(
            f"<html><body style='font-family:sans-serif;background:#0a0a0a;"
            f"color:#33ff33;text-align:center;padding-top:60px'>"
            f"<h2>{msg}</h2></body></html>".encode("utf-8")
        )

    def log_message(self, *_args):
        pass  # silence the default stderr logging


# ------------------------------------------------------------------ #
#  Controller
# ------------------------------------------------------------------ #

class SpotifyController:
    def __init__(self, config_path, cache_path):
        self._config_path = config_path
        self._cache_path = cache_path

        self.enabled = False
        self.client_id = ""
        self.client_secret = ""
        self.redirect_uri = DEFAULT_REDIRECT
        self.playlists = {}  # state_key -> context uri
        self.volume = DEFAULT_VOLUME  # 0-100, applied on first playback

        self._access_token = None
        self._access_expires_at = 0
        self._refresh_token = None

        self._lock = threading.Lock()          # serializes token refresh
        self._playback_lock = threading.Lock()  # serializes control calls
        # Spotify launches loud; apply the configured volume once per session
        # (on the first playback) so we don't fight manual tweaks afterwards.
        self._volume_applied = False

        self._load_config()
        self._load_tokens()

    # ------------------------------------------------------------------ #
    #  Persistence
    # ------------------------------------------------------------------ #

    def _load_config(self):
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        sp = cfg.get("spotify", {}) or {}
        self.enabled = bool(sp.get("enabled", False))
        self.client_id = sp.get("client_id", "") or ""
        self.client_secret = sp.get("client_secret", "") or ""
        self.redirect_uri = sp.get("redirect_uri") or DEFAULT_REDIRECT
        raw = sp.get("playlists", {}) or {}
        self.playlists = {k.lower(): v for k, v in raw.items() if v}
        try:
            self.volume = max(0, min(100, int(sp.get("volume", DEFAULT_VOLUME))))
        except (TypeError, ValueError):
            self.volume = DEFAULT_VOLUME

    def save_config(self):
        """Write the spotify block back into xipod_config.json, preserving
        everything else in the file."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        cfg["spotify"] = {
            "enabled": self.enabled,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "volume": self.volume,
            "playlists": self.playlists,
        }
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            console.warn(f"Couldn't save Spotify config: {e}")

    def _load_tokens(self):
        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._refresh_token = data.get("refresh_token")
            self._access_token = data.get("access_token")
            self._access_expires_at = data.get("expires_at", 0)
        except Exception:
            pass

    def _save_tokens(self):
        data = {
            "refresh_token": self._refresh_token,
            "access_token": self._access_token,
            "expires_at": self._access_expires_at,
        }
        try:
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            console.warn(f"Couldn't cache Spotify tokens: {e}")

    # ------------------------------------------------------------------ #
    #  Status
    # ------------------------------------------------------------------ #

    def is_configured(self):
        return bool(self.client_id and self.client_secret)

    def is_authorized(self):
        return bool(self._refresh_token)

    def is_active(self):
        """True when the feature is on AND usable (credentials + linked)."""
        return self.enabled and self.is_configured() and self.is_authorized()

    def playlist_for(self, state):
        if not state:
            return ""
        return self.playlists.get(state.lower(), "")

    def set_playlist(self, state, text):
        """Assign/normalize a playlist for a state. Empty text clears it.
        Returns the stored URI, or raises ValueError on a bad reference."""
        state = state.lower()
        if not text or not text.strip():
            self.playlists.pop(state, None)
            return ""
        uri = parse_context_uri(text)
        if not uri:
            raise ValueError("Not a valid Spotify playlist link or URI.")
        self.playlists[state] = uri
        return uri

    # ------------------------------------------------------------------ #
    #  OAuth
    # ------------------------------------------------------------------ #

    def authorize(self, timeout=180):
        """Run the Authorization Code flow. Opens the user's browser, catches
        the redirect on a local server, exchanges the code for tokens.

        BLOCKS until the user approves or `timeout` elapses — call from a
        background thread. Returns (ok: bool, message: str).
        """
        if not self.is_configured():
            return False, "Enter your Client ID and Client Secret first."

        parsed = urllib.parse.urlparse(self.redirect_uri)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8888

        try:
            server = http.server.HTTPServer((host, port), _CallbackHandler)
        except OSError as e:
            return False, f"Couldn't open local port {port} for the redirect: {e}"
        server.auth_code = None
        server.auth_error = None
        server.timeout = 1

        state = base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip("=")
        query = urllib.parse.urlencode({
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": SCOPES,
            "state": state,
            "show_dialog": "false",
        })
        auth_url = f"{AUTH_URL}?{query}"

        console.shen("Opening your browser to authorize Spotify...")
        webbrowser.open(auth_url)

        deadline = time.time() + timeout
        try:
            while time.time() < deadline and server.auth_code is None and server.auth_error is None:
                server.handle_request()
        finally:
            try:
                server.server_close()
            except Exception:
                pass

        if server.auth_error:
            return False, f"Spotify authorization denied: {server.auth_error}"
        if not server.auth_code:
            return False, "Timed out waiting for Spotify authorization."

        return self._exchange_code(server.auth_code)

    def _basic_auth_header(self):
        raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _exchange_code(self, code):
        body = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }).encode("utf-8")
        try:
            status, data = self._token_request(body)
        except Exception as e:
            return False, f"Token exchange failed: {e}"
        if status != 200:
            return False, f"Spotify rejected the token request (HTTP {status})."
        self._store_token_response(data)
        return True, "Spotify linked successfully."

    def _refresh(self):
        """Refresh the access token using the stored refresh token."""
        if not self._refresh_token:
            return False
        body = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }).encode("utf-8")
        try:
            status, data = self._token_request(body)
        except Exception as e:
            console.warn(f"Spotify token refresh failed: {e}")
            return False
        if status != 200:
            console.warn(f"Spotify token refresh rejected (HTTP {status}).")
            return False
        self._store_token_response(data)
        return True

    def _token_request(self, body):
        req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
        req.add_header("Authorization", self._basic_auth_header())
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, {}

    def _store_token_response(self, data):
        self._access_token = data.get("access_token")
        self._access_expires_at = time.time() + int(data.get("expires_in", 3600)) - 30
        # Spotify only returns a new refresh_token sometimes; keep the old one.
        if data.get("refresh_token"):
            self._refresh_token = data["refresh_token"]
        self._save_tokens()

    def _valid_token(self):
        with self._lock:
            if self._access_token and time.time() < self._access_expires_at:
                return self._access_token
            if self._refresh():
                return self._access_token
            return None

    # ------------------------------------------------------------------ #
    #  API calls
    # ------------------------------------------------------------------ #

    def _api(self, method, path, params=None, json_body=None):
        """Authenticated Web API call. Returns (status, data|None).
        Retries once after a forced refresh on 401."""
        token = self._valid_token()
        if not token:
            return 401, None

        url = API_BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(json_body).encode("utf-8") if json_body is not None else None

        def _do(tok):
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Authorization", f"Bearer {tok}")
            if data is not None:
                req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    # Playback-control calls (play/pause/next/volume) return
                    # 204 No Content, or occasionally a whitespace/non-JSON
                    # body. Only parse when it actually looks like JSON —
                    # json.loads on "" or " " throws, which used to crash the
                    # SpotifyPause thread.
                    raw = resp.read().decode("utf-8", errors="replace").strip()
                    parsed = None
                    if raw:
                        try:
                            parsed = json.loads(raw)
                        except ValueError:
                            parsed = None
                    return resp.status, parsed
            except urllib.error.HTTPError as e:
                return e.code, None

        status, result = _do(token)
        if status == 401:
            with self._lock:
                self._access_expires_at = 0
            token = self._valid_token()
            if token:
                status, result = _do(token)
        return status, result

    def active_device_id(self):
        """Return the id of the active device, or the first available one."""
        status, data = self._api("GET", "/me/player/devices")
        if status != 200 or not data:
            return None
        devices = data.get("devices", [])
        if not devices:
            return None
        for d in devices:
            if d.get("is_active"):
                return d.get("id")
        return devices[0].get("id")

    def play_context(self, context_uri):
        """Point Spotify at a playlist/album/artist context and play it.
        Returns (ok, message)."""
        with self._playback_lock:
            device_id = self.active_device_id()
            if not device_id:
                return False, ("No Spotify device found. Open the Spotify desktop "
                               "app and start playing something once, then retry.")
            params = {"device_id": device_id}
            status, _ = self._api("PUT", "/me/player/play", params=params,
                                  json_body={"context_uri": context_uri})
            if status in (200, 202, 204):
                # Tame the launch volume once per session (Spotify often
                # starts at 100%). Best-effort — never fail playback over it.
                if not self._volume_applied:
                    self._volume_applied = True
                    self._set_volume(self.volume, device_id)
                return True, "Playing on Spotify."
            if status == 403:
                return False, ("Spotify refused playback — this requires Spotify "
                               "Premium.")
            if status == 404:
                return False, "No active Spotify device (is the desktop app open?)."
            return False, f"Spotify play failed (HTTP {status})."

    def pause(self):
        with self._playback_lock:
            status, _ = self._api("PUT", "/me/player/pause")
            return status in (200, 202, 204, 404)

    def resume(self):
        with self._playback_lock:
            status, _ = self._api("PUT", "/me/player/play")
            return status in (200, 202, 204)

    def _set_volume(self, percent, device_id=None):
        """Set the Spotify player volume (0-100). Best-effort; ignores errors
        (older devices / free accounts don't support it)."""
        percent = max(0, min(100, int(percent)))
        params = {"volume_percent": percent}
        if device_id:
            params["device_id"] = device_id
        try:
            self._api("PUT", "/me/player/volume", params=params)
        except Exception:
            pass

    def set_volume(self, percent):
        """Public: update the stored volume and apply it right away if we can."""
        self.volume = max(0, min(100, int(percent)))
        with self._playback_lock:
            self._set_volume(self.volume)

    def set_volume_async(self, percent):
        self._spawn(lambda: self.set_volume(percent), "SpotifyVolume")

    def next_track(self):
        with self._playback_lock:
            self._api("POST", "/me/player/next")

    def prev_track(self):
        with self._playback_lock:
            self._api("POST", "/me/player/previous")

    # ------------------------------------------------------------------ #
    #  Async wrappers (network I/O off the caller's thread)
    # ------------------------------------------------------------------ #

    def _spawn(self, fn, name):
        threading.Thread(target=fn, daemon=True, name=name).start()

    def play_context_async(self, context_uri):
        def _run():
            ok, msg = self.play_context(context_uri)
            (console.shen if ok else console.warn)(f"Spotify: {msg}")
        self._spawn(_run, "SpotifyPlay")

    def pause_async(self):
        self._spawn(self.pause, "SpotifyPause")

    def resume_async(self):
        self._spawn(self.resume, "SpotifyResume")

    def next_async(self):
        self._spawn(self.next_track, "SpotifyNext")

    def prev_async(self):
        self._spawn(self.prev_track, "SpotifyPrev")
