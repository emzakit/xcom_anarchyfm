"""Anarchy Radio FM Music Library — scanning, manifest, INI export."""

import json
import os
import console

# Path to xipod_defaults.json (lives in project root next to xipod_config.json)
from paths import resource_path

_DEFAULTS_PATH = resource_path("xipod_defaults.json")

# Base states (each may also have a _LOOP sibling folder)
BASE_STATES = [
    "state_shell_menu", "state_avenger", "state_geoscape",
    "state_squadselect", "state_mission_explore", "state_mission_combat",
]

# States that support loop variants (all base states get _loop siblings)
LOOP_STATES = {s + "_loop" for s in BASE_STATES}

# Stinger states — no loop variant
STINGER_STATES = ["state_victory", "state_defeat"]

# Shared radio folder — when the radio toggle is ON for a state,
# tracks play from here instead of the state's own folder.
RADIO_STATE = "state_resistance_radio"

# The only state the Radio Mode button applies to. Resistance-radio content
# is long-form downtime atmosphere — DJ banter, fake adverts, hour-long
# mixes. That works on the ship and nowhere else: on the shell menu it
# fights the game's own music, and mid-firefight a DJ telling jokes kills
# the tension outright.
RADIO_MODE_STATE = "state_avenger"

# Which folder(s) Radio Mode draws from.
RADIO_SOURCE_RADIO = "radio"       # STATE_RESISTANCE_RADIO only
RADIO_SOURCE_STATE = "state"       # STATE_AVENGER only
RADIO_SOURCE_BOTH = "both"         # both pooled together
RADIO_SOURCES = (RADIO_SOURCE_RADIO, RADIO_SOURCE_STATE, RADIO_SOURCE_BOTH)

# File types the scanner will pick up. Every one of these is decoded by
# src/decode.py (PyAV), so this list is about what we advertise rather than
# what's technically possible — PyAV will read plenty more. It used to be
# just mp3/wav/ogg, back when decoding meant shelling out to a user-installed
# ffmpeg. Keep it in sync with the table in music/music_readme.md.
AUDIO_EXTENSIONS = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".opus", ".wma")

# The state folders a Workshop addon can ship, upper-cased as they appear on
# disk. RADIO_STATE is included: a station pack is exactly the sort of thing
# people want to share.
STATE_FOLDERS_FOR_MODS = tuple(
    s.upper() for s in
    (BASE_STATES + sorted(LOOP_STATES) + STINGER_STATES + [RADIO_STATE])
)

# Everything the scanner recognises as a valid folder
ALL_KNOWN = set(BASE_STATES) | LOOP_STATES | set(STINGER_STATES) | {RADIO_STATE}


def _scan_audio_files(folder, source=None):
    """Return list of track dicts from a single folder (non-recursive).

    `source` is the addon name the tracks came from, or None for the user's
    own music folder. It's carried through so the UI can say where a track
    came from, and so an addon's tracks can be dropped when it's turned off.
    """
    tracks = []
    if not os.path.isdir(folder):
        return tracks
    for file in sorted(os.listdir(folder)):
        if file.lower().endswith(AUDIO_EXTENSIONS):
            tracks.append({
                "name": file,
                "path": os.path.join(folder, file),
                "source": source,
            })
    return tracks


class MusicLibrary:
    def __init__(self):
        self.library = {}   # key → [track dicts]  (includes _loop keys)
        self.manifest = []

    def load(self, root_folder, addons=None):
        """Scan the user's music folder, then merge in any enabled addons.

        Addon tracks are referenced where they sit in the workshop folder —
        nothing is copied. Returns the total track count.
        """
        self.library = {}

        if not os.path.exists(root_folder):
            console.error(f"Music folder not found: {root_folder}")
            return 0

        console.shen("Cataloguing the music archive...")
        total = 0

        for top_entry in os.listdir(root_folder):
            top_path = os.path.join(root_folder, top_entry)
            if not os.path.isdir(top_path):
                continue

            top_key = top_entry.lower()

            # Skip the assets folder (handled by audio_engine directly)
            if top_key == "assets":
                continue

            # Music state folders (base + _loop + stingers)
            if top_key in ALL_KNOWN:
                tracks = _scan_audio_files(top_path)
                self.library[top_key] = tracks
                if tracks:
                    console.debug(f"{top_key}: {len(tracks)} tracks")
                    total += len(tracks)

        total += self._merge_addons(addons or [])

        console.shen(f"Archive loaded. {total} tracks standing by.")
        self._build_manifest()
        return total

    def _merge_addons(self, addons):
        """Fold each enabled addon's declared folders into the library.

        The user's own music folder is scanned first and wins every collision:
        if they've dropped in a track with the same filename an addon provides,
        theirs is the one that plays. Duplicates between addons resolve in
        scan order (alphabetical by name), which at least makes it stable.

        Filename is the dedupe key rather than the full path, because the
        realistic collision is the same song shipped by two packs — and
        because users who ran an older version still have copies of addon
        tracks sitting in their own folder from back when packs were imported
        by copying.
        """
        added = 0
        for addon in addons:
            if not addon.enabled:
                continue
            addon.track_count = 0
            for state_key, src_dir in addon.source_dirs():
                existing = self.library.setdefault(state_key, [])
                seen = {t["name"].lower() for t in existing}
                for track in _scan_audio_files(src_dir, source=addon.name):
                    if track["name"].lower() in seen:
                        console.debug(
                            f"  {addon.name}: '{track['name']}' already in "
                            f"{state_key} — skipping duplicate.")
                        continue
                    seen.add(track["name"].lower())
                    existing.append(track)
                    addon.track_count += 1
                    added += 1
            if addon.track_count:
                console.debug(f"addon '{addon.name}': {addon.track_count} tracks")
        return added

    def _build_manifest(self):
        """Build a flat ID-indexed manifest for UI track selection."""
        self.manifest = []
        tid = 0
        for top_key in sorted(self.library.keys()):
            tracks = self.library[top_key]
            if not isinstance(tracks, list):
                continue
            for track in tracks:
                self.manifest.append({
                    "id": tid, "state": top_key,
                    "name": track["name"], "path": track["path"],
                })
                tid += 1

    def find_track_by_id(self, track_id):
        """Find a track by its manifest ID."""
        for entry in self.manifest:
            if entry["id"] == track_id:
                return entry
        return None

    def resolve_playlist(self, top, use_loop=False, use_radio=False):
        """Resolve state to a track list.

        When use_radio is True, try the shared state_radio folder first.
        If state_radio is empty, fall back to the state's own folder.

        When use_loop is True, try the _LOOP folder first.
        If _LOOP folder is empty, fall back to the regular folder.

        Returns [] if no tracks found — the engine handles all
        cross-state fallback logic via settings.fallbacks.
        """
        if use_radio:
            radio_tracks = self.library.get(RADIO_STATE, [])
            if radio_tracks:
                return radio_tracks
            # state_radio empty → fall through to regular folder

        if use_loop:
            loop_key = top + "_loop"
            loop_tracks = self.library.get(loop_key, [])
            if loop_tracks:
                return loop_tracks
            # _LOOP empty → fall through to regular folder

        return self.library.get(top, [])

    def resolve_radio_playlist(self, top, source):
        """Track list for the Radio Mode button (Avenger only).

        The state's _LOOP folder (STATE_AVENGER_LOOP) is deliberately NOT
        consulted here. Radio Mode overrides it: when the button is on, the
        Avenger plays the station, not the loop track, regardless of what the
        Loop Track checkbox in Effects says. XiPodEngine._should_loop refuses
        to repeat for the same reason.

        `source` decides where the tracks come from:
          "radio" — STATE_RESISTANCE_RADIO only. Falls back to the state's
                    own folder if the radio folder is empty, so switching
                    Radio Mode on before you've filled it isn't silence.
          "state" — the state's own folder only. No fallback: you asked for
                    this folder specifically, and an empty one means the
                    game's own music takes over, same as it would normally.
          "both"  — both folders pooled. The engine shuffles the combined
                    list, so a finished track can be followed by one from
                    either folder.
        """
        radio_tracks = self.library.get(RADIO_STATE, [])
        own_tracks = self.library.get(top, [])

        if source == RADIO_SOURCE_STATE:
            return own_tracks
        if source == RADIO_SOURCE_BOTH:
            return radio_tracks + own_tracks
        return radio_tracks or own_tracks

    def export_ini(self, log_path, settings_lines, prefer_existing=True):
        """Write XComXiPod.ini with settings + track manifest.

        `prefer_existing` decides who wins a key both sides have an opinion on:

          True  (startup/rescan) — the FILE wins. The player may have changed
                settings in-game through MCM since we last looked, and those
                shouldn't be stomped just because we booted.
          False (saving)         — OUR settings win. The user just changed
                something in the GUI; deferring to the old file value here is
                what made every toggle appear to "not persist" — the save
                dutifully rewrote the ini with the value it was trying to
                replace.

        Keys we hold no opinion on (CurrentScreenType, anything a newer mod
        version writes) are preserved either way.
        """
        base_dir = os.path.dirname(os.path.dirname(log_path))
        config_dir = os.path.join(base_dir, "Config")

        if not os.path.exists(config_dir):
            console.warn("XCOM Config folder not found. UI track list won't generate.")
            return

        ini_path = os.path.join(config_dir, "XComXiPod.ini")

        # Load defaults from xipod_defaults.json
        default_settings = self._load_ini_defaults()

        # Read ALL existing settings to preserve user changes — including
        # keys we don't know about (UserPresetN, CurrentScreenType, or
        # anything a newer mod version writes). Dropping unknown keys here
        # would wipe game-side state on every Anarchy Radio FM start.
        existing_settings = {}
        if os.path.exists(ini_path):
            try:
                with open(ini_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        stripped = line.strip()
                        if ('=' in stripped and not stripped.startswith('TrackList')
                                and not stripped.startswith('[') and not stripped.startswith(';')):
                            key = stripped.split('=', 1)[0].strip()
                            existing_settings[key] = stripped
            except Exception:
                pass

        settings_by_key = {}
        for sl in settings_lines:
            k = sl.split('=', 1)[0].strip()
            settings_by_key[k] = sl

        # Merge over the union of keys: existing > settings_lines > defaults.
        # Order: defaults first (stable layout), then any extra keys.
        final_settings = {}
        ordered_keys = list(default_settings)
        ordered_keys += [k for k in settings_by_key if k not in default_settings]
        ordered_keys += [k for k in existing_settings
                         if k not in default_settings and k not in settings_by_key]
        for key in ordered_keys:
            if key.startswith("UserPreset"):
                # Python owns preset contents (xipod_presets.json) — the
                # game only round-trips these lines and may write back
                # stale values, so our fresh copy wins. Cleared slots
                # (no settings line) are dropped.
                if key in settings_by_key:
                    final_settings[key] = settings_by_key[key]
                continue
            if prefer_existing and key in existing_settings:
                final_settings[key] = existing_settings[key]
            elif key in settings_by_key:
                final_settings[key] = settings_by_key[key]
            elif key in existing_settings:
                # Saving, but we have no opinion on this key — keep the file's
                # value rather than resetting it to the shipped default.
                final_settings[key] = existing_settings[key]
            else:
                final_settings[key] = f"{key}={default_settings[key]}"

        try:
            with open(ini_path, 'w', encoding='utf-8') as f:
                f.write("[AnarchyRadioFM.XiPod_Settings]\n")
                for setting_line in final_settings.values():
                    f.write(setting_line + "\n")
                f.write("\n")

                f.write("[AnarchyRadioFM.XiPod_UI]\n")
                for entry in self.manifest:
                    # Strip file extension for cleaner display in the UI.
                    # Strip quotes and pipes — both break the UC-side parse.
                    display_name = os.path.splitext(entry['name'])[0]
                    safe_name = display_name.replace('"', '').replace('|', '-')
                    safe_state = entry['state'].replace('"', '').replace('|', '-')
                    f.write(f'TrackList="{entry["id"]}|{safe_state}|{safe_name}"\n')
            console.debug(f"Manifest exported: {ini_path}")
        except Exception as e:
            console.warn(f"Manifest write failed: {e}")

    @staticmethod
    def _load_ini_defaults():
        """Read ini_defaults from xipod_defaults.json and return as {key: "str_value"} dict.
        UE3 INI format needs bools as True/False and numbers as strings."""
        try:
            with open(_DEFAULTS_PATH, 'r', encoding='utf-8') as f:
                raw = json.load(f).get("ini_defaults", {})
        except Exception as e:
            console.warn(f"Could not load xipod_defaults.json: {e}")
            raw = {}

        result = {}
        for k, v in raw.items():
            if k.startswith("_"):
                continue
            if isinstance(v, bool):
                result[k] = "True" if v else "False"
            else:
                result[k] = str(v)
        return result
