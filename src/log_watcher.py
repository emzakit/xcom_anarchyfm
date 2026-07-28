"""Anarchy Radio FM Log Watcher — monitors XCOM 2 log file for commands."""

import json
import re
import time
import os
import threading
import console
import process_utils


# Every log line carries the engine's own clock. Reading ordering and
# duration off that instead of off when Python happened to notice the line
# matters because the log is buffered and a cinematic logs NOTHING while it
# runs — so a whole cinematic can land in a single read, long after it played.
_ENGINE_TIME_RE = re.compile(r"^\[(\d+\.\d+)\]")

# "Movie Finished Event: CIN_Name, <seconds played>, <full runtime>"
_MOVIE_FINISHED_RE = re.compile(
    r"Movie Finished Event:\s*([^,]+?)\s*,\s*([\d.]+)\s*,\s*([\d.]+)"
)

# How long to wait after a cinematic before resuming. Avenger facility
# flyovers chain back to back with only 2.3–3.8s between one ending and the
# next starting, so a shorter delay just blips the music on between films.
_POST_CINEMATIC_RESUME_DELAY = 4.5

# A single read covering more than this much engine time means the game had
# been holding those lines. Below it, ordinary poll jitter.
_FLUSH_SPAN_WARN = 1.0

# Ceiling on a mod-driven cinematic lock. CINE_OFF normally releases it, but
# if the game crashes mid-film or the watcher actor dies with the map, this
# stops the music being muted for the rest of the session. Longer than the
# longest cinematic in the game (204s) with room to spare.
_UC_CINEMATIC_SAFETY = 300.0

# Name recorded for a lock the mod told us about rather than one we inferred
# from a Movie event. Keeps the two paths distinguishable in the logs.
_UC_CINEMATIC = "mod watcher"


def _engine_time(line):
    """Seconds since engine start, read from the line's own timestamp."""
    m = _ENGINE_TIME_RE.match(line)
    return float(m.group(1)) if m else None


def _normalise_cin(raw):
    """Trim whitespace and any file extension off a cinematic name."""
    raw = raw.strip()
    if "." in raw:
        raw = raw.rsplit(".", 1)[0]
    return raw


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
    def __init__(self, log_path, audio_engine, debug_flush=False):
        self.log_path = log_path
        self.audio_engine = audio_engine
        self.last_position = 0
        self.is_running = False
        self.thread = None

        # Diagnostic for one specific question: does the game's log reach disk
        # promptly, or does it sit in a buffer? It decides whether a cinematic
        # can be caught while it plays or only after it ends. Off by default —
        # see _report_flush.
        self.debug_flush = debug_flush

        # Load cinematic durations from xipod_defaults.json
        load_cinematic_defaults()

        # Cinematic lock — blocks all play/state triggers while a
        # cinematic is running. Cleared by "Movie Finished Event"
        # (player skip or natural end) or by the safety timer.
        self._cinematic_lock_until = 0.0   # time.time() deadline
        self._cinematic_lock_set_at = 0.0  # when the lock was engaged
        self._cinematic_safety_timer = None # threading.Timer backup
        self._active_cinematic = None      # name of current cinematic
        # Last (cinematic key, engine timestamp) we acted on. The engine
        # emits some "Movie Finished" events twice against the same engine
        # timestamp, and the duplicate carries a raw clock reading in the
        # elapsed field rather than a duration — so it can't be filtered on
        # value, only on identity.
        self._last_finished = (None, None)

        # True while the mod's own cinematic watcher says a film is up. It
        # sees a cinematic coming before the script thread blocks, so when it
        # is talking to us its word beats anything we could infer from the
        # game's Movie events — which by then are already late.
        self._uc_cinematic = False

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
            "CINE_ON":        self._cmd_cine_on,
            "CINE_OFF":       self._cmd_cine_off,
            "CINE_WATCH":     self._cmd_cine_watch,
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

                        # Processed as a batch, not line by line: a cinematic
                        # writes nothing to the log while it plays, so its
                        # "Movie Started" and "Movie Finished" routinely reach
                        # us together in one read. Seeing the rest of the batch
                        # is what lets us tell "a cinematic is running now" from
                        # "a cinematic already came and went".
                        batch = [line.strip() for line in new_lines]
                        if self.debug_flush:
                            self._report_flush(batch)
                        for i, line in enumerate(batch):
                            try:
                                self._process_line(line, batch[i + 1:])
                            except Exception as e:
                                console.warn(f"Signal error: {e}")
            except PermissionError:
                pass
            except Exception as e:
                console.warn(f"Comms relay hiccup: {e}")

    def _process_line(self, line, rest_of_batch=()):
        """Route a log line to the appropriate handler.

        `rest_of_batch` is the remainder of the lines that arrived in the same
        read, used to spot a cinematic that has already finished by the time
        we hear about it.
        """
        # Anarchy Radio FM commands (from mod UC code)
        if "XIPOD:" in line:
            self._process_command(line)
            return

        # MMS's own log wording is matched case-insensitively. These used to be
        # exact substring tests and had drifted apart — "Transition to explore!"
        # against "Transition to Combat!" — so a single letter of casing was
        # enough to silently kill combat detection while explore kept working.
        low = line.lower()

        # Cutscene detection (native game log lines). Matched case-insensitively
        # because the game is inconsistent about it — "Cin_Welcome_Labs_Part1"
        # ships alongside "CIN_TP_WelcomeEngineering", and the capitalised-only
        # test silently skipped the lower-case ones.
        if "movie started event: cin" in low:
            self._handle_cutscene_start(line, rest_of_batch)
        elif "movie finished event: cin" in low:
            self._handle_cutscene_end(line)

        # Kismet concealment broken — civilians spotting XCOM fires this
        # native log line instead of the event system our UC hooks into.
        elif "kismet: << xcom : concealment broken >>" in low:
            if self._is_cinematic_locked():
                console.debug(f"Cinematic lock active — suppressing Kismet combat switch")
            else:
                console.signal("Kismet concealment break detected")
                self.audio_engine.switch_state("state_mission_combat")

        # MMS (Music Modding System) state transitions — MMS is the actual
        # sound manager, so we listen to its log output for tactical and
        # strategy music events instead of rolling our own detection.
        # Explore. MMS never actually logs "Transition to explore" — that
        # matcher was wishful thinking and explore only ever worked by
        # accident, via "Starting Ambience" at mission start. "Started
        # Explorer N" is the line MMS really emits, verified against real
        # logs, and it also fires when combat drops back to explore.
        elif ("music modding system - transition to explore" in low
              or "music modding system - started explorer" in low):
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS explore transition")
            else:
                console.signal("MMS: Transition to explore")
                self.audio_engine.switch_state("state_mission_explore")

        # Combat has three independent triggers — the Kismet concealment break
        # above, MMS's transition line, and MMS actually starting the combat
        # track. Any one of them is enough; switch_state() ignores repeats.
        elif ("music modding system - transition to combat" in low
              or "music modding system - started combat" in low):
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS combat transition")
            else:
                console.signal("MMS: Transition to combat")
                self.audio_engine.switch_state("state_mission_combat")

        elif "music modding system - starting ambience" in low:
            # First tactical music trigger — mission just started, explore mode
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS ambience start")
            else:
                console.signal("MMS: Mission ambience started (explore)")
                self.audio_engine.switch_state("state_mission_explore")

        elif "music modding system - playbaseviewmusic" in low:
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS avenger music")
            else:
                console.signal("MMS: Avenger music")
                self.audio_engine.switch_state("state_avenger")

        elif "music modding system - playgeoscapemusic" in low:
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS geoscape music")
            else:
                console.signal("MMS: Geoscape music")
                self.audio_engine.switch_state("state_geoscape")

        elif "music modding system - playsquadselectmusic" in low:
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing MMS squad select music")
            else:
                console.signal("MMS: Squad select music")
                self.audio_engine.switch_state("state_squadselect")

        elif "music modding system - playafteractionmusic" in low:
            if not self._is_cinematic_locked():
                console.signal("MMS: After-action music")
                # Victory/defeat is determined by the audio engine based on
                # the STATE_ command from our post-mission listener

        # Returning to the main menu. The shell map load is the only reliable
        # marker we get for it.
        #
        # The comment below used to claim "subsequent shell visits go through
        # UC's STATE_SHELL_MENU" — they don't. XiPod_UISL_Shell never fires in
        # practice (real logs show a full session with zero STATE_SHELL_MENU
        # lines despite two trips to the menu), so quitting to the main menu
        # produced no state change at all and whatever was playing on the
        # Avenger or in combat just kept going.
        #
        # LoadMap fires on every shell load, launch and return alike. A
        # duplicate at launch is free — switch_state() ignores a state it's
        # already on — so this can safely overlap the init-complete trigger.
        # MMS logs this from its own shell listener every time the shell comes
        # up — boot and return-to-menu alike, twice per session in every log
        # we have. It is the only shell signal we actually receive: our own
        # XiPod_UISL_Shell listens for UIShell, but the screen the game pushes
        # is UIFinalShell, and XCOM 2 matches listeners on the exact class, so
        # STATE_SHELL_MENU has never once appeared in a real log.
        elif "menu music played" in low:
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing shell switch")
            else:
                console.signal("MMS: Shell menu music — back to the main menu")
                self.audio_engine.switch_state("state_shell_menu")

        # Map-load backstop. WOTC boots the XPACK shell, so matching only
        # "XComShell" missed the shell entirely on most installs — real logs
        # show XPACK_Shell_Intro 23 times against XComShell_Tundra 4.
        elif "loadmap: xcomshell" in low or "loadmap: xpack_shell" in low:
            if self._is_cinematic_locked():
                console.debug("Cinematic lock active — suppressing shell map switch")
            else:
                console.signal("Shell map loading — back to the main menu")
                self.audio_engine.switch_state("state_shell_menu")

        # Early shell detection — "Initializing Engine Completed" fires
        # ~1s after XComShell is created, after async loads are done.
        # By this point UC's StopMenuMusic() has had a real target to
        # kill. Using "Game class is 'XComShell'" was too early — native
        # music loaded async and started AFTER StopMenuMusic was called.
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

    def _report_flush(self, batch):
        """Measure how far behind the game's log is running.

        Every line carries the engine's own clock, so the engine-time span of
        a SINGLE read is a lower bound on how long those lines sat unwritten.
        A read covering 98 seconds of engine time means the game produced
        those lines 98 seconds apart and we heard about all of them at once.

        That is the whole question for cinematics. A cinematic writes nothing
        while it plays, so if the log is buffered there is nothing to push
        "Movie Started" out until the film ends — and by then it is too late
        to pause for it. Spans near zero mean the log is prompt and the movie
        events can be trusted live; large spans around movie events mean they
        cannot, and detection has to move out of the log entirely.

        Enable with "debug_log_flush": true in xipod_config.json. Look for
        FLUSH lines in the app's own log under <music folder>/_logs/.
        """
        stamps = [t for t in (_engine_time(l) for l in batch) if t is not None]
        if not stamps:
            return

        span = max(stamps) - min(stamps)
        movies = [l for l in batch if "movie started event" in l.lower()
                  or "movie finished event" in l.lower()]
        if span < _FLUSH_SPAN_WARN and not movies:
            return

        console.debug(
            f"FLUSH: one read carried {len(batch)} "
            f"line{'' if len(batch) == 1 else 's'} spanning {span:.2f}s of "
            f"engine time ({min(stamps):.2f}–{max(stamps):.2f})"
            + (f", including {len(movies)} movie "
               f"event{'' if len(movies) == 1 else 's'}" if movies else "")
        )
        for line in movies:
            console.debug(f"FLUSH:   {line[:110]}")
        if movies and span >= _FLUSH_SPAN_WARN:
            console.debug(
                "FLUSH:   ^ movie events arrived batched — the log is buffered, "
                "so a cinematic cannot be caught from it while it plays"
            )

    def _is_cinematic_locked(self):
        """True if a cinematic is actively playing and music must stay silent."""
        return time.time() < self._cinematic_lock_until

    def _clear_cinematic_lock(self):
        """Clear the cinematic lock and cancel any pending safety timer."""
        self._cinematic_lock_until = 0.0
        self._active_cinematic = None
        # Also stands the mod-driven lock down, so that a lock released by
        # the safety timer or by a STATE_ command hands the Movie-event path
        # back rather than leaving it suppressed for the rest of the session.
        self._uc_cinematic = False
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
            # Clear the lock and let the state switch proceed. There used to
            # be a "too fresh, ignore it" guard here for events arriving in
            # the same read as Movie Started; that case is now caught at the
            # source, in _handle_cutscene_start.
            if self._is_cinematic_locked():
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
            return _normalise_cin(line.split(prefix)[1].split(",")[0])
        except (IndexError, AttributeError):
            return ""

    @staticmethod
    def _finished_later_in_batch(key, rest_of_batch):
        """True if this cinematic's "Movie Finished" is already in this read."""
        for line in rest_of_batch:
            m = _MOVIE_FINISHED_RE.search(line)
            if m and _normalise_cin(m.group(1)).lower() == key:
                return True
        return False

    def _handle_cutscene_start(self, line, rest_of_batch=()):
        # The mod already told us, earlier and more reliably. Its lock has no
        # fixed duration and is released by CINE_OFF, so re-locking here with
        # a table duration could only cut it short.
        if self._uc_cinematic:
            return

        cin_name = self._extract_cin_name(line, "Movie Started Event: ")
        key = cin_name.lower() if cin_name else ""
        if not key:
            return

        # A cinematic writes nothing to the log while it plays, so there is
        # often nothing to push "Movie Started" out of the engine's buffer
        # until the film ends and both events arrive together. Locking on a
        # cinematic that has demonstrably already finished would mute the
        # music for its entire runtime — up to 204s — after the fact.
        if self._finished_later_in_batch(key, rest_of_batch):
            console.debug(
                f"{cin_name} started and finished within one read — "
                f"already over, not locking"
            )
            return

        if key not in _CINEMATIC_DURATIONS:
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
        # CINE_OFF owns the release while the mod watcher is driving. Letting
        # a Movie Finished clear the lock here would resume the music during
        # a chained sequence, between two films the mod still considers one
        # unbroken cinematic.
        if self._uc_cinematic:
            return

        m = _MOVIE_FINISHED_RE.search(line)
        if not m:
            return

        cin_name = _normalise_cin(m.group(1))
        key = cin_name.lower()
        if not key:
            return

        played, runtime = float(m.group(2)), float(m.group(3))
        stamp = _engine_time(line)

        # Some Finished events are emitted twice against the same engine
        # timestamp. The duplicate usually carries a raw clock reading in the
        # played field (16860449s in one real log) rather than a duration, so
        # it can only be filtered on identity.
        if (key, stamp) == self._last_finished:
            console.debug(f"Duplicate Movie Finished for {cin_name} — ignoring")
            return
        self._last_finished = (key, stamp)

        was_known = key in _CINEMATIC_DURATIONS

        # The line states the film's true runtime, so the bundled durations
        # table only has to carry a cinematic until its first playthrough.
        if 0 < runtime < 86400:
            _CINEMATIC_DURATIONS[key] = int(round(runtime))

        holding_lock = (self._active_cinematic or "").lower() == key
        if not was_known and not holding_lock:
            # Never locked for this one and it isn't in the table — resuming
            # here could start music on a state that is meant to be silent.
            return

        if played < runtime * 2:  # guards against a duplicate's clock reading
            how = "skipped" if played < runtime else "played through"
            console.debug(f"{cin_name}: {how} ({played:.1f}s of {runtime:.1f}s)")

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
        console.debug(f"Scheduling post-cinematic resume in {_POST_CINEMATIC_RESUME_DELAY}s")
        t = threading.Timer(_POST_CINEMATIC_RESUME_DELAY,
                            self._delayed_cinematic_resume, args=[cin_name])
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

    # ------------------------------------------------------------------ #
    #  Mod-driven cinematic lock
    #
    #  The mod polls for a cinematic and tells us before the film starts,
    #  which is the only useful moment: once UIPlayMovie blocks the script
    #  thread nothing more is written to the log until the film ends.
    # ------------------------------------------------------------------ #

    def _cmd_cine_watch(self, parts):
        """The mod's watcher came up (fresh map). Nothing to do but note it."""
        console.debug("Mod cinematic watcher active")

    def _cmd_cine_on(self, parts):
        if self._uc_cinematic:
            return
        self._uc_cinematic = True
        console.signal("Cinematic starting (mod watcher) — holding music")

        self.audio_engine.pause(fade=False)

        self._active_cinematic = _UC_CINEMATIC
        self._cinematic_lock_set_at = time.time()
        self._cinematic_lock_until = self._cinematic_lock_set_at + _UC_CINEMATIC_SAFETY

        # CINE_OFF is the real release; this only covers the mod going quiet
        # (crash mid-film, or the watcher dying with the map).
        if self._cinematic_safety_timer:
            self._cinematic_safety_timer.cancel()
        self._cinematic_safety_timer = threading.Timer(
            _UC_CINEMATIC_SAFETY, self._safety_cinematic_resume, args=[_UC_CINEMATIC]
        )
        self._cinematic_safety_timer.daemon = True
        self._cinematic_safety_timer.start()

    def _cmd_cine_off(self, parts):
        if not self._uc_cinematic:
            return
        self._uc_cinematic = False
        console.signal("Cinematic over (mod watcher) — music resuming")
        self._clear_cinematic_lock()

        t = threading.Timer(_POST_CINEMATIC_RESUME_DELAY,
                            self._delayed_cinematic_resume, args=[_UC_CINEMATIC])
        t.daemon = True
        t.start()

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
