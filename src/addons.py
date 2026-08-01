"""Music addons — Workshop music packs, discovered and played in place.

A music addon is any Workshop mod folder containing an `xipod_settings.json`
descriptor. The descriptor maps game states to folders of audio files inside
that mod. See the Making a music pack guide in the wiki for the authoring
side.

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


# What marks a folder as a music pack.
#
# One fixed filename, so building a pack means dropping the template in and
# editing it — no renaming to match your mod, and no way to get the rename
# subtly wrong and end up with a pack the app can't see. It's also cheaper to
# find: an exact name is a single stat, where a suffix means listing every
# candidate folder's contents.
DESCRIPTOR_NAME = "xipod_settings.json"

# The original scheme, `<ModName>_xipod.json`. Still honoured so packs
# published before the change keep working — there is no upside to breaking
# someone's uploaded mod over a filename.
DESCRIPTOR_SUFFIX = "_xipod.json"


# Test addons get their id prefixed so they can never collide with a workshop
# id, and so enabling a local copy doesn't silently flip the published one.
TEST_ID_PREFIX = "test::"


class Addon:
    """One discovered music pack."""

    def __init__(self, addon_id, root, descriptor_path, data, is_test=False):
        self.id = addon_id                  # workshop folder name (stable id)
        self.root = root                    # absolute path to the mod folder
        self.descriptor_path = descriptor_path
        # Came from the local testing folder rather than the Workshop.
        self.is_test = is_test

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


def _find_descriptor(folder):
    """The descriptor file directly inside `folder`, or None.

    Checks the fixed name first — one stat, and it's what every pack built
    from the current template uses. Only falls back to scanning for the old
    `*_xipod.json` suffix when that misses.
    """
    fixed = os.path.join(folder, DESCRIPTOR_NAME)
    if os.path.isfile(fixed):
        return fixed

    try:
        for fname in sorted(os.listdir(folder)):
            if fname.lower().endswith(DESCRIPTOR_SUFFIX):
                return os.path.join(folder, fname)
    except OSError:
        pass
    return None


# How far to search inside a folder someone placed by hand. A ModBuddy
# solution wraps the project in another folder of the same name, so a freshly
# built pack sits one level lower than a subscribed one; a little slack past
# that costs nothing and saves a "why isn't it showing up".
_HAND_PLACED_DEPTH = 3


def _is_workshop_id(name):
    """True for a folder Steam created — those are always the numeric id."""
    return name.isdigit()


def _scan_root(root, enabled_map, is_test, label, depth_for):
    """Collect addons from a folder of mod folders.

    `depth_for(entry_name)` says how many levels to search beneath that
    top-level entry. That's per-entry rather than global because the workshop
    folder holds two different things:

      * Folders Steam made, named after the numeric workshop id. The
        descriptor is always in the root of those, and a deep walk over
        thousands of subscribed mods is what made startup crawl.
      * Folders someone dropped in by hand, which are named whatever they
        liked and may well be a nested ModBuddy project.

    Descending only into the second kind gets hand-placed packs working for
    free — a real subscribed mod is never searched any deeper than before.
    """
    found = []
    if not root or not os.path.isdir(root):
        return found

    try:
        queue = [(os.path.join(root, e), depth_for(e))
                 for e in sorted(os.listdir(root))]
    except OSError as e:
        console.warn(f"Couldn't read {label}: {e}")
        return found

    while queue:
        folder, remaining = queue.pop(0)
        if not os.path.isdir(folder):
            continue

        descriptor = _find_descriptor(folder)
        if descriptor:
            data = _read_descriptor(descriptor)
            if data is not None:
                entry = os.path.basename(folder)
                addon_id = (TEST_ID_PREFIX + entry) if is_test else entry
                addon = Addon(addon_id, folder, descriptor, data, is_test=is_test)
                # Absent from the map = enabled. Dropping a pack in should
                # just work, without a trip to a settings screen first.
                addon.enabled = bool(enabled_map.get(addon_id, True))
                found.append(addon)
            # Found the pack — its own subfolders are music, not more packs.
            continue

        if remaining > 1:
            try:
                queue.extend((os.path.join(folder, e), remaining - 1)
                             for e in sorted(os.listdir(folder)))
            except OSError:
                pass

    return found


def scan(workshop_folder, enabled_map=None, test_folder=""):
    """Find every music addon in the workshop folder, plus any being tested.

    Only looks one level deep — descriptors live in each mod's root, and a
    full walk over thousands of workshop mods made startup crawl.

    `test_folder` is the optional local folder a pack author drops an
    in-progress mod into, so it can be played in-game before it goes anywhere
    near the Workshop. Same layout, same descriptor; the only difference is
    where it came from.

    Returns a list of Addon, sorted by name, with tested packs first — they're
    the ones being actively worked on, so they belong at the top of the list.
    """
    enabled_map = enabled_map or {}

    addons = _scan_root(
        workshop_folder, enabled_map, False, "workshop folder",
        # Subscribed mods keep the old shallow scan; anything dropped in by
        # hand gets searched properly. See _scan_root.
        depth_for=lambda name: 1 if _is_workshop_id(name) else _HAND_PLACED_DEPTH,
    )
    tested = _scan_root(
        test_folder, enabled_map, True, "addon test folder",
        depth_for=lambda name: _HAND_PLACED_DEPTH,
    )
    if tested:
        console.shen(f"Addon testing: found {len(tested)} local pack(s).")
    addons.extend(tested)

    addons.sort(key=lambda a: (not a.is_test, a.name.lower()))
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


def prune_enabled_map(config_path, known_ids):
    """Forget the on/off setting for packs that aren't installed any more.

    The descriptor is the identity: no `xipod_settings.json` in a folder, no
    pack. A
    remembered setting for something that no longer exists is just noise that
    builds up in the config forever, and it comes back to life confusingly if
    a folder of the same name ever reappears.

    Call this only when the folders were genuinely readable — see
    setup.discover_addons. An unplugged drive looks exactly like every pack
    being uninstalled at once, and that would quietly reset everyone's
    choices.
    """
    current = load_enabled_map(config_path)
    kept = {k: v for k, v in current.items() if k in known_ids}
    if kept == current:
        return
    dropped = sorted(set(current) - set(kept))
    save_enabled_map(config_path, kept)
    console.debug(f"Forgot {len(dropped)} uninstalled addon(s): {', '.join(dropped)}")


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
