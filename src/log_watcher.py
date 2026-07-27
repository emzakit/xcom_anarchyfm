"""Anarchy Radio FM Log Watcher — monitors XCOM 2 log file for commands."""

import json
import time
import os
import threading
import console
import process_utils


# Cinematic durations and transition list — loaded from xipod_defaults.json
# at startup. If the file is missing, these empty dicts mean cinematics are
# ignored (not ideal, but the game still functions).
_CINEMATIC_DURATIONS = {}       # name (lowercase) → duration (seconds)
_TRANSITION_CINEMATICS = set()  # names (lowercase) — no resume after these

# Path to xipod_defaults.json (lives next to xipod_config.json in project root)
from paths import resource_path

_DEFAULTS_PATH = resource_path("xipod_defaults.json")


def load_cinematic_defaults():
    """Load cinematic durations and transition list from xipod_defaults.json."""
    global _CINEMATIC_DURATIONS, _TRANSITION_CINEMATICS

    if not os.path.exists(_DEFAULTS_PATH):
        console.warn(f"xipod_defaults.json not found — cinematic detection disabled.")
        return

    try:
        with open(_DEFAULTS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        console.warn(f"Failed to read xipod_defaults.json: {e}")
        return

    raw = data.get("cinematics", {})
    _CINEMATIC_DURATIONS = {k.lower(): v for k, v in raw.items() if isinstance(v, int) and v > 0}

    transitions = data.get("transition_cinematics", {})
    # Support both dict format {"CIN_Name": true} and list format ["CIN_Name"]
    if isinstance(transitions, dict):
        _TRANSITION_CINEMATICS = {k.lower() for k in transitions if not k.startswith("_")}
    else:
        _TRANSITION_CINEMATICS = {s.lower() for s in transitions}

    console.debug(f"Loaded {len(_CINEMATIC_DURATIONS)} cinematics, {len(_TRANSITION_CINEMATICS)} transitions from defaults")


class Bridge:
    def __init__(self, log_path, audio_engine):
        self.log_path = log_path
        self.audio_engine = audio_engine
        self.last_position = 0
        self.is_running = False
        self.thread = None

        # Load cinematic durations from xipod_defaults.json
        load_cinematic_defaults()

        # Cinematic lock — blocks all play/state triggers while a
        # cinematic is running. Cleared by "Movie Finished Event"
        # (player skip or natural end) or by the safety timer.
        self._cinematic_lock_until = 0.0   # time.time() deadline
        self._cinematic_lock_set_at = 0.0  # when the lock was engaged
        self._cinematic_safety_timer = None # threading.Timer backup
        self._active_cinematic = None      # name of current cinematic
        # Minimum time a lock must be held before "Movie Finished" can
        # clear it. Stale/buffered events arrive at ~0.0s (same log batch
        # as Movie Started) and are discarded. Real player skips need at
        # least 2s of reaction time, so this threshold is safe.
        self._CINEMATIC_MIN_LOCK = 2.0

        self._dispatch = {
            "VOLUME":         self._cmd_volume,
            "TOGGLE":         self._cmd_toggle,
            "STATEVOL":       self._cmd_statevol,
            "STATERADIO":     self._cmd_stateradio,
            "STATEREVERB":    self._cmd_statereverb,
            "STATELOOP":      self._cmd_stateloop,
            "STATERANDOMSTART": self._cmd_staterandomstart,
            "FXPARAM":        self._cmd_fxparam,
            "PRESET":         self._cmd_preset,
            "SAVEPRESET":     self._cmd_save_preset,
            "CLEARPRESET":    self._cmd_clear_preset,
            "RESCAN":         self._cmd_rescan,
            "PLAY_ID":        self._cmd_play_id,
            "PLAY":           self._cmd_play,
            "PAUSE":          self._cmd_pause,
            "NEXT":           self._cmd_next,
            "PREV":           self._cmd_prev,
        }

    def start(self):
        log_dir = os.path.dirname(self.log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        if not os.path.exists(self.log_path):
            with open(self.log_path, 'w') as f:
                f.write("Anarchy Radio FM Log Initialized.\n")

        # Jump to end so we don't replay old commands, but first
        # scan for the most recent STATE_ so we know what the game
        # is currently doing (handles Anarchy Radio FM starting after the game).
        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(0, os.SEEK_END)
                self.last_position = f.tell()
        except Exception as e:
            console.warn(f"Initial log position: {e}")

        self._recover_last_state()

        self.is_running = True
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()
        return self

    def _recover_last_state(self):
        """Scan the existing log for the most recent XIPOD: STATE_ command.
        Only recovers if the game is currently running — stale log entries
        from a previous session should NOT trigger playback on fresh launch."""
        if not os.path.exists(self.log_path):
            return
        if not self._is_game_running():
            console.debug("Game not running — skipping state recovery from stale log.")
            return
        try:
            last_state = None
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if "XIPOD: STATE_" in line:
                        last_state = line.strip()
            if last_state:
                console.signal(f"Recovering last state from log: {last_state}")
                self._process_command(last_state)
        except Exception as e:
            console.warn(f"State recovery failed: {e}")

    @staticmethod
    def _is_game_running():
        """Quick check if XCOM 2 is currently running."""
        return process_utils.is_game_running()

    def _watch_loop(self):
        while self.is_running:
            time.sleep(0.15)  # Fast poll — cinematics need sub-200ms reaction

            if not os.path.exists(self.log_path):
                continue

            try:
                current_size = os.path.getsize(self.log_path)

                if current_size < self.last_position:
                    self.last_position = 0

                if current_size > self.last_position:
                    with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(self.last_position)
                        new_lines = f.readlines()
                        self.last_position = f.tell()

                        for line in new_lines:
                            try:
                                self._process_line(line.strip())
                            except Exception as e:
                                console.warn(f"Signal error: {e}")
            except PermissionError:
                pass
            except Exception as e:
                console.warn(f"Comms relay hiccup: {e}")

    def _process_line(self, line):
        """Route a log line to the appropriate handler."""
        # Anarchy Radio FM commands (from mod UC code)
        if "XIPOD:" in line:
            self._process_command(line)
            return

        # Cutscene detection (native game log lines)
        if "Movie Started Event: CIN_" in line:
            self._handle_cutscene_start(line)
        elif "Movie Finished Event: CIN_" in line:
            self._handle_cutscene_end(line)

        # Kismet concealment broken — civilians spotting XCOM fires this
        # native log line instead of the event system our UC hooks into.
        elif "Kismet: << XCOM : Concealment Broken >>" in line:
            if self._is_cinematic_locked():
                console.debug(f"Cinematic lock active — suppressing Kismet combat switch")
            else:
                console.signal("Kismet concealment break detected")
                self.audio_engine.switch_state("state_mission_combat")

        # MMS (Music Modding System) state transitions — MMS is the actual
        # sound manager, so we listen to its log output for tactical and
        # strategy music events instead of rolling our own detection.
        elif "Music Modding System - Transition to explore!" in line:
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS explore transition")
            else:
                console.signal("MMS: Transition to explore")
                self.audio_engine.switch_state("state_mission_explore")

        elif "Music Modding System - Transition to Combat!" in line:
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS combat transition")
            else:
                console.signal("MMS: Transition to combat")
                self.audio_engine.switch_state("state_mission_combat")

        elif "Music Modding System - Starting Ambience" in line:
            # First tactical music trigger — mission just started, explore mode
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS ambience start")
            else:
                console.signal("MMS: Mission ambience started (explore)")
                self.audio_engine.switch_state("state_mission_explore")

        elif "Music Modding System - PlayBaseViewMusic" in line:
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS avenger music")
            else:
                console.signal("MMS: Avenger music")
                self.audio_engine.switch_state("state_avenger")

        elif "Music Modding System - PlayGeoscapeMusic" in line:
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS geoscape music")
            else:
                console.signal("MMS: Geoscape music")
                self.audio_engine.switch_state("state_geoscape")

        elif "Music Modding System - PlaySquadSelectMusic" in line:
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS squad select music")
            else:
                console.signal("MMS: Squad select music")
                self.audio_engine.switch_state("state_squadselect")

        elif "Music Modding System - PlayAfterActionMusic" in line:
            if not self._is_cinematic_locked():
                console.signal("MMS: After-action music")
                # Victory/defeat is determined by the audio engine based on
                # the STATE_ command from our post-mission listener

        # Early shell detection — "Initializing Engine Completed" fires
        # ~1s after XComShell is created, after async loads are done.
        # By this point UC's StopMenuMusic() has had a real target to
        # kill. Using "Game class is 'XComShell'" was too early — native
        # music loaded async and started AFTER StopMenuMusic was called.
        # Only fires once on initial launch; subsequent shell visits go
        # through UC's STATE_SHELL_MENU via OnInit/OnReceiveFocus.
        elif "Initializing Engine Completed" in line:
            if self._is_cinematic_locked():
                console.debug(f"Cinematic lock active — suppressing early shell switch")
            else:
                console.signal("Engine init complete — starting shell music")
                self.audio_engine.switch_state("state_shell_menu")

        # FUNNY WORKAROUND: The game logs "Failed to find state State_UINarrative"
        # right before avenger cinematics (welcome engineering, welcome labs, etc.).
        # This warning reliably precedes the Movie Started event, so we use it as
        # a preemptive pause trigger. It's a failed state lookup being used as a
        # cinematic detector — hilariously, it works better than actual movie polling.
        elif "Failed to find state State_UINarrative" in line:
            console.signal("Avenger cinematic incoming (State_UINarrative)")
            self.audio_engine.pause(fade=False)

    def _is_cinematic_locked(self):
        """True if a cinematic is actively playing and music must stay silent."""
        return time.time() < self._cinematic_lock_until

    def _clear_cinematic_lock(self):
        """Clear the cinematic lock and cancel any pending safety timer."""
        self._cinematic_lock_until = 0.0
        self._active_cinematic = None
        if self._cinematic_safety_timer:
            self._cinematic_safety_timer.cancel()
            self._cinematic_safety_timer = None

    def _process_command(self, line):
        cmd = line.split("XIPOD:")[1].strip()
        parts = cmd.upper().split()

        if not parts:
            return

        # State commands — all states are simple now (no substate/context)
        if parts[0].startswith("STATE_"):
            console.signal(f"Field report: {cmd}")

            # STATE_TACTICAL is just a screen marker — MMS handles the
            # actual explore/combat sub-states via its own log lines.
            if parts[0] == "STATE_TACTICAL":
                return

            # A STATE_ command from our screen listeners means the game has
            # moved on to a new screen. If a cinematic lock is active, this
            # is proof the cinematic is over (player skipped or it ended).
            # Clear the lock and let the state switch proceed.
            if self._is_cinematic_locked():
                elapsed = time.time() - self._cinematic_lock_set_at
                if elapsed < self._CINEMATIC_MIN_LOCK:
                    # Too fast — arrived in same batch as Movie Started
                    console.debug(f"Cinematic lock too fresh ({elapsed:.1f}s) — suppressing {cmd}")
                    return
                console.signal(f"STATE_ during cinematic lock ({self._active_cinematic}) — cinematic over, clearing lock")
                self._clear_cinematic_lock()
            self.audio_engine.switch_state(parts[0].lower())
        elif parts[0] == "PLAY":
            # Block PLAY during cinematics too
            if self._is_cinematic_locked():
                console.debug(f"Cinematic lock active ({self._active_cinematic}) — suppressing PLAY")
                return
            console.signal(f"Command received: {cmd}")
            self._dispatch[parts[0]](parts)
        elif parts[0] in self._dispatch:
            console.signal(f"Command received: {cmd}")
            self._dispatch[parts[0]](parts)

    # ------------------------------------------------------------------ #
    #  Cutscene Handling
    # ------------------------------------------------------------------ #

    def _extract_cin_name(self, line, prefix):
        """Extract the cinematic name from a Movie Started/Finished log line."""
        try:
            raw = line.split(prefix)[1].split(",")[0].strip()
            # Strip file extension if present (.bk2, etc.)
            if "." in raw:
                raw = raw.rsplit(".", 1)[0]
            return raw
        except (IndexError, AttributeError):
            return ""

    def _handle_cutscene_start(self, line):
        cin_name = self._extract_cin_name(line, "Movie Started Event: ")
        key = cin_name.lower() if cin_name else ""
        if not key or key not in _CINEMATIC_DURATIONS:
            return

        duration = _CINEMATIC_DURATIONS[key]
        lock_time = duration  # exact Bink duration — safety timer is our primary resume

        console.signal(f"Cinematic detected: {cin_name} ({duration}s) — locking music for {lock_time}s")

        # Hard stop, no fade — cinematics need instant silence
        self.audio_engine.pause(fade=False)

        # Engage cinematic lock — blocks PLAY/STATE_ until cleared
        self._active_cinematic = cin_name
        self._cinematic_lock_set_at = time.time()
        self._cinematic_lock_until = self._cinematic_lock_set_at + lock_time

        # Safety timer: if "Movie Finished Event" never arrives (log
        # buffering, crash, etc.), auto-resume after the full duration.
        if self._cinematic_safety_timer:
            self._cinematic_safety_timer.cancel()
        self._cinematic_safety_timer = threading.Timer(
            lock_time, self._safety_cinematic_resume, args=[cin_name]
        )
        self._cinematic_safety_timer.daemon = True
        self._cinematic_safety_timer.start()

    def _handle_cutscene_end(self, line):
        cin_name = self._extract_cin_name(line, "Movie Finished Event: ")
        key = cin_name.lower() if cin_name else ""
        if not key or key not in _CINEMATIC_DURATIONS:
            return

        # Reject stale "Movie Finished" that arrived in the same log batch
        # as "Movie Started". The game buffers both events together — if we
        # honored this immediately (or after a short delay), it would kill
        # the lock while the movie is still playing. Drop it entirely and
        # rely on the REAL "Movie Finished" event (which arrives when the
        # player skips or the video actually ends) or the safety timer.
        elapsed = time.time() - self._cinematic_lock_set_at
        if elapsed < self._CINEMATIC_MIN_LOCK:
            console.debug(f"Movie Finished for {cin_name} arrived too fast ({elapsed:.1f}s) — DISCARDING (stale buffered event)")
            return

        self._process_cutscene_end(cin_name, key)

    def _process_cutscene_end(self, cin_name, key):
        """Common logic for handling a cinematic ending."""
        console.signal(f"Cinematic ended: {cin_name}")

        # Clear the lock — cinematic is over (natural end or player skip)
        self._clear_cinematic_lock()

        # Hardcoded state transitions after specific cinematics
        if key == "cin_tp_intro":
            console.signal("Post-cinematic transition: switching to squad select")
            self.audio_engine.switch_state("state_squadselect")
            return

        # Transition cinematics: don't resume — the game is switching
        # to a new state and the next STATE_ command will start music.
        if key in _TRANSITION_CINEMATICS:
            console.debug(f"Transition cinematic — waiting for next state")
            return

        # Resume music after a brief delay (lets the game settle)
        console.debug("Scheduling post-cinematic resume in 2s")
        t = threading.Timer(2.0, self._delayed_cinematic_resume, args=[cin_name])
        t.daemon = True
        t.start()

    def _delayed_cinematic_resume(self, cin_name):
        """Resume music after a cinematic ends, unless something else
        has already started playing or another cinematic has started."""
        if self._is_cinematic_locked():
            console.debug(f"Post-cinematic resume for {cin_name} — skipped, new cinematic active")
            return
        if self.audio_engine.playback.is_playing:
            console.debug(f"Post-cinematic resume for {cin_name} — skipped, already playing")
            return
        console.signal(f"Post-cinematic resume — resuming music after {cin_name}")
        self.audio_engine.play()

    def _safety_cinematic_resume(self, cin_name):
        """Backup resume if 'Movie Finished Event' never arrived."""
        if self._active_cinematic and self._active_cinematic.lower() == cin_name.lower():
            console.warn(f"Safety timer: 'Movie Finished' never arrived for {cin_name} — clearing lock")
            self._clear_cinematic_lock()
            if not self.audio_engine.playback.is_playing:
                self.audio_engine.play()

    # ------------------------------------------------------------------ #
    #  Command Handlers
    # ------------------------------------------------------------------ #

    def _cmd_volume(self, parts):
        try:
            vol_percent = int(parts[1])
            vol_float = max(0.0, min(1.0, vol_percent / 100.0))
            self.audio_engine.set_volume(vol_float)
        except (ValueError, IndexError):
            console.warn("Bad volume signal. Ignoring.")

    def _cmd_toggle(self, parts):
        try:
            self.audio_engine.set_toggle(parts[1].lower(), parts[2].upper() == "ON")
        except IndexError:
            console.warn("Bad toggle signal. Ignoring.")

    def _cmd_statevol(self, parts):
        try:
            self.audio_engine.set_state_volume(parts[1].lower(), int(parts[2]))
        except (ValueError, IndexError):
            console.warn("Bad state volume signal. Ignoring.")

    def _cmd_stateradio(self, parts):
        try:
            self.audio_engine.set_radio(parts[1].lower(), parts[2].upper() == "ON")
        except IndexError:
            console.warn("Bad radio signal. Ignoring.")

    def _cmd_statereverb(self, parts):
        try:
            self.audio_engine.set_reverb(parts[1].lower(), parts[2].upper() == "ON")
        except IndexError:
            console.warn("Bad reverb signal. Ignoring.")

    def _cmd_stateloop(self, parts):
        try:
            self.audio_engine.set_loop(parts[1].lower(), parts[2].upper() == "ON")
        except IndexError:
            console.warn("Bad loop signal. Ignoring.")

    def _cmd_staterandomstart(self, parts):
        try:
            self.audio_engine.set_random_start(parts[1].lower(), parts[2].upper() == "ON")
        except IndexError:
            console.warn("Bad random start signal. Ignoring.")

    def _cmd_fxparam(self, parts):
        try:
            self.audio_engine.set_fx_param(parts[1].lower(), int(parts[2]))
        except (ValueError, IndexError):
            console.warn("Bad FX param signal. Ignoring.")

    def _cmd_preset(self, parts):
        # PRESET SHELL_MENU FIELD_RADIO
        try:
            state = parts[1].lower()
            preset = "_".join(parts[2:]).lower()
            self.audio_engine.set_preset(state, preset)
        except IndexError:
            console.warn("Bad preset signal. Ignoring.")

    def _cmd_save_preset(self, parts):
        try:
            slot = int(parts[1])
            self.audio_engine.save_user_preset(slot)
        except (ValueError, IndexError):
            console.warn("Bad save preset signal. Ignoring.")

    def _cmd_clear_preset(self, parts):
        try:
            slot = int(parts[1])
            self.audio_engine.clear_user_preset(slot)
        except (ValueError, IndexError):
            console.warn("Bad clear preset signal. Ignoring.")

    def _cmd_rescan(self, parts):
        self.audio_engine.rescan()

    def _cmd_play_id(self, parts):
        try:
            self.audio_engine.play(track_id=int(parts[1]))
        except (ValueError, IndexError):
            console.warn("Bad track ID signal. Ignoring.")

    def _cmd_play(self, parts):
        self.audio_engine.play()

    def _cmd_pause(self, parts):
        self.audio_engine.pause()

    def _cmd_next(self, parts):
        self.audio_engine.next_track()

    def _cmd_prev(self, parts):
        self.audio_engine.prev_track()

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
        self._clear_cinematic_lock()
