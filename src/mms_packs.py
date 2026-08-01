"""Discovery of other people's MMS music packs.

Anarchy Radio FM and an MMS music pack can both claim the same screen, and
when they do, MMS picks between them at random:

    foreach idxs(idx)
        if (FallbackSongs.Find(MusicDefs[idx].MusicID) == INDEX_NONE)
            nonfallbackidxs.AddItem(idx);
    Def = MusicDefs[nonfallbackidxs[Rand(nonfallbackidxs.Length)]];

MMS registers its own stock music in FallbackSongs so it loses that draw, but
a third-party pack isn't in that list, so a pack and our silence cue end up as
equal contenders and the winner changes from session to session.

The fix is to use the same mechanism MMS uses on itself: for the states
Anarchy Radio FM is actually covering, register the pack's definitions as
fallbacks too. The draw is then over a single candidate and the outcome is
settled. States we aren't covering are left alone, so the pack plays there
exactly as it would without us — which is the whole point of running both.

Reading, not writing: nothing here touches another mod's files.
"""

import json
import os
import re

import console


# The mod ids listed in XComModOptions.ini are the .XComMod filenames, minus
# the extension.
_MOD_MARKER = ".xcommod"

# Ours and MMS's own definitions must never be registered as fallbacks —
# ours because it would silence us, MMS's because it already is one.
_SKIP_MODS = {"anarchyradiofm", "musicmoddingsystem"}

# eSSG_* group -> the toggle key that covers it. Matched by prefix, because
# packs are inconsistent about the chapter suffix: MMS ships eSSG_Chapter01
# but the Halo pack writes plain eSSG_Chapter.
_GROUP_PREFIXES = [
    ("essg_chapter",              "avenger"),
    ("essg_customobjective",      "avenger"),
    ("essg_geoscape",             "geoscape"),
    ("essg_squadselect",          "squadselect"),
    ("essg_afteractionflawless",  "victory"),
    ("essg_afteractioncasualties","victory"),
    ("essg_afteractionloss",      "defeat"),
    ("essg_loss",                 "defeat"),
]

_ACTIVE_MOD_RE = re.compile(r"^\s*ActiveMods\s*=\s*(\S+)", re.IGNORECASE)
_MUSIC_ID_RE = re.compile(r'MusicID\s*=\s*"?([A-Za-z0-9_]+)"?')
_GROUP_RE = re.compile(r"Group\s*=\s*(eSSG_[A-Za-z0-9_]*)", re.IGNORECASE)
_DEF_ID_RE = re.compile(r'ID\s*=\s*"?([A-Za-z0-9_]+)"?')
_CUE_PATH_RE = re.compile(r'=\s*"([^"]+)"')


def _toggle_key_for_group(group):
    low = group.lower()
    for prefix, key in _GROUP_PREFIXES:
        if low.startswith(prefix):
            return key
    return None


def active_mod_ids(game_config_folder):
    """Mod ids enabled in XComModOptions.ini, lowercased.

    Only enabled mods count. A pack sitting unsubscribed-but-not-deleted in
    the workshop folder isn't in the game's def list, so registering it as a
    fallback would be noise at best.
    """
    path = os.path.join(game_config_folder or "", "XComModOptions.ini")
    if not os.path.isfile(path):
        console.debug("XComModOptions.ini not found — skipping MMS pack scan.")
        return set()

    found = set()
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = _ACTIVE_MOD_RE.match(line)
                if m:
                    # The list can carry duplicates; a set handles that.
                    found.add(m.group(1).strip().lower())
    except Exception as e:
        console.warn(f"Couldn't read XComModOptions.ini: {e}")
        return set()

    return found


def _logical_lines(path):
    """Yield ini entries with UE3 line continuations folded back together.

    A single +MusicDefs entry is spread over several physical lines ending in
    a backslash, and MusicID and Group sit on different ones — so they have to
    be rejoined before either can be read in context.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.readlines()
    except Exception as e:
        console.debug(f"Couldn't read {path}: {e}")
        return

    buf = ""
    for line in raw:
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        continued = line.endswith("\\")
        if continued:
            # One backslash or two — MMS's own configs use two, and some
            # packs use one.
            line = line.rstrip("\\").rstrip()
        buf = (buf + " " + line) if buf else line
        if not continued:
            yield buf.strip()
            buf = ""
    if buf:
        yield buf.strip()


def _scan_mod_folder(root):
    """Return {toggle_key: set(def ids)} for one mod folder."""
    found = {}

    strategy = os.path.join(root, "Config", "XComStrategySound.ini")
    if os.path.isfile(strategy):
        for entry in _logical_lines(strategy):
            if not entry.lstrip("+").lower().startswith("musicdefs"):
                continue
            gid = _GROUP_RE.search(entry)
            mid = _MUSIC_ID_RE.search(entry)
            if not gid or not mid:
                continue
            key = _toggle_key_for_group(gid.group(1))
            if key:
                found.setdefault(key, set()).add(mid.group(1))

    # The shell is the odd one out: MMS_UISL_UIShell has no MusicID to
    # register, it autogenerates "Shell_Autogenerated_N" from whatever cue
    # paths it finds. So we collect the cue PATHS here, not ids, and the
    # writer moves them between arrays rather than naming them as fallbacks.
    shell = os.path.join(root, "Config", "XComShellSound.ini")
    if os.path.isfile(shell):
        for entry in _logical_lines(shell):
            if not entry.lstrip("+").lower().startswith("shellcues"):
                continue
            m = _CUE_PATH_RE.search(entry)
            if m:
                found.setdefault("shell_menu", set()).add(m.group(1))

    tactical = os.path.join(root, "Config", "XComTacticalSound.ini")
    if os.path.isfile(tactical):
        for entry in _logical_lines(tactical):
            low = entry.lstrip("+").lower()
            if not (low.startswith("combatdefs") or low.startswith("exploredefs")):
                continue
            did = _DEF_ID_RE.search(entry)
            if did:
                found.setdefault("battle", set()).add(did.group(1))

    return found


_OWN_MOD_MARKER = "anarchyradiofm.xcommod"

# Where a mod folder can live, relative to the steamapps root that the
# workshop folder sits under. These are the paths the GAME itself reads when
# launched directly — a mod installed by hand goes in one of them.
#
# A mod launcher can load from anywhere at all, so this list is the fallback,
# not the answer. See _aml_mod_path.
_LOCAL_MOD_DIRS = [
    os.path.join("common", "XCOM 2", "XComGame", "Mods"),
    os.path.join("common", "XCOM 2", "XCom2-WarOfTheChosen", "XComGame", "Mods"),
]

# Our mod's id as it appears in a launcher's mod list.
_OWN_MOD_ID = "anarchyradiofm"


def _aml_mod_path(game_exe):
    """Our mod's folder according to the Alternative Mod Launcher, or "".

    AML keeps a settings.json beside its exe listing every mod it knows about,
    each with the folder it will actually load and whether it's switched on.
    When someone launches through AML that file is the authority — it can and
    does point somewhere the game would never look on its own, such as the
    SDK's ModBuddy output for anyone who builds the mod themselves.

    Worth reading rather than guessing: writing the silencing settings into a
    copy the launcher ignores leaves a correct-looking file on disk that does
    absolutely nothing, which is a miserable thing to diagnose.
    """
    if not game_exe:
        return ""

    settings = os.path.join(os.path.dirname(os.path.abspath(game_exe)),
                            "settings.json")
    if not os.path.isfile(settings):
        return ""      # not AML, or a layout we don't recognise

    try:
        with open(settings, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as e:
        console.debug(f"Couldn't read the launcher's settings.json: {e}")
        return ""

    try:
        groups = (data.get("Mods") or {}).get("Entries") or {}
        for group in groups.values():
            for mod in (group.get("Entries") or []):
                if str(mod.get("ID", "")).lower() != _OWN_MOD_ID:
                    continue
                # Deliberately ignores whether the launcher has the mod ticked
                # on. Someone toggling mods around while testing shouldn't get
                # nagged, and writing the settings into a folder that isn't
                # loaded right now costs nothing — it's simply correct already
                # when they switch it back on.
                path = mod.get("Path") or ""
                if path and os.path.isdir(path):
                    return path
                console.warn(f"Launcher points at a folder that isn't there: {path}")
    except Exception as e:
        console.debug(f"Couldn't parse the launcher's mod list: {e}")

    return ""


def steamapps_root(path):
    """The steamapps folder `path` sits under, or "".

    Works from the workshop folder, the game exe, anything inside a Steam
    library — they all hang off the same root, so one configured path locates
    the rest of the install.
    """
    if not path:
        return ""
    current = os.path.abspath(path)
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            return ""
        if os.path.basename(current).lower() == "steamapps":
            return current
        current = parent


def _mod_containers(workshop_folder):
    """Folders that may hold mod folders, derived from the workshop path.

    Steam's layout puts the workshop content and the game install under the
    same steamapps root, so one configured path locates both without asking
    the user for a second one.
    """
    out = []
    if workshop_folder and os.path.isdir(workshop_folder):
        out.append(workshop_folder)

    if not workshop_folder:
        return out

    # <steamapps>/workshop/content/268500 -> <steamapps>
    steamapps = os.path.abspath(workshop_folder)
    for _ in range(3):
        steamapps = os.path.dirname(steamapps)

    for rel in _LOCAL_MOD_DIRS:
        path = os.path.join(steamapps, rel)
        if os.path.isdir(path):
            out.append(path)

    return out


def find_own_config_dirs(workshop_folder, extra=None, game_exe=None):
    """Config folders of our own installed mod, where MMS actually reads.

    MMS loads its settings from each mod's own Config folder. The game does
    NOT mirror mod config files into the user's Documents config directory —
    XComSkyrangerSound.ini, which MMS ships and nothing rewrites, never
    appears there — so anything written to Documents for a
    [MusicModdingSystem.*] section is simply not read.

    Steam replaces the workshop copy on every mod update, which is why this
    used to write to Documents instead. That's handled by rewriting on each
    launch rather than by writing somewhere the game ignores.

    `extra` covers installs the workshop folder can't describe, such as a
    local ModBuddy build output, via "mod_config_folder" in xipod_config.json.
    """
    dirs = []

    for path in (extra or []):
        if not path:
            continue
        # Accept either the mod root or its Config folder.
        cfg = path if os.path.basename(path).lower() == "config" \
            else os.path.join(path, "Config")
        if os.path.isdir(cfg):
            dirs.append(cfg)
        else:
            console.warn(f"mod_config_folder not found: {path}")

    # If a launcher told us where it loads the mod from, that settles it —
    # nothing found by searching can be more accurate than the thing doing
    # the loading.
    launcher_path = _aml_mod_path(game_exe)
    if launcher_path:
        cfg = os.path.join(launcher_path, "Config")
        if os.path.isdir(cfg):
            console.debug(f"Mod folder per the launcher: {launcher_path}")
            dirs.append(cfg)

    for container in _mod_containers(workshop_folder):
        try:
            entries = os.listdir(container)
        except Exception:
            continue
        for entry in entries:
            root = os.path.join(container, entry)
            if not os.path.isdir(root):
                continue
            try:
                names = os.listdir(root)
            except Exception:
                continue
            for f in names:
                if f.lower() == _OWN_MOD_MARKER:
                    cfg = os.path.join(root, "Config")
                    if os.path.isdir(cfg):
                        dirs.append(cfg)
                    break

    # Preserve order, drop duplicates.
    seen, out = set(), []
    for d in dirs:
        key = os.path.normcase(os.path.abspath(d))
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def find_pack_defs(workshop_folder, game_config_folder):
    """Definition ids belonging to enabled third-party MMS packs.

    Returns {toggle_key: sorted list of ids}. Empty when there is nothing to
    scan, which leaves the generated config exactly as it was before.
    """
    if not workshop_folder or not os.path.isdir(workshop_folder):
        return {}

    active = active_mod_ids(game_config_folder)
    if not active:
        return {}

    result = {}
    try:
        entries = os.listdir(workshop_folder)
    except Exception as e:
        console.warn(f"Couldn't list workshop folder: {e}")
        return {}

    for entry in entries:
        root = os.path.join(workshop_folder, entry)
        if not os.path.isdir(root):
            continue

        # A mod folder identifies itself by its .XComMod file, whose name is
        # the id used in XComModOptions.ini.
        mod_id = None
        try:
            for f in os.listdir(root):
                if f.lower().endswith(_MOD_MARKER):
                    mod_id = os.path.splitext(f)[0]
                    break
        except Exception:
            continue

        if not mod_id:
            continue
        low = mod_id.lower()
        if low not in active or low in _SKIP_MODS:
            continue

        defs = _scan_mod_folder(root)
        if not defs:
            continue
        console.debug(
            f"MMS pack detected: {mod_id} "
            f"({sum(len(v) for v in defs.values())} defs across {', '.join(sorted(defs))})"
        )
        for key, ids in defs.items():
            result.setdefault(key, set()).update(ids)

    return {k: sorted(v) for k, v in result.items() if v}
