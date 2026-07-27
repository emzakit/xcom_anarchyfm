"""Music addons — Workshop music packs, discovered and played in place.

A music addon is any Workshop mod folder containing a `*_xipod.json`
descriptor. The descriptor maps game states to folders of audio files inside
that mod. See MODDING_GUIDE.md for the authoring side.

Addons used to be *copied* into the user's music folder on startup. They
aren't any more, for two reasons:

  * Size. A single station-rip pack runs to hundreds of megabytes; a few of
    them and you've duplicated gigabytes onto the user's drive for nothing.
  * You can't un-copy. Once a pack's files are sitting in the music folder
    they're indistinguishable from the user's own tracks, so "turn this addon
    off" is impossible without guessing which files came from where.

So tracks are referenced where they sit in the workshop folder, and each one
remembers which addon it came from. Turning an addon off just drops it from
the next scan.

Enabled/disabled state lives in xipod_config.json under "addons", keyed by
the mod's workshop folder id. Anything not in that map is treated as enabled:
subscribing to a pack should just work, without a visit to a settings screen.
"""

import json
import os

import console


# Descriptor filenames end with this. Matches the modding guide.
DESCRIPTOR_SUFFIX = "_xipod.json"


class Addon:
    """One discovered music pack."""

    def __init__(self, addon_id, root, descriptor_path, data):
        self.id = addon_id                  # workshop folder name (stable id)
        self.root = root                    # absolute path to the mod folder
        self.descriptor_path = descriptor_path

        self.name = (data.get("name") or addon_id).strip()
        self.author = (data.get("author") or "").strip()
        self.description = (data.get("description") or "").strip()

        # Genres are free-form tags. Accept a list or a comma-separated
        # string, because authors will absolutely write both.
        raw_genres = data.get("genres") or data.get("genre") or []
        if isinstance(raw_genres, str):
            raw_genres = [g for g in raw_genres.split(",")]
        self.genres = sorted({g.strip() for g in raw_genres if str(g).strip()})

        self.folders = data.get("folders") or {}   # STATE_NAME -> relative path

        self.enabled = True                 # overwritten from config by scan()
        self.track_count = 0                # filled in by the library scan

    def genre_text(self):
        return ", ".join(self.genres) if self.genres else "—"

    def source_dirs(self, warn=True):
        """Yield (canonical_state_key, absolute_dir) for each declared folder.

        Skips anything that isn't a real state folder or that points outside
        the mod root — a descriptor is untrusted input from the workshop, and
        "../../../Windows" is not a music folder.

        `warn=False` for UI callers, which re-query this on every redraw and
        would otherwise fill the comms log with the same complaint.
        """
        from library import ALL_KNOWN

        mod_root = os.path.normpath(self.root)
        for state_name, rel in self.folders.items():
            key = str(state_name).strip().lower()
            if key not in ALL_KNOWN:
                if warn:
                    console.warn(f"  {self.name}: unknown state '{state_name}' — skipping.")
                continue

            src = os.path.normpath(os.path.join(mod_root, str(rel)))
            if not src.lower().startswith(mod_root.lower() + os.sep) and src.lower() != mod_root.lower():
                if warn:
                    console.warn(f"  {self.name}: '{rel}' escapes the mod folder — skipping.")
                continue
            if not os.path.isdir(src):
                continue
            yield key, src

    def folders_resolved(self):
        """The state keys that actually resolve to a real folder on disk."""
        return [key for key, _ in self.source_dirs(warn=False)]


def _read_descriptor(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception as e:
        console.warn(f"Couldn't read {os.path.basename(path)}: {e}")
        return None


def scan(workshop_folder, enabled_map=None):
    """Find every music addon in the workshop folder.

    Only looks one level deep — descriptors live in each mod's root, and a
    full walk over thousands of workshop mods made startup crawl.

    Returns a list of Addon, sorted by name.
    """
    enabled_map = enabled_map or {}
    addons = []

    if not workshop_folder or not os.path.isdir(workshop_folder):
        return addons

    try:
        entries = os.listdir(workshop_folder)
    except OSError as e:
        console.warn(f"Couldn't read workshop folder: {e}")
        return addons

    for entry in entries:
        mod_root = os.path.join(workshop_folder, entry)
        if not os.path.isdir(mod_root):
            continue
        try:
            files = os.listdir(mod_root)
        except OSError:
            continue

        for fname in files:
            if not fname.lower().endswith(DESCRIPTOR_SUFFIX):
                continue
            path = os.path.join(mod_root, fname)
            data = _read_descriptor(path)
            if data is None:
                continue
            addon = Addon(entry, mod_root, path, data)
            # Absent from the map = enabled. Subscribing should just work.
            addon.enabled = bool(enabled_map.get(entry, True))
            addons.append(addon)
            break   # one descriptor per mod

    addons.sort(key=lambda a: a.name.lower())
    return addons


def load_enabled_map(config_path):
    """Read the {addon_id: bool} enable map out of xipod_config.json."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return {}
    raw = cfg.get("addons") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): bool(v) for k, v in raw.items()}


def save_enabled_map(config_path, enabled_map):
    """Write the enable map back, preserving everything else in the file."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    cfg["addons"] = {str(k): bool(v) for k, v in enabled_map.items()}
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        console.warn(f"Couldn't save addon settings: {e}")
