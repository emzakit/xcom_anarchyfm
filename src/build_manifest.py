"""build.json — what a build contains, and proof it arrived intact.

One file written into the root of every release build, listing its version and
a SHA-256 for every file in it. Three things read it:

  * `make_release.py`, which writes it.
  * `updater.stage`, which verifies a download against it BEFORE anything is
    copied over someone's install. The old check was "the size matches and it
    is a zip", which a corrupted-but-right-size download passes happily.
  * The app at startup, which compares the manifest's version against the
    version compiled into it. Those disagreeing is the signature of a
    half-applied update — previously invisible, and the reason a silent no-op
    looked exactly like a successful one.

Deliberately NOT a list of files for the updater to go and fetch. Robocopy
walks the tree perfectly well on its own, and the _internal mirror guarantees
an exact match; a hand-maintained file list would be a second source of truth
that silently misses things the day it drifts. This is for verification only.
"""

import hashlib
import json
import os

MANIFEST_NAME = "build.json"

# Written by the app after install, so they're absent from a fresh build and
# must never count as corruption. Same list the updater refuses to overwrite.
_USER_FILES = {"xipod_config.json", "xipod_presets.json", ".spotify_cache.json"}

_CHUNK = 1024 * 1024


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _walk(build_dir):
    """Every file in the build, as paths relative to its root, forward-slashed.

    Forward slashes so a manifest written on one machine reads the same on
    another, and so the keys are stable if this ever runs anywhere but Windows.
    """
    for root, _dirs, files in os.walk(build_dir):
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, build_dir).replace(os.sep, "/")
            if rel == MANIFEST_NAME or os.path.basename(rel) in _USER_FILES:
                continue
            yield rel, full


def build(build_dir, app_version, built_at=None):
    """Compute the manifest for a finished build. Doesn't write anything."""
    files = {}
    for rel, full in _walk(build_dir):
        files[rel] = {"size": os.path.getsize(full), "sha256": sha256(full)}
    return {
        "app": "Anarchy Radio FM",
        "version": app_version,
        "built": built_at or "",
        "files": dict(sorted(files.items())),
    }


def write(build_dir, app_version, built_at=None):
    """Write build.json into the root of a finished build. Returns its path."""
    manifest = build(build_dir, app_version, built_at)
    path = os.path.join(build_dir, MANIFEST_NAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return path


def read(build_dir):
    """Load build.json from a build folder, or None if it isn't there.

    Never raises. A build without a manifest is a build from before this
    existed, and must keep working exactly as it did.
    """
    path = os.path.join(build_dir, MANIFEST_NAME)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def verify(build_dir, manifest=None):
    """Check a build against its manifest. Returns (ok, problems).

    `problems` is a list of human-readable strings, so a caller can put the
    actual failing filenames in front of someone rather than "verification
    failed". Returns (True, []) when there's no manifest to check against —
    absence of proof isn't proof of corruption, and older builds have none.
    """
    manifest = manifest or read(build_dir)
    if not manifest:
        return True, []

    files = manifest.get("files")
    if not isinstance(files, dict):
        return False, [f"{MANIFEST_NAME} has no usable file list."]

    problems = []
    for rel, want in sorted(files.items()):
        if not isinstance(want, dict):
            continue
        full = os.path.join(build_dir, rel.replace("/", os.sep))
        if not os.path.isfile(full):
            problems.append(f"missing: {rel}")
            continue
        size = want.get("size")
        if isinstance(size, int) and os.path.getsize(full) != size:
            problems.append(f"wrong size: {rel}")
            continue
        digest = want.get("sha256")
        if digest and sha256(full) != digest:
            problems.append(f"corrupt: {rel}")

    return (not problems), problems


def installed_version(install_dir):
    """The version recorded in an install's build.json, or "" if unknown."""
    manifest = read(install_dir)
    return str((manifest or {}).get("version") or "")
