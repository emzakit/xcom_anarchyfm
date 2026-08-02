"""Anarchy Radio FM Engine Settings — toggles, volumes, effects config, INI I/O."""

import json
import os
import console
import state_schema


def _get_toggle_key(top_state):
    """Map a top-level state string to its toggle/volume key.

    Explore and combat both answer to "battle" — one screen as far as the user
    is concerned, and one bucket as far as MMS silencing is concerned.
    """
    return state_schema.TOGGLE_KEYS.get(top_state)


def _get_loop_key(top_state):
    """Map a state to its loop toggle key. Explore and combat get their own,
    so a single mission phase can loop without the other."""
    return state_schema.LOOP_KEYS.get(top_state)


# A loop key that a broader toggle also switches on. Battle covers the whole
# tactical mission, so its Loop Track box loops explore AND combat, while the
# sub-toggles stay available for looping only one phase.
#
# Without this, bLoopBattle was written to the ini and shown in MCM but read
# by nothing at all: no state maps to the "battle" LOOP key, so the checkbox
# was inert.
_LOOP_MASTERS = dict(state_schema.LOOP_MASTERS)


# ------------------------------------------------------------------ #
#  FX Presets — XCOM-themed effect combinations
#
#  Each preset defines the complete FX chain for a state:
#    radio/reverb flags + all parameter values.
#  "custom" is special: uses individual radio/reverb checkboxes
#  and the global FX slider values instead.
# ------------------------------------------------------------------ #

from paths import resource_path, data_path

# Bundled preset/cinematic defaults (read-only, ships with the app)
_DEFAULTS_PATH = resource_path("xipod_defaults.json")

# User presets live in their own JSON next to xipod_config.json. Python is
# the source of truth: the game's SaveConfig round-trips UserPresetN ini
# lines but writes back the values from ITS launch, so the ini copy can be
# stale and must never override this file.
_PRESETS_PATH = data_path("xipod_presets.json")


def _load_presets_from_defaults():
    """Load preset definitions from xipod_defaults.json."""
    try:
        with open(_DEFAULTS_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f).get("presets", {})
        presets = {"custom": {}}
        for k, v in raw.items():
            if isinstance(v, dict):
                presets[k] = v
        if len(presets) < 2:
            console.warn("No presets in xipod_defaults.json.")
        return presets
    except Exception as e:
        console.warn(f"Could not load presets from xipod_defaults.json: {e}")
        return {"custom": {}}


PRESETS = _load_presets_from_defaults()

# User preset slots — populated from INI at load time.
# Each slot stores the same dict shape as a built-in preset.
# Empty dict = slot unused.
USER_PRESETS = {
    "user_1": {},
    "user_2": {},
    "user_3": {},
}

# Display names and internal keys (matched by index).
# User presets are appended after built-ins when their slot is non-empty.
_BUILTIN_NAMES = [
    "Custom", "Clean", "Field Radio",
]
_BUILTIN_KEYS = [
    "custom", "clean", "field_radio",
]

_USER_SLOT_NAMES = ["User Preset 1", "User Preset 2", "User Preset 3"]
_USER_SLOT_KEYS  = ["user_1", "user_2", "user_3"]


def get_preset_lists():
    """Return (names, keys) including any populated user presets."""
    names = list(_BUILTIN_NAMES)
    keys = list(_BUILTIN_KEYS)
    for i, slot_key in enumerate(_USER_SLOT_KEYS):
        if USER_PRESETS.get(slot_key):
            names.append(_USER_SLOT_NAMES[i])
            keys.append(slot_key)
    return names, keys


def _set_user_preset_slot(slot_key, params):
    """Update a user preset slot in the module-level tables (no persist)."""
    global PRESET_NAMES, PRESET_KEYS
    USER_PRESETS[slot_key] = params
    if params:
        PRESETS[slot_key] = params
    else:
        PRESETS.pop(slot_key, None)
    PRESET_NAMES, PRESET_KEYS = get_preset_lists()


def _persist_user_presets():
    """Write populated user preset slots to xipod_presets.json."""
    data = {k: v for k, v in USER_PRESETS.items() if v}
    try:
        with open(_PRESETS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        console.warn(f"Couldn't save user presets: {e}")


def _load_stored_user_presets():
    """Return the stored presets dict, or None if the file is missing/broken."""
    if not os.path.exists(_PRESETS_PATH):
        return None
    try:
        with open(_PRESETS_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: v for k, v in raw.items()
                if k in USER_PRESETS and isinstance(v, dict)}
    except Exception as e:
        console.warn(f"Couldn't read xipod_presets.json: {e}")
        return None


def _overlay_stored_user_presets():
    """Apply xipod_presets.json over the in-memory slots (authoritative).
    Returns True if the file existed and was applied."""
    stored = _load_stored_user_presets()
    if stored is None:
        return False
    for slot_key in _USER_SLOT_KEYS:
        _set_user_preset_slot(slot_key, stored.get(slot_key, {}))
    return True

# Keep module-level references updated for backwards compat
PRESET_NAMES, PRESET_KEYS = get_preset_lists()

# States that support FX presets (same as radio/reverb)
FX_STATES = ["shell_menu", "avenger", "geoscape", "battle", "squadselect"]


class EngineSettings:
    def __init__(self):

        self.toggles = {
            "shell_menu": False,
            "avenger": True,
            "geoscape": False,
            "battle": False,
            "squadselect": False,
            "victory": False,
            "defeat": False,
        }

        self.volumes = {
            "shell_menu": 0.5,
            "avenger": 0.7,
            "geoscape": 0.5,
            "battle": 0.5,
            "squadselect": 0.5,
            "victory": 0.5,
            "defeat": 0.5,
        }

        self.radio = {
            "shell_menu": False, "avenger": False, "geoscape": False,
            "battle": False, "squadselect": False,
        }

        self.reverb = {
            "shell_menu": False, "avenger": True, "geoscape": False,
            "battle": False, "squadselect": False,
        }

        self.loop = {
            "shell_menu": False, "avenger": False, "geoscape": False,
            "battle": False, "squadselect": False,
            "explore": False, "combat": False,
        }

        self.random_start = {
            "shell_menu": False, "avenger": False, "geoscape": False,
            "battle": False, "squadselect": False,
            "explore": False, "combat": False,
        }

        # Per-state FX preset — index maps to preset_index in xipod_defaults.json
        # 0=custom, 1=clean, 2=field_radio, 3-5=user slots
        self.presets = {
            "shell_menu": "custom",
            "avenger": "field_radio",
            "geoscape": "custom",
            "battle": "custom",
            "squadselect": "custom",
        }

        # Global FX parameters — used when a state's preset is "custom"
        self.fx_params = {
            "radiohighpass": 450,      # Hz, radio highpass cutoff
            "radiolowpass": 3000,      # Hz, radio lowpass cutoff
            "reverbroomsize": 80,      # 0-100, maps to 0.0-1.0
            "reverbwet": 20,           # 0-100, wet/dry mix
            "bassboost": 0,            # 0-12 dB low shelf boost at 200Hz (0 = off)
            "chorusdepth": 0,          # 0-100% chorus depth (0 = off)
            "chorusrate": 10,          # 10-50, maps to 1.0-5.0 Hz
            "bitcrush": 16,            # 4-16 bit depth (16 = clean/off)
            "echodelay": 25,           # 0-500 ms delay time (0 = off)
            "echomix": 10,             # 0-100% wet/dry mix for echo
        }

        # Load user presets from xipod_presets.json so they're available
        # even before (or without) an INI load.
        _overlay_stored_user_presets()

    def get_toggle_key(self, top_state):
        return _get_toggle_key(top_state)

    def get_loop_key(self, top_state):
        return _get_loop_key(top_state)

    def is_loop_enabled(self, top_state):
        """Whether this state should repeat its track.

        True if the state's own loop toggle is on, or if a master covering it
        is — see _LOOP_MASTERS. Either one alone is enough, so Battle loops the
        whole mission while Explore/Combat loop just their own phase.
        """
        loop_key = _get_loop_key(top_state)
        if loop_key is None:
            return False
        if self.loop.get(loop_key, False):
            return True
        master = _LOOP_MASTERS.get(loop_key)
        return bool(master and self.loop.get(master, False))

    def effective_volume(self, top_state, master_volume):
        key = _get_toggle_key(top_state)
        state_vol = self.volumes.get(key, 1.0) if key else 1.0
        return master_volume * state_vol

    # ------------------------------------------------------------------ #
    #  FX Resolution — get the actual params/flags for a state
    # ------------------------------------------------------------------ #

    def is_radio_mode(self, top_state):
        """Check if this state should play from the shared radio folder.

        The per-state radio checkbox now controls SOURCE (state_resistance_radio
        folder + always random start), NOT audio effects. Audio FX are
        handled exclusively by presets.
        """
        state_key = _get_toggle_key(top_state)
        if not state_key:
            return False
        return self.radio.get(state_key, False)

    def resolve_fx(self, top_state):
        """Return (use_radio_fx, use_reverb, fx_params) for the given state.

        If the state has a named preset, use the preset's values.
        If "custom", use the per-state reverb checkbox + global sliders.

        NOTE: The per-state radio checkbox no longer controls audio FX —
        it controls folder selection (state_resistance_radio). Only presets
        can enable the radio audio effect (highpass/lowpass/compressor).
        """
        state_key = _get_toggle_key(top_state)
        if not state_key or state_key not in self.presets:
            return False, False, self.fx_params

        preset_key = self.presets.get(state_key, "custom")

        # Look up preset in built-ins and user slots
        all_presets = {**PRESETS, **{k: v for k, v in USER_PRESETS.items() if v}}
        if preset_key == "custom" or preset_key not in all_presets:
            # Custom: radio FX OFF (checkbox controls folder, not FX),
            # reverb from checkbox, params from global sliders.
            use_reverb = self.reverb.get(state_key, False)
            return False, use_reverb, self.fx_params

        # Named preset: self-contained FX chain
        preset = all_presets[preset_key]
        use_radio = preset.get("radio", False)
        use_reverb = preset.get("reverb", False)
        return use_radio, use_reverb, preset

    # ------------------------------------------------------------------ #
    #  Setters
    # ------------------------------------------------------------------ #

    def set_toggle(self, name, enabled):
        key = name.lower()
        if key in self.toggles:
            if self.toggles[key] == enabled:
                return  # No change
            self.toggles[key] = enabled
            status = "ON" if enabled else "OFF"
            console.debug(f"Toggle {key}: {status}")

    def set_volume(self, state_key, level):
        key = state_key.lower()
        if key in self.volumes:
            new_val = max(0.0, min(1.0, level / 100.0))
            if self.volumes[key] == new_val:
                return
            self.volumes[key] = new_val
            console.debug(f"Volume {key}: {level}%")

    def set_radio(self, state_key, enabled):
        key = state_key.lower()
        if key in self.radio:
            if self.radio[key] == enabled:
                return
            self.radio[key] = enabled
            console.debug(f"Radio {key}: {'ON' if enabled else 'OFF'}")

    def set_reverb(self, state_key, enabled):
        key = state_key.lower()
        if key in self.reverb:
            if self.reverb[key] == enabled:
                return
            self.reverb[key] = enabled
            console.debug(f"Reverb {key}: {'ON' if enabled else 'OFF'}")

    def set_loop(self, state_key, enabled):
        key = state_key.lower()
        if key in self.loop:
            if self.loop[key] == enabled:
                return
            self.loop[key] = enabled
            console.debug(f"Loop {key}: {'ON' if enabled else 'OFF'}")

    def set_random_start(self, state_key, enabled):
        key = state_key.lower()
        if key in self.random_start:
            if self.random_start[key] == enabled:
                return
            self.random_start[key] = enabled
            console.debug(f"Random start {key}: {'ON' if enabled else 'OFF'}")

    def should_random_start(self, top_state):
        """Check if this state should start tracks from a random position."""
        key = _get_loop_key(top_state)  # Uses same mapping as loop (explore/combat separate)
        if key is None:
            return False
        return self.random_start.get(key, False)

    def set_fx_param(self, param_name, value):
        key = param_name.lower()
        if key in self.fx_params:
            new_val = int(value)
            if self.fx_params[key] == new_val:
                return
            self.fx_params[key] = new_val
            console.debug(f"FX {key}: {value}")

    def set_preset(self, state_key, preset_name):
        """Set the FX preset for a state. preset_name is the internal key."""
        key = state_key.lower()
        preset_key = preset_name.lower().replace(" ", "_")
        if key not in self.presets:
            console.warn(f"Unknown state for preset: {key}")
            return
        # Accept built-in presets and populated user slots
        all_presets = {**PRESETS, **{k: v for k, v in USER_PRESETS.items() if v}}
        if preset_key not in all_presets:
            console.warn(f"Unknown preset: {preset_name}")
            return
        if self.presets[key] == preset_key:
            return
        self.presets[key] = preset_key
        names, keys = get_preset_lists()
        display = names[keys.index(preset_key)] if preset_key in keys else preset_key
        console.debug(f"Preset {key}: {display}")

    def save_user_preset(self, slot, params=None):
        """Save current custom FX params to a user preset slot (1-3).
        If params is None, uses the current fx_params + radio/reverb from
        the first state that has 'custom' selected."""
        slot_key = f"user_{slot}"
        if slot_key not in USER_PRESETS:
            console.warn(f"Invalid user preset slot: {slot}")
            return
        if params is None:
            # Snapshot current global FX params + radio/reverb from custom state
            params = dict(self.fx_params)
            # Pick radio/reverb from a state using custom, or default to off
            for skey in FX_STATES:
                if self.presets.get(skey) == "custom":
                    params["radio"] = self.radio.get(skey, False)
                    params["reverb"] = self.reverb.get(skey, False)
                    break
            else:
                params["radio"] = False
                params["reverb"] = False
        _set_user_preset_slot(slot_key, params)
        _persist_user_presets()
        console.shen(f"User Preset {slot} saved.")

    def clear_user_preset(self, slot):
        """Clear a user preset slot."""
        slot_key = f"user_{slot}"
        if slot_key in USER_PRESETS:
            _set_user_preset_slot(slot_key, {})
            _persist_user_presets()
            console.debug(f"User Preset {slot} cleared.")

    # ------------------------------------------------------------------ #
    #  INI I/O
    # ------------------------------------------------------------------ #

    def load_from_ini(self, ini_path):
        """Read saved toggle/volume/effect/FX states from XComXiPod.ini."""
        if not os.path.exists(ini_path):
            console.debug("No saved settings found — using defaults.")
            return

        toggle_map = {
            "bEnableShellMenu": "shell_menu", "bEnableAvenger": "avenger",
            "bEnableGeoscape": "geoscape", "bEnableBattle": "battle",
            "bEnableSquadSelect": "squadselect",
            "bEnableVictory": "victory", "bEnableDefeat": "defeat",
        }
        volume_map = {
            "VolumeShellMenu": "shell_menu", "VolumeAvenger": "avenger",
            "VolumeGeoscape": "geoscape", "VolumeBattle": "battle",
            "VolumeSquadSelect": "squadselect",
            "VolumeVictory": "victory", "VolumeDefeat": "defeat",
        }
        radio_map = {
            "bRadioShellMenu": "shell_menu", "bRadioAvenger": "avenger",
            "bRadioGeoscape": "geoscape", "bRadioBattle": "battle",
            "bRadioSquadSelect": "squadselect",
        }
        reverb_map = {
            "bReverbShellMenu": "shell_menu", "bReverbAvenger": "avenger",
            "bReverbGeoscape": "geoscape", "bReverbBattle": "battle",
            "bReverbSquadSelect": "squadselect",
        }
        loop_map = {
            "bLoopShellMenu": "shell_menu", "bLoopAvenger": "avenger",
            "bLoopGeoscape": "geoscape", "bLoopBattle": "battle",
            "bLoopSquadSelect": "squadselect",
            "bLoopExplore": "explore", "bLoopCombat": "combat",
        }
        random_start_map = {
            "bRandomStartShellMenu": "shell_menu", "bRandomStartAvenger": "avenger",
            "bRandomStartGeoscape": "geoscape", "bRandomStartBattle": "battle",
            "bRandomStartSquadSelect": "squadselect",
            "bRandomStartExplore": "explore", "bRandomStartCombat": "combat",
        }
        preset_map = {
            "PresetShellMenu": "shell_menu", "PresetAvenger": "avenger",
            "PresetGeoscape": "geoscape", "PresetBattle": "battle",
            "PresetSquadSelect": "squadselect",
        }
        fx_param_map = {
            "RadioHighpass": "radiohighpass", "RadioLowpass": "radiolowpass",
            "ReverbRoomSize": "reverbroomsize", "ReverbWet": "reverbwet",
            "BassBoost": "bassboost", "ChorusDepth": "chorusdepth",
            "ChorusRate": "chorusrate", "Bitcrush": "bitcrush",
            "EchoDelay": "echodelay", "EchoMix": "echomix",
        }

        try:
            with open(ini_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if '=' not in stripped:
                        continue
                    key, val = stripped.split('=', 1)
                    key, val = key.strip(), val.strip()

                    if key in toggle_map:
                        self.toggles[toggle_map[key]] = val.lower() in ('true', '1', 'yes')
                    elif key in volume_map:
                        try:
                            self.volumes[volume_map[key]] = max(0.0, min(1.0, int(val) / 100.0))
                        except ValueError:
                            pass
                    elif key in radio_map:
                        self.radio[radio_map[key]] = val.lower() in ('true', '1', 'yes')
                    elif key in reverb_map:
                        self.reverb[reverb_map[key]] = val.lower() in ('true', '1', 'yes')
                    elif key in loop_map:
                        self.loop[loop_map[key]] = val.lower() in ('true', '1', 'yes')
                    elif key in random_start_map:
                        self.random_start[random_start_map[key]] = val.lower() in ('true', '1', 'yes')
                    elif key in preset_map:
                        try:
                            idx = int(val)
                            # Fixed index → key mapping (matches UC side)
                            _idx_to_key = [
                                "custom", "clean", "field_radio",
                                "user_1", "user_2", "user_3",
                            ]
                            if 0 <= idx < len(_idx_to_key):
                                self.presets[preset_map[key]] = _idx_to_key[idx]
                        except ValueError:
                            pass
                    elif key in fx_param_map:
                        try:
                            self.fx_params[fx_param_map[key]] = int(val)
                        except ValueError:
                            pass
                    elif key.startswith("UserPreset") and key[-1] in "123":
                        self._parse_user_preset(int(key[-1]), val)

            # User presets: xipod_presets.json is authoritative (the game
            # round-trips stale UserPresetN lines via SaveConfig). If no
            # JSON exists yet but the INI had presets, migrate them.
            if not _overlay_stored_user_presets() and any(USER_PRESETS.values()):
                _persist_user_presets()

            active = [k for k, v in self.toggles.items() if v]
            inactive = [k for k, v in self.toggles.items() if not v]
            console.debug(f"Toggles ON: {active}")
            if inactive:
                console.debug(f"Toggles OFF: {inactive}")

            vol_display = {k: f"{int(v*100)}%" for k, v in self.volumes.items()}
            console.debug(f"Volumes: {vol_display}")

            preset_display = {k: PRESET_NAMES[PRESET_KEYS.index(v)] if v in PRESET_KEYS else v
                              for k, v in self.presets.items()}
            console.debug(f"Presets: {preset_display}")

            radio_on = [k for k, v in self.radio.items() if v]
            reverb_on = [k for k, v in self.reverb.items() if v]
            if radio_on or reverb_on:
                console.debug(f"FX — Radio: {radio_on or 'none'}, Reverb: {reverb_on or 'none'}")
        except Exception as e:
            console.warn(f"Couldn't read saved settings: {e}")

    def get_settings_lines(self):
        """Return INI lines for the settings section."""
        def b(v): return "True" if v else "False"
        def vi(k): return str(int(self.volumes[k] * 100))
        def pi(k):
            preset = self.presets.get(k, "custom")
            # Fixed index mapping matching UC side:
            # 0=custom, 1=clean, 2=field_radio, 3=user_1, 4=user_2, 5=user_3
            idx_map = {
                "custom": 0, "clean": 1, "field_radio": 2,
                "user_1": 3, "user_2": 4, "user_3": 5,
            }
            return str(idx_map.get(preset, 0))

        lines = [
            f"bEnableShellMenu={b(self.toggles['shell_menu'])}",
            f"bEnableAvenger={b(self.toggles['avenger'])}",
            f"bEnableGeoscape={b(self.toggles['geoscape'])}",
            f"bEnableBattle={b(self.toggles['battle'])}",
            f"bEnableSquadSelect={b(self.toggles['squadselect'])}",
            f"bEnableVictory={b(self.toggles['victory'])}",
            f"bEnableDefeat={b(self.toggles['defeat'])}",
            f"VolumeShellMenu={vi('shell_menu')}",
            f"VolumeAvenger={vi('avenger')}",
            f"VolumeGeoscape={vi('geoscape')}",
            f"VolumeBattle={vi('battle')}",
            f"VolumeSquadSelect={vi('squadselect')}",
            f"VolumeVictory={vi('victory')}",
            f"VolumeDefeat={vi('defeat')}",
            f"bRadioShellMenu={b(self.radio['shell_menu'])}",
            f"bRadioAvenger={b(self.radio['avenger'])}",
            f"bRadioGeoscape={b(self.radio['geoscape'])}",
            f"bRadioBattle={b(self.radio['battle'])}",
            f"bRadioSquadSelect={b(self.radio['squadselect'])}",
            f"bReverbShellMenu={b(self.reverb['shell_menu'])}",
            f"bReverbAvenger={b(self.reverb['avenger'])}",
            f"bReverbGeoscape={b(self.reverb['geoscape'])}",
            f"bReverbBattle={b(self.reverb['battle'])}",
            f"bReverbSquadSelect={b(self.reverb['squadselect'])}",
            f"bLoopShellMenu={b(self.loop['shell_menu'])}",
            f"bLoopAvenger={b(self.loop['avenger'])}",
            f"bLoopGeoscape={b(self.loop['geoscape'])}",
            f"bLoopBattle={b(self.loop['battle'])}",
            f"bLoopSquadSelect={b(self.loop['squadselect'])}",
            f"bLoopExplore={b(self.loop['explore'])}",
            f"bLoopCombat={b(self.loop['combat'])}",
            f"bRandomStartShellMenu={b(self.random_start['shell_menu'])}",
            f"bRandomStartAvenger={b(self.random_start['avenger'])}",
            f"bRandomStartGeoscape={b(self.random_start['geoscape'])}",
            f"bRandomStartBattle={b(self.random_start['battle'])}",
            f"bRandomStartSquadSelect={b(self.random_start['squadselect'])}",
            f"bRandomStartExplore={b(self.random_start['explore'])}",
            f"bRandomStartCombat={b(self.random_start['combat'])}",
            f"PresetShellMenu={pi('shell_menu')}",
            f"PresetAvenger={pi('avenger')}",
            f"PresetGeoscape={pi('geoscape')}",
            f"PresetBattle={pi('battle')}",
            f"PresetSquadSelect={pi('squadselect')}",
            f"RadioHighpass={self.fx_params['radiohighpass']}",
            f"RadioLowpass={self.fx_params['radiolowpass']}",
            f"ReverbRoomSize={self.fx_params['reverbroomsize']}",
            f"ReverbWet={self.fx_params['reverbwet']}",
            f"BassBoost={self.fx_params['bassboost']}",
            f"ChorusDepth={self.fx_params['chorusdepth']}",
            f"ChorusRate={self.fx_params['chorusrate']}",
            f"Bitcrush={self.fx_params['bitcrush']}",
            f"EchoDelay={self.fx_params['echodelay']}",
            f"EchoMix={self.fx_params['echomix']}",
        ]
        # Serialize user presets (pipe-delimited key:value pairs)
        for slot in range(1, 4):
            slot_key = f"user_{slot}"
            data = USER_PRESETS.get(slot_key, {})
            if data:
                pairs = "|".join(f"{k}:{v}" for k, v in sorted(data.items()))
                lines.append(f"UserPreset{slot}={pairs}")
        return lines

    def _parse_user_preset(self, slot, raw):
        """Parse a pipe-delimited user preset string from INI.
        Memory-only — the JSON overlay in load_from_ini decides what
        actually sticks, so a stale INI line can't clobber the file."""
        try:
            params = {}
            for pair in raw.split("|"):
                if ":" not in pair:
                    continue
                k, v = pair.split(":", 1)
                k = k.strip()
                v = v.strip()
                if k in ("radio", "reverb"):
                    params[k] = v.lower() in ("true", "1", "yes")
                else:
                    try:
                        params[k] = int(v)
                    except ValueError:
                        params[k] = v
            if params:
                _set_user_preset_slot(f"user_{slot}", params)
                console.debug(f"Loaded User Preset {slot} from INI")
        except Exception as e:
            console.warn(f"Failed to parse User Preset {slot}: {e}")
