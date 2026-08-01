"""Anarchy Radio FM Audio Engine — thin facade coordinating library, settings, and playback."""

import os
import random
import threading

from pydub import AudioSegment

# STINGER_STATES (victory/defeat: play once, no loop, no advance) is defined
# in library.py alongside the other state-folder lists — single source of truth.
from library import (
    MusicLibrary, STINGER_STATES, BASE_STATES,
    RADIO_MODE_STATE, RADIO_SOURCE_RADIO, interleave_pools,
)
from settings import EngineSettings
from playback import PlaybackController
import decode
from decode import load_audio
import console
import mms_config
import mms_packs

# Duration of silence played when a state's toggle is OFF.
# Keeps the engine "active" (is_playing=True) so repeated STATE_
# commands for the same state see "already playing" and skip,
# while outputting silence so the game's native music plays through.
SILENT_DURATION_MS = 30000

# Minutes of a station Radio Mode decodes at a time. See radio_chunk_ms.
DEFAULT_RADIO_CHUNK_MIN = 10


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

        # The separate folders the active playlist was woven from, when Radio
        # Mode is drawing from more than one. Held so the playlist can be
        # rewoven each time it runs out — a straight reshuffle of the finished
        # list would keep the balance but replay the same 24 tracks forever.
        # Empty whenever there's only one source, which is every other state.
        self._mix_pools = []

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

        # Radio Mode (the panel button). Applies to the Avenger ONLY — see
        # RADIO_MODE_STATE in library.py for why. Tracks get a forced random
        # start, as if you'd tuned into a station mid-broadcast.
        # Deliberately a separate flag rather than flipping settings.radio:
        # the per-state checkboxes in the Effects dialog are the user's saved
        # preferences, and a temporary master switch has no business
        # overwriting them.
        self.radio_override = False
        self.radio_source = RADIO_SOURCE_RADIO

        # How much of a track Radio Mode decodes before the station "moves on"
        # and re-tunes. Station rips run to an hour; decoding one whole costs
        # ~657 MB and ten-plus seconds of silence before the first note.
        # 0 disables the cap and plays to the end of the file.
        self.radio_chunk_ms = DEFAULT_RADIO_CHUNK_MIN * 60 * 1000

        # Discovered music addons (Workshop packs). Their tracks are merged
        # into the library on load and referenced in place — see addons.py.
        self.addons = []

        # Paths for rescan
        self._root_folder = None
        self._game_log_path = None
        self._game_config_folder = None
        self._workshop_folder = None
        self._mod_config_folders = []
        self._game_exe = ""

        # Debounced settings write-back (see _persist_settings).
        self._persist_lock = threading.Lock()
        self._persist_timer = None

    # ------------------------------------------------------------------ #
    #  Library Loading
    # ------------------------------------------------------------------ #

    def load_library(self, root_folder, game_log_path, game_config_folder=None,
                     shuffle=True, addons=None, workshop_folder=None,
                     mod_config_folders=None, game_exe=""):
        self._root_folder = root_folder
        self._game_log_path = game_log_path
        self._game_config_folder = game_config_folder
        # Used to spot other people's MMS packs, and to find our own installed
        # mod folder — which is the only place MMS reads our config from.
        self._workshop_folder = workshop_folder
        # Only used to find the launcher's mod list, which is the
        # authority on where the mod is actually loaded from.
        self._game_exe = game_exe or ""
        # Escape hatch for installs the workshop folder can't describe, such
        # as a local ModBuddy build.
        if isinstance(mod_config_folders, str):
            mod_config_folders = [mod_config_folders]
        self._mod_config_folders = [p for p in (mod_config_folders or []) if p]
        self.shuffle = shuffle
        self.addons = addons or []

        # Derive ini path from log path
        ini_path = self._get_ini_path(game_log_path)
        if ini_path:
            self.settings.load_from_ini(ini_path)

        self.library.load(root_folder, addons=self.addons)
        self.library.export_ini(game_log_path, self.settings.get_settings_lines())

        # Sync MMS config files. This runs AFTER the scan so a state whose
        # folder turned out to be empty can be left unsilenced for MMS to
        # cover, rather than silenced into dead air.
        # Writes to the game's user Config dir (Documents/my games/...),
        # NOT the mod folder (Steam overwrites that on updates).
        if game_config_folder:
            self.sync_mms_config(config_folder=game_config_folder)
        else:
            console.warn("No game_config_folder set — MMS config sync skipped.")

    def _state_enabled(self, state):
        """False when the state's toggle is off — the game's music owns it."""
        key = self.settings.get_toggle_key(state)
        return not key or self.settings.toggles.get(key, True)

    def _toggle_keys_with_tracks(self):
        """Which toggle keys we can actually cover, and so are safe to silence.

        Resolution goes through the library the same way switch_state would
        ask for it — loop folders, radio sources and all — so the answer
        matches what would really play rather than what the folder layout
        hints at. A state that comes back empty is left to MMS.

        A Spotify-scored state counts as covered even with an empty folder:
        Spotify is what plays there, and leaving it unsilenced put the stock
        soundtrack underneath the playlist rather than replacing it.
        """
        found = {}
        for state in list(BASE_STATES) + list(STINGER_STATES):
            key = self.settings.get_toggle_key(state)
            if not key or found.get(key):
                continue
            if (self.spotify and self.spotify.is_active()
                    and self.spotify.playlist_for(state)):
                found[key] = True
                continue
            if self.radio_override and state == RADIO_MODE_STATE:
                playlist = self.library.resolve_radio_playlist(state, self.radio_source)
            else:
                playlist = self.library.resolve_playlist(
                    state,
                    use_loop=self._should_loop_for_state(state),
                    use_radio=self.settings.is_radio_mode(state),
                )
            found[key] = bool(playlist)
        return found

    def sync_mms_config(self, config_folder=None):
        """Rewrite the MMS ini files for the current toggles and library."""
        try:
            has_tracks = self._toggle_keys_with_tracks()
        except Exception as e:
            # Never let a resolution hiccup stop the sync — falling back to
            # toggles alone is the old behaviour, which is still correct for
            # everyone whose folders aren't empty.
            console.warn(f"Track-presence check failed, syncing on toggles alone: {e}")
            has_tracks = None

        # Other people's MMS music packs, so we can settle who owns each
        # screen instead of leaving it to MMS's coin flip.
        try:
            pack_defs = mms_packs.find_pack_defs(self._workshop_folder,
                                                 config_folder or self._game_config_folder)
        except Exception as e:
            console.warn(f"MMS pack scan failed, leaving pack music as-is: {e}")
            pack_defs = None

        # Where MMS actually reads from. Without at least one of these the
        # silencing does nothing at all, however correct the content is.
        try:
            mod_dirs = mms_packs.find_own_config_dirs(self._workshop_folder,
                                                      self._mod_config_folders,
                                                      game_exe=self._game_exe)
        except Exception as e:
            console.warn(f"Couldn't locate our mod's config folder: {e}")
            mod_dirs = []

        mms_config.sync_ini_files(self.settings.toggles,
                                  config_folder=config_folder,
                                  has_tracks=has_tracks,
                                  pack_defs=pack_defs,
                                  mod_config_dirs=mod_dirs)

    def rescan(self):
        """Re-scan the music library. Preserves current state and settings."""
        if not self._root_folder or not self._game_log_path:
            console.warn("Can't rescan — library was never loaded.")
            return
        console.shen("Rescanning the music archive, Commander...")
        saved_top = self.current_top

        self.library.load(self._root_folder, addons=self.addons)
        self.library.export_ini(self._game_log_path, self.settings.get_settings_lines())

        # Dropping the last track out of a folder (or adding the first one
        # back) changes who should be covering that state next launch.
        self.sync_mms_config()

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
        """Force 16-bit 44100Hz stereo — pyaudio opens a stream that many
        devices output as silence for odd sample widths.

        decode.load_audio already guarantees 16-bit/44100Hz, so in practice
        only the mono->stereo branch still fires (deliberately left to pydub;
        see the layout note in decode.py). The rest is kept as a safety net
        for segments built elsewhere, e.g. the FX chain's raw constructor.
        """
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

    def _pick_random_start(self, path, state, force=False):
        """Choose a random offset to start a track at — like tuning into a
        station already in progress. Returns 0 for "start from the top".

        Decided BEFORE decoding, from the container's own duration metadata,
        so decode.load_audio can seek straight there. Deciding afterwards
        meant decoding the whole file and binning the skipped part, which on
        an hour-long station rip is hundreds of megabytes of wasted work.

        force=True for radio mode (always random). Otherwise the per-state
        random-start toggle decides.
        """
        if not force and not self.settings.should_random_start(state):
            return 0
        duration_ms = decode.probe_duration_ms(path)
        if duration_ms < 5000:  # too short to bother (or unknown)
            return 0
        # Start anywhere in the first 90% (leave at least 10% to play)
        start_ms = random.randint(0, int(duration_ms * 0.9))
        console.debug(f"Random start: jumping to {start_ms}ms / {duration_ms}ms")
        return start_ms

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
        path = track['path']
        if random_start:
            start_ms = self._pick_random_start(path, self.current_top, force=True)
        elif state_random:
            start_ms = self._pick_random_start(path, self.current_top)
        else:
            start_ms = 0

        # The chunk cap only applies to radio playback. A normal track is
        # expected to play through to its end.
        max_ms = self.radio_chunk_ms if random_start else 0

        segment = load_audio(path, start_ms=start_ms, max_ms=max_ms)
        segment = self._normalize(segment)
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
        self._mix_pools = []
        # This path returns before the radio resolution below, so clear the
        # flag explicitly — otherwise it stays stale from whatever state we
        # came from, and a later resume would apply a random start that this
        # state never asked for.
        self._radio_mode = False

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
            # A toggled-off state belongs to the game's own music, and that
            # applies to Spotify too. Spotify used to skip this check
            # entirely, so a screen we had deliberately left unsilenced got
            # the stock soundtrack, MMS and Spotify all at once.
            uri = self.spotify.playlist_for(top) if self._state_enabled(top) else ""
            if uri:
                if top != self.current_top or not self._spotify_active:
                    self.pause()
                    self.playback.current_segment = None
                    self.active_playlist = []   # local engine stands down
                    self.active_index = 0
                    self._mix_pools = []
                    self.current_top = top
                    self._spotify_active = True
                    self._spotify_paused = False
                    console.shen(f"Spotify has {top} — handing off the airwaves.")
                    self.spotify.play_context_async(uri)
                return
            # Leaving a Spotify-scored state for one without a playlist (or
            # for one that's toggled off): stop Spotify and fall through to
            # normal local playback.
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
        if not self._state_enabled(top):
            self._play_silent_override(top)
            return

        self._silent_override = False

        use_loop = self._should_loop_for_state(top)

        # Radio Mode owns the Avenger and nothing else. Everywhere else falls
        # through to the per-state Radio Source checkbox in Effects, which is
        # a separate, deliberately-configured thing and stays untouched.
        if self.radio_override and top == RADIO_MODE_STATE:
            radio_mode = True
            # Radio Mode supersedes the _LOOP folder AND the loop flag. The
            # folder is bypassed in resolve_radio_playlist; clearing use_loop
            # here keeps the debug line honest, and _should_loop() refuses to
            # repeat while radio is live — a station that replays one track
            # forever isn't a station.
            use_loop = False
            pools = self.library.resolve_radio_pools(top, self.radio_source)
            # Only a genuine multi-folder source is a mix. One pool (or none)
            # goes down the ordinary shuffle path.
            self._mix_pools = pools if len(pools) > 1 else []
            playlist = [t for pool in pools for t in pool]
            if self._mix_pools:
                console.debug("Radio mix: "
                              + " + ".join(str(len(p)) for p in pools)
                              + " tracks, alternating sources")
        else:
            radio_mode = self.settings.is_radio_mode(top)
            self._mix_pools = []
            playlist = self.library.resolve_playlist(
                top, use_loop=use_loop, use_radio=radio_mode)

        self._radio_mode = radio_mode
        console.debug(f"switch_state({top}) radio={radio_mode} loop={use_loop} tracks={len(playlist)}")
        if not playlist:
            console.shen(f"No custom tracks for {top}. Game music has the conn.")
            self.pause()
            # Drop the outgoing state's tracks. Leaving them in place meant
            # active_playlist stayed stale, so Next/Prev would start playing
            # the PREVIOUS state's music on a screen that's meant to be silent.
            self.playback.current_segment = None
            self.active_playlist = []
            self.active_index = 0
            self._mix_pools = []
            self.current_top = top
            return

        # If the resolved playlist is the same tracks already playing, keep
        # going rather than restarting the same song on every screen change.
        #
        # EXCEPT when radio is involved on either side. Radio states share one
        # folder, so leaving the Avenger for a screen that also draws from it
        # matched here and simply carried on — the Avenger's track followed you
        # out to the main menu. Radio is meant to re-tune on every arrival
        # anyway, so a fresh random start is the correct behaviour.
        active_paths = {t['path'] for t in self.active_playlist} if self.active_playlist else set()
        new_paths = {t['path'] for t in playlist}
        radio_involved = radio_mode or self._radio_mode
        if active_paths == new_paths and self.playback.is_playing and not radio_involved:
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

        # Shuffle playlist (or weave the sources together, in a radio mix)
        self.active_playlist = self._build_playlist(playlist)
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

    def _build_playlist(self, playlist):
        """Order a resolved playlist for playback.

        A radio mix is woven from its source folders so the two keep trading
        off (see library.interleave_pools); everything else is the plain
        shuffle it has always been.
        """
        if len(self._mix_pools) > 1:
            return interleave_pools(self._mix_pools)
        out = list(playlist)
        if len(out) > 1:
            random.shuffle(out)
        return out

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

    def radio_is_active(self):
        """True when the Radio Mode button currently owns playback."""
        return bool(self.radio_override and self.current_top == RADIO_MODE_STATE)

    def _should_loop(self):
        """Check if the current state has looping enabled."""
        # Radio Mode overrides looping outright — see switch_state.
        if self.radio_is_active():
            return False
        return self._should_loop_for_state(self.current_top)

    def _should_loop_for_state(self, state):
        """Check if a given state has looping enabled."""
        return self.settings.is_loop_enabled(state)

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
                if len(self._mix_pools) > 1:
                    # Reweave rather than reshuffle, and regardless of the
                    # shuffle setting: the weave IS the mix, and reshuffling a
                    # finished one just replays the same sequence for the rest
                    # of the session.
                    self.active_playlist = interleave_pools(self._mix_pools)
                elif self.shuffle and len(self.active_playlist) > 1:
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

    def _persist_settings(self, delay=1.5):
        """Queue a write-back of settings to XComXiPod.ini.

        Settings used to be exported only at startup and on rescan, so
        anything changed in the GUI lived in memory and in the MMS files but
        never reached XComXiPod.ini — every toggle, volume and effect quietly
        reverted on the next launch.

        Debounced because volume and FX are sliders: writing the ini (which
        carries the whole track manifest) on every pixel of a drag would be
        absurd. The last change in a burst wins, 1.5s later.
        """
        if not self._game_log_path:
            return
        with self._persist_lock:
            if self._persist_timer is not None:
                self._persist_timer.cancel()
            self._persist_timer = threading.Timer(delay, self._write_settings_now)
            self._persist_timer.daemon = True
            self._persist_timer.start()

    def _write_settings_now(self):
        with self._persist_lock:
            self._persist_timer = None
        if not self._game_log_path:
            return
        try:
            # prefer_existing=False — this IS the save. The file's old value
            # must not win over what the user just changed.
            self.library.export_ini(self._game_log_path,
                                    self.settings.get_settings_lines(),
                                    prefer_existing=False)
            console.debug("Settings saved to XComXiPod.ini")
        except Exception as e:
            console.warn(f"Couldn't save settings: {e}")

    def flush_settings(self):
        """Write any pending settings immediately — called on shutdown so a
        change made seconds before quitting isn't lost with the timer."""
        with self._persist_lock:
            pending = self._persist_timer is not None
            if pending:
                self._persist_timer.cancel()
                self._persist_timer = None
        if pending:
            self._write_settings_now()

    def set_toggle(self, toggle_name, enabled):
        key = toggle_name.lower()
        old_value = self.settings.toggles.get(key)
        self.settings.set_toggle(toggle_name, enabled)
        if old_value == enabled:
            return

        # Rewrite MMS ini files so the change takes effect on next game launch
        self.sync_mms_config()
        self._persist_settings()

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
        self._persist_settings()

    def set_radio(self, state_key, enabled):
        key = state_key.lower()
        old_value = self.settings.radio.get(key)
        self.settings.set_radio(state_key, enabled)
        if old_value == enabled:
            return
        self._persist_settings()
        # Radio toggle changed — reload current state to switch between
        # radio folder and normal folder.
        if self.current_top:
            active_key = self.settings.get_toggle_key(self.current_top)
            if active_key == key:
                saved = self.current_top
                self.current_top = None
                self.switch_state(saved)

    def set_radio_override(self, enabled):
        """Radio Mode on/off (Avenger only)."""
        enabled = bool(enabled)
        if self.radio_override == enabled:
            return
        self.radio_override = enabled
        console.shen(
            "Resistance Radio is on the air — the Avenger is tuned in."
            if enabled else
            "Resistance Radio off. Avenger back to its regular playlist."
        )
        self._reload_if_on_avenger()

    def set_radio_source(self, source):
        """Which folder(s) Radio Mode draws from — see RADIO_SOURCES."""
        if source == self.radio_source:
            return
        self.radio_source = source
        console.debug(f"Radio source -> {source}")
        if self.radio_override:
            self._reload_if_on_avenger()

    def _reload_if_on_avenger(self):
        """Re-resolve the Avenger playlist so a Radio Mode change is audible
        immediately. Only reloads when the Avenger is actually the live state:
        restarting the track you're listening to elsewhere would be a jarring
        side effect of flipping a switch that doesn't apply there."""
        if self.current_top != RADIO_MODE_STATE:
            return
        saved = self.current_top
        self.current_top = None
        self.switch_state(saved)

    def set_reverb(self, state_key, enabled):
        key = state_key.lower()
        old_value = self.settings.reverb.get(key)
        self.settings.set_reverb(state_key, enabled)
        if old_value == enabled:
            return
        self._persist_settings()

    def set_loop(self, state_key, enabled):
        key = state_key.lower()
        old_value = self.settings.loop.get(key)
        # Compared rather than key-matched: the Battle box loops explore and
        # combat without sharing their loop key, so "did this change what the
        # live state does?" is the only question that gives the right answer
        # for both the master and the sub-toggles.
        was_looping = (self.settings.is_loop_enabled(self.current_top)
                       if self.current_top else None)
        self.settings.set_loop(state_key, enabled)
        if old_value == enabled:
            return
        self._persist_settings()
        if (self.current_top
                and self.settings.is_loop_enabled(self.current_top) != was_looping):
            saved_top = self.current_top
            self.current_top = None
            self.switch_state(saved_top)

    def set_random_start(self, state_key, enabled):
        self.settings.set_random_start(state_key, enabled)
        self._persist_settings()

    def set_preset(self, state_key, preset_name):
        self.settings.set_preset(state_key, preset_name)
        self._persist_settings()

    def save_user_preset(self, slot):
        self.settings.save_user_preset(slot)
        self._persist_settings()

    def clear_user_preset(self, slot):
        self.settings.clear_user_preset(slot)
        self._persist_settings()

    def set_fx_param(self, param_name, value):
        key = param_name.lower()
        old_value = self.settings.fx_params.get(key)
        self.settings.set_fx_param(param_name, value)
        if old_value == int(value):
            return
        self._persist_settings()

    def set_volume(self, level):
        self.volume = max(0.0, min(1.0, float(level)))

    def set_crossfade(self, ms):
        self.crossfade_ms = max(0, int(ms))

    def set_radio_chunk_minutes(self, minutes):
        """How long a stretch Radio Mode plays before re-tuning. 0 = no cap."""
        try:
            minutes = max(0, int(minutes))
        except (TypeError, ValueError):
            minutes = DEFAULT_RADIO_CHUNK_MIN
        self.radio_chunk_ms = minutes * 60 * 1000

    def get_now_playing(self):
        if self.active_playlist and self.playback.is_playing:
            track = self.active_playlist[self.active_index % len(self.active_playlist)]
            return track["name"]
        return ""

    def shutdown(self):
        """Stop playback and release audio resources. Call once on exit."""
        self.flush_settings()
        if self._spotify_active and self.spotify:
            self.spotify.pause_async()
            self._spotify_active = False
        self.pause(fade=False)
        self.playback.close()
