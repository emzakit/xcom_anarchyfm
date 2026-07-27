"""Anarchy Radio FM Audio Engine — thin facade coordinating library, settings, and playback."""

import os
import random
import threading

from pydub import AudioSegment

# STINGER_STATES (victory/defeat: play once, no loop, no advance) is defined
# in library.py alongside the other state-folder lists — single source of truth.
from library import MusicLibrary, STINGER_STATES
from settings import EngineSettings
from playback import PlaybackController
import console
import mms_config

# Duration of silence played when a state's toggle is OFF.
# Keeps the engine "active" (is_playing=True) so repeated STATE_
# commands for the same state see "already playing" and skip,
# while outputting silence so the game's native music plays through.
SILENT_DURATION_MS = 30000


class XiPodEngine:
    def __init__(self):
        self.library = MusicLibrary()
        self.settings = EngineSettings()
        self.playback = PlaybackController()

        # Current resolved state
        self.current_top = None

        # Active playlist + index
        self.active_playlist = []
        self.active_index = 0

        # Master playback config
        self.volume = 1.0
        self.shuffle = True
        self.crossfade_ms = 2500

        # True when we're playing silence because the state's toggle is OFF
        self._silent_override = False

        # True when radio toggle is ON — playing from state_resistance_radio
        # folder with forced random start on every track.
        self._radio_mode = False

        # Lock that serializes the "check generation + start playback" commit
        # in _load_and_play against "bump generation + stop playback" in pause().
        # This eliminates the TOCTOU race where pause() fires between the final
        # generation check and playback.start(), causing start() to clear stop_event.
        self._commit_lock = threading.Lock()
        # Incremented on every switch_state/pause call — background loaders check
        # this to bail out if a newer switch or pause has been requested.
        self._switch_generation = 0

        # Optional Spotify remote control (experimental). When set and active,
        # states with an assigned Spotify playlist are handed to Spotify
        # instead of the local file engine. None = feature off (default path
        # is completely unchanged).
        self.spotify = None
        self._spotify_active = False
        self._spotify_paused = False

        # Paths for rescan
        self._root_folder = None
        self._game_log_path = None

    # ------------------------------------------------------------------ #
    #  Library Loading
    # ------------------------------------------------------------------ #

    def load_library(self, root_folder, game_log_path, game_config_folder=None, shuffle=True):
        self._root_folder = root_folder
        self._game_log_path = game_log_path
        self.shuffle = shuffle

        # Derive ini path from log path
        ini_path = self._get_ini_path(game_log_path)
        if ini_path:
            self.settings.load_from_ini(ini_path)

        # Sync MMS config files based on toggle states.
        # Writes to the game's user Config dir (Documents/my games/...),
        # NOT the mod folder (Steam overwrites that on updates).
        # This runs BEFORE the game reads ini, so disabled states let MMS play.
        if game_config_folder:
            mms_config.sync_ini_files(self.settings.toggles, config_folder=game_config_folder)
        else:
            console.warn("No game_config_folder set — MMS config sync skipped.")

        self.library.load(root_folder)
        self.library.export_ini(game_log_path, self.settings.get_settings_lines())

    def rescan(self):
        """Re-scan the music library. Preserves current state and settings."""
        if not self._root_folder or not self._game_log_path:
            console.warn("Can't rescan — library was never loaded.")
            return
        console.shen("Rescanning the music archive, Commander...")
        saved_top = self.current_top

        self.library.load(self._root_folder)
        self.library.export_ini(self._game_log_path, self.settings.get_settings_lines())

        if saved_top:
            self.current_top = None
            self.switch_state(saved_top)
        console.shen("Rescan complete. All tracks accounted for.")

    def _get_ini_path(self, log_path):
        base_dir = os.path.dirname(os.path.dirname(log_path))
        config_dir = os.path.join(base_dir, "Config")
        ini_path = os.path.join(config_dir, "XComXiPod.ini")
        if os.path.exists(ini_path):
            return ini_path
        return None

    # ------------------------------------------------------------------ #
    #  Effects Helper
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize(segment):
        """Force 16-bit 44100Hz stereo — WAV files may be 24/32-bit which
        causes pyaudio to open a stream that many devices output as silence."""
        if segment.sample_width != 2:
            console.debug(f"Normalizing: {segment.sample_width * 8}-bit -> 16-bit")
            segment = segment.set_sample_width(2)
        if segment.frame_rate != 44100:
            console.debug(f"Resampling: {segment.frame_rate}Hz -> 44100Hz")
            segment = segment.set_frame_rate(44100)
        if segment.channels == 1:
            console.debug("Converting: mono -> stereo")
            segment = segment.set_channels(2)
        return segment

    def _process_segment(self, segment):
        """Apply effects to a segment based on current state settings.

        Uses per-state preset if one is selected, otherwise falls back
        to the individual radio/reverb checkboxes + global FX sliders.
        """
        if not self.current_top:
            return segment
        use_radio, use_reverb, fx_params = self.settings.resolve_fx(self.current_top)
        return PlaybackController.apply_effects(segment, use_radio, use_reverb, fx_params)

    def _apply_random_start(self, segment, state, force=False):
        """Slice from a random position — like tuning into a radio station.

        Called with force=True for radio mode (always random start).
        Called without force for normal mode (uses the per-state toggle).
        """
        if not force and not self.settings.should_random_start(state):
            return segment
        duration_ms = len(segment)
        if duration_ms < 5000:  # Too short to bother
            return segment
        # Start anywhere in the first 90% (leave at least 10% to play)
        max_start = int(duration_ms * 0.9)
        start_ms = random.randint(0, max_start)
        console.debug(f"Random start: jumping to {start_ms}ms / {duration_ms}ms")
        return segment[start_ms:]

    def _get_effective_volume(self):
        """Return combined master * state volume. Called by playback thread."""
        return self.settings.effective_volume(self.current_top, self.volume)

    def _prepare_segment(self, track, random_start=False, state_random=False):
        """Load a track file, normalize it, and apply random start + FX.
        Raises on unreadable files — callers decide how to recover.

        random_start=True forces a random start (radio mode).
        state_random=True honors the per-state random-start toggle
        (only wanted on state switches, not on skips/auto-advance).
        """
        segment = AudioSegment.from_file(track['path'])
        segment = self._normalize(segment)
        if random_start:
            segment = self._apply_random_start(segment, self.current_top, force=True)
        elif state_random:
            segment = self._apply_random_start(segment, self.current_top)
        return self._process_segment(segment)

    def _commit_playback(self, generation, segment, fade_in=False):
        """Atomically start playback if no newer switch/pause has landed.
        Returns True if playback was started."""
        with self._commit_lock:
            if generation != self._switch_generation:
                console.debug(f"commit BAIL — gen {generation} != {self._switch_generation}")
                return False
            if self.playback.is_playing:
                console.debug("commit BAIL — already playing")
                return False
            self.playback.start(segment, on_track_finished=self._advance_track,
                                get_volume=self._get_effective_volume, fade_in=fade_in)
            return True

    # ------------------------------------------------------------------ #
    #  State Switching
    # ------------------------------------------------------------------ #

    def _play_silent_override(self, top):
        """Play silence for a toggled-off state. Keeps engine 'active' so
        repeated STATE_ commands see is_playing=True and skip, while the
        game's native music plays through uninterrupted."""
        self.pause()
        self.current_top = top
        self._silent_override = True
        self.active_playlist = []
        self.active_index = 0

        console.shen(f"Silent override for {top} — game music has the conn.")
        silence = AudioSegment.silent(duration=SILENT_DURATION_MS, frame_rate=44100)
        self.playback.start(silence, on_track_finished=self._advance_track, get_volume=self._get_effective_volume)

    def switch_state(self, top):
        """Switch to a new music state. The quick checks (same-state, toggle,
        empty playlist) run inline so the log watcher stays responsive.
        The heavy work (file I/O, FX processing) is dispatched to a
        background thread so cinematic pause commands aren't blocked."""
        top = top.lower()

        # --- Spotify override (experimental) -------------------------------
        # If Spotify is active and this state has an assigned playlist, hand
        # the state to Spotify and stand the local engine down. Only taken
        # when the feature is on; otherwise the path below is unchanged.
        if self.spotify and self.spotify.is_active():
            uri = self.spotify.playlist_for(top)
            if uri:
                if top != self.current_top or not self._spotify_active:
                    self.pause()
                    self.playback.current_segment = None
                    self.active_playlist = []   # local engine stands down
                    self.active_index = 0
                    self.current_top = top
                    self._spotify_active = True
                    self._spotify_paused = False
                    console.shen(f"Spotify has {top} — handing off the airwaves.")
                    self.spotify.play_context_async(uri)
                return
            # Leaving a Spotify-scored state for one without a playlist:
            # stop Spotify and fall through to normal local playback.
            if self._spotify_active:
                self._spotify_active = False
                self.spotify.pause_async()

        # If already in this exact state and music is playing, skip
        if top == self.current_top:
            if self.playback.is_playing:
                console.faint(f"(already tuned to {top})")
                return
            # Music is stopped and we're already on this state. Only resume
            # if a suspended segment is waiting — that only happens after a
            # cinematic pause (which preserves current_segment). After a real
            # state switch, current_segment is cleared, so a DUPLICATE state
            # trigger (combat announces itself via the UC STATE line, the
            # Kismet concealment line, AND MMS "Transition to Combat") falls
            # through to a no-op and lets the in-flight loader start playback,
            # instead of resuming the previous state's track over it.
            if self.playback.current_segment is not None:
                console.shen(f"Resuming {top} after pause.")
                self.play()
            else:
                console.debug(f"(already on {top} — switch loader will start playback)")
            return

        # Check toggle — if disabled, play silence instead of real music.
        toggle_key = self.settings.get_toggle_key(top)
        if toggle_key and not self.settings.toggles.get(toggle_key, True):
            self._play_silent_override(top)
            return

        self._silent_override = False

        radio_mode = self.settings.is_radio_mode(top)
        self._radio_mode = radio_mode
        use_loop = self._should_loop_for_state(top)
        playlist = self.library.resolve_playlist(top, use_loop=use_loop, use_radio=radio_mode)
        console.debug(f"switch_state({top}) radio={radio_mode} loop={use_loop} tracks={len(playlist)}")
        if not playlist:
            console.shen(f"No custom tracks for {top}. Game music has the conn.")
            self.pause()
            self.current_top = top
            return

        # If resolved playlist is the same tracks already playing, just keep going
        active_paths = {t['path'] for t in self.active_playlist} if self.active_playlist else set()
        new_paths = {t['path'] for t in playlist}
        if active_paths == new_paths and self.playback.is_playing:
            console.debug(f"Same playlist — holding steady on {top}")
            self.current_top = top
            return

        old_desc = self.current_top or "None"
        console.divider()
        console.shen(f"Switching frequencies: {old_desc} -> {top} ({len(playlist)} tracks)")

        # Capture outgoing tail for crossfade BEFORE stopping
        outgoing_tail = self.playback.capture_outgoing_tail(self.crossfade_ms)

        self.pause()
        # Abandon the old track entirely — only cinematic pauses are
        # resumable. If a stray resume fires anyway, it must reload the
        # NEW state's track, never continue the old segment.
        self.playback.current_segment = None
        self.playback.playback_position = 0
        self.current_top = top

        # Shuffle playlist
        self.active_playlist = list(playlist)
        if len(self.active_playlist) > 1:
            random.shuffle(self.active_playlist)
        self.active_index = 0

        # Bump generation — any older background loader will bail out
        self._switch_generation += 1
        gen = self._switch_generation
        console.debug(f"switch_state({top}) — dispatching _load_and_play with gen={gen}")

        # Dispatch the slow part (file load + FX) to a background thread
        # so the log watcher can keep processing (e.g. cinematic pauses).
        threading.Thread(
            target=self._load_and_play,
            args=(gen, outgoing_tail, top),
            daemon=True,
            name=f"Loader-{gen}"
        ).start()

    def _load_and_play(self, generation, outgoing_tail, top):
        """Background worker: loads the track, applies FX, starts playback.
        Bails out if a newer switch_state or a pause has fired since dispatch.

        The slow work (file I/O, FX processing) runs WITHOUT holding any lock
        so that pause() can respond instantly. Only the final "check generation
        + start playback" is done under _commit_lock, making it atomic with
        respect to pause()'s "bump generation + stop playback".
        """
        # Early bail-out (no lock needed — just an optimisation)
        if generation != self._switch_generation:
            console.debug(f"_load_and_play BAIL(early) — gen {generation} != {self._switch_generation}")
            return

        track = self.active_playlist[0]
        console.track("Now playing", track['name'])

        try:
            incoming = self._prepare_segment(track, random_start=self._radio_mode,
                                             state_random=True)
        except Exception as e:
            console.error(f"Track failed to load: {track['name']} — {e}")
            return

        # Check again after the slow load — did a pause or new switch land?
        if generation != self._switch_generation:
            console.debug(f"_load_and_play BAIL(post-load) — gen {generation} != {self._switch_generation}")
            return

        # Crossfade (still outside the lock — it's pure computation)
        segment = PlaybackController.crossfade_segments(outgoing_tail, incoming, self.crossfade_ms)
        self._commit_playback(generation, segment)

    # ------------------------------------------------------------------ #
    #  Playback Controls
    # ------------------------------------------------------------------ #

    def is_spotify_active(self):
        """True when Spotify currently owns playback for the active state."""
        return bool(self._spotify_active and self.spotify and self.spotify.is_active())

    def spotify_is_paused(self):
        return self._spotify_paused

    def play(self, track_id=None):
        # Spotify owns this state — a play/resume command resumes Spotify,
        # not the local engine. (track_id selections are ignored in this mode.)
        if self.is_spotify_active():
            self.spotify.resume_async()
            self._spotify_paused = False
            return

        if track_id is not None:
            self.pause()
            entry = self.library.find_track_by_id(int(track_id))
            if entry:
                # Set state from the track's state so volume/fx resolve correctly
                if entry.get('state') and not self.current_top:
                    self.current_top = entry['state']
                console.track("Now playing", entry['name'])
                gen = self._switch_generation
                threading.Thread(
                    target=self._load_and_play_entry, args=(gen, entry),
                    daemon=True, name=f"PlayID-{gen}"
                ).start()
            return

        if self.playback.is_playing:
            return

        # If we have a playlist, resume from it (loading happens off-thread
        # so GUI clicks and the log watcher never block on file I/O + FX)
        if self.active_playlist:
            gen = self._switch_generation
            threading.Thread(
                target=self._resume_playlist, args=(gen,),
                daemon=True, name=f"Resume-{gen}"
            ).start()
            return

        # No playlist loaded — try to kick-start from current state
        if self.current_top:
            console.shen("No playlist loaded — triggering current state.")
            saved = self.current_top
            self.current_top = None
            self.switch_state(saved)
        else:
            console.shen("Nothing to play — waiting for a state command from XCOM.")

    def _load_and_play_entry(self, generation, entry):
        """Background worker for play-by-track-id."""
        try:
            segment = self._prepare_segment(entry)
        except Exception as e:
            console.error(f"Track failed to load: {entry['name']} — {e}")
            return
        self._commit_playback(generation, segment)

    def _resume_playlist(self, generation):
        """Background worker: resume the active playlist from where it left off."""
        track = self.active_playlist[self.active_index % len(self.active_playlist)]
        segment = self.playback.current_segment
        pos = self.playback.playback_position
        if segment is None:
            try:
                segment = self._prepare_segment(track, random_start=self._radio_mode)
            except Exception as e:
                console.error(f"Track failed to load: {track['name']} — {e}")
                return
            pos = 0

        # Resume from where we left off, not the beginning
        if 0 < pos < len(segment):
            segment = segment[pos:]
            console.track("Resuming", f"{track['name']} (from {pos}ms)")
        else:
            console.track("Resuming", track['name'])

        self._commit_playback(generation, segment, fade_in=True)

    def pause(self, fade=True):
        # If Spotify owns the current state, a pause pauses Spotify too.
        # (Only fires while Spotify is active — the local path is unchanged.)
        if self.is_spotify_active():
            self.spotify.pause_async()
            self._spotify_paused = True

        # Acquire _commit_lock so this is atomic with respect to the
        # "check generation + start playback" block in _load_and_play.
        # Without the lock, pause could fire between those two lines,
        # setting stop_event that start() immediately clears (TOCTOU).
        old_gen = self._switch_generation
        console.debug(f"pause(fade={fade}) — acquiring commit lock, gen={old_gen}, is_playing={self.playback.is_playing}")
        with self._commit_lock:
            self._switch_generation += 1
            new_gen = self._switch_generation
            console.debug(f"pause() — lock acquired, gen {old_gen}->{new_gen}, calling playback.stop()")
            self.playback.stop(fade_out=fade)
            console.debug(f"pause() — playback.stop() returned, is_playing={self.playback.is_playing}")

    def next_track(self):
        if self.is_spotify_active():
            self.spotify.next_async()
            return
        self._skip(+1)

    def prev_track(self):
        if self.is_spotify_active():
            self.spotify.prev_async()
            return
        self._skip(-1)

    def _skip(self, delta):
        """Manual skip. Heavy loading is dispatched to a background thread."""
        if not self.active_playlist:
            return
        outgoing_tail = self.playback.capture_outgoing_tail(self.crossfade_ms)
        self.pause(fade=False)
        self.playback.current_segment = None
        self.active_index = (self.active_index + delta) % len(self.active_playlist)
        gen = self._switch_generation
        threading.Thread(
            target=self._load_and_crossfade, args=(gen, outgoing_tail),
            daemon=True, name=f"Skip-{gen}"
        ).start()

    def _load_and_crossfade(self, generation, outgoing_tail):
        """Background worker: load current track and crossfade from outgoing tail."""
        track = self.active_playlist[self.active_index % len(self.active_playlist)]
        console.track("Now playing", track['name'])
        try:
            # Radio mode: always random start. Non-radio: never on manual skip.
            segment = self._prepare_segment(track, random_start=self._radio_mode)
        except Exception as e:
            console.error(f"Track failed to load: {track['name']} — {e}")
            return
        segment = PlaybackController.crossfade_segments(outgoing_tail, segment, self.crossfade_ms)
        self._commit_playback(generation, segment)

    def _should_loop(self):
        """Check if the current state has looping enabled."""
        return self._should_loop_for_state(self.current_top)

    def _should_loop_for_state(self, state):
        """Check if a given state has looping enabled."""
        loop_key = self.settings.get_loop_key(state)
        if loop_key is None:
            return False
        return self.settings.loop.get(loop_key, False)

    def _advance_track(self):
        """Called (on a fresh thread) when a track finishes naturally.

        Snapshot the switch generation first: if a state switch or pause
        lands while we're loading the next file, we bail out instead of
        starting a stale track over the new one.
        """
        generation = self._switch_generation
        self.playback.is_playing = False
        self.playback.current_segment = None

        # Silent override — keep looping silence until state changes
        if self._silent_override:
            silence = AudioSegment.silent(duration=SILENT_DURATION_MS, frame_rate=44100)
            self._commit_playback(generation, silence)
            return

        if not self.active_playlist:
            return

        # Stinger states (victory/defeat) play once then stop
        if self.current_top in STINGER_STATES:
            console.shen(f"Stinger complete ({self.current_top}). Standing by for orders.")
            return

        # If loop is ON for this state, replay the same track
        if self._should_loop():
            track = self.active_playlist[self.active_index % len(self.active_playlist)]
            console.track("Looping", track['name'])
            try:
                segment = self._prepare_segment(track)
            except Exception as e:
                console.error(f"Track failed to load: {track['name']} — {e}")
                return
            self._commit_playback(generation, segment)
            return

        # Loop OFF — advance to the next track. Bounded retry: if a file
        # is unreadable, skip it, but never spin forever when the whole
        # playlist is broken.
        for _ in range(len(self.active_playlist)):
            next_idx = self.active_index + 1
            if next_idx >= len(self.active_playlist):
                next_idx = 0
                if self.shuffle and len(self.active_playlist) > 1:
                    random.shuffle(self.active_playlist)

            self.active_index = next_idx
            track = self.active_playlist[self.active_index]
            console.track("Next up", track['name'])

            try:
                # Radio mode: always random start. Non-radio: never on auto-advance.
                segment = self._prepare_segment(track, random_start=self._radio_mode)
            except Exception as e:
                console.error(f"Track failed to load: {track['name']} — {e}")
                continue
            self._commit_playback(generation, segment)
            return

        console.error("Every track in the playlist failed to load. Standing by.")

    # ------------------------------------------------------------------ #
    #  Settings Passthrough
    # ------------------------------------------------------------------ #

    def set_toggle(self, toggle_name, enabled):
        key = toggle_name.lower()
        old_value = self.settings.toggles.get(key)
        self.settings.set_toggle(toggle_name, enabled)
        if old_value == enabled:
            return

        # Rewrite MMS ini files so the change takes effect on next game launch
        mms_config.sync_ini_files(self.settings.toggles)

        if not enabled:
            # Toggled OFF mid-state → switch to silent override
            active_key = self.settings.get_toggle_key(self.current_top)
            if active_key == key:
                self._play_silent_override(self.current_top)
        elif enabled and self._silent_override:
            # Toggled ON mid-state → reload real tracks
            active_key = self.settings.get_toggle_key(self.current_top)
            if active_key == key:
                self._silent_override = False
                saved_top = self.current_top
                self.current_top = None
                self.switch_state(saved_top)

    def set_state_volume(self, state_key, level):
        self.settings.set_volume(state_key, level)

    def set_radio(self, state_key, enabled):
        key = state_key.lower()
        old_value = self.settings.radio.get(key)
        self.settings.set_radio(state_key, enabled)
        if old_value == enabled:
            return
        # Radio toggle changed — reload current state to switch between
        # radio folder and normal folder.
        if self.current_top:
            active_key = self.settings.get_toggle_key(self.current_top)
            if active_key == key:
                saved = self.current_top
                self.current_top = None
                self.switch_state(saved)

    def set_reverb(self, state_key, enabled):
        key = state_key.lower()
        old_value = self.settings.reverb.get(key)
        self.settings.set_reverb(state_key, enabled)
        if old_value == enabled:
            return

    def set_loop(self, state_key, enabled):
        key = state_key.lower()
        old_value = self.settings.loop.get(key)
        self.settings.set_loop(state_key, enabled)
        if old_value == enabled:
            return
        if self.current_top:
            active_loop_key = self.settings.get_loop_key(self.current_top)
            if active_loop_key == key:
                saved_top = self.current_top
                self.current_top = None
                self.switch_state(saved_top)

    def set_random_start(self, state_key, enabled):
        self.settings.set_random_start(state_key, enabled)

    def set_preset(self, state_key, preset_name):
        self.settings.set_preset(state_key, preset_name)

    def save_user_preset(self, slot):
        self.settings.save_user_preset(slot)

    def clear_user_preset(self, slot):
        self.settings.clear_user_preset(slot)

    def set_fx_param(self, param_name, value):
        key = param_name.lower()
        old_value = self.settings.fx_params.get(key)
        self.settings.set_fx_param(param_name, value)
        if old_value == int(value):
            return

    def set_volume(self, level):
        self.volume = max(0.0, min(1.0, float(level)))

    def set_crossfade(self, ms):
        self.crossfade_ms = max(0, int(ms))

    def get_now_playing(self):
        if self.active_playlist and self.playback.is_playing:
            track = self.active_playlist[self.active_index % len(self.active_playlist)]
            return track["name"]
        return ""

    def shutdown(self):
        """Stop playback and release audio resources. Call once on exit."""
        if self._spotify_active and self.spotify:
            self.spotify.pause_async()
            self._spotify_active = False
        self.pause(fade=False)
        self.playback.close()
