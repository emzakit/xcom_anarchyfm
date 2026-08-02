"""Self-update from GitHub Releases.

Checks the repo's latest release, and if it's newer, downloads the app zip and
swaps it over the running install.

The awkward part is that this is a PyInstaller *onedir* build: Windows won't
let a running exe be overwritten. So applying an update is a three-step dance:

  1. Download and extract the new build into a staging folder in %TEMP%.
  2. Write a small .bat that waits for our PID to exit, copies the staged
     files over the install folder, and relaunches us.
  3. Spawn that .bat detached and quit.

The copy is done in two passes, because the install folder holds two very
different kinds of thing:

  * The install ROOT is shared with the user. xipod_config.json, presets, and
    quite possibly their entire music library live here, because the app is
    portable and people unzip it wherever they like. This pass is additive
    (robocopy /E). Mirroring it would delete all of that.

  * _internal/ is generated wholly by PyInstaller and contains nothing the user
    or the app ever writes — data_path() resolves to the root, never here. This
    pass IS a mirror (/MIR), and needs to be.

That second point used to be additive too, which was wrong twice over. Files
dropped between versions lingered forever, so an install accumulated debris
from every version it had ever been. Worse, a onedir exe embeds a PYZ whose
module set has to match the .pyd/.dll files sitting beside it in _internal —
so a half-old _internal isn't untidy, it's a build that was never tested.

Everything here is stdlib. Nothing is executed from the download: we extract a
zip of data files and copy them, and the only thing spawned is a .bat we wrote
ourselves.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import build_manifest
import console
import version
from paths import is_frozen

# Release assets must look like this. Guards against grabbing the mod-file zip
# (AnarchyRadioFM_ModFile_*.zip) or a source archive by mistake.
ASSET_PREFIX = "anarchyradiofm_app"
ASSET_SUFFIX = ".zip"

# The exe that must exist inside a downloaded build for it to be considered
# valid. If this isn't in the zip, it isn't our app and we don't touch it.
EXE_NAME = "AnarchyRadioFM.exe"

# Files that must survive an update no matter what.
_KEEP = ("xipod_config.json", "xipod_presets.json", ".spotify_cache.json")

_UA = f"AnarchyRadioFM/{version.__version__} (+{version.RELEASES_PAGE})"

_ALLOWED_HOSTS = ("github.com", "api.github.com", "objects.githubusercontent.com",
                  "release-assets.githubusercontent.com")


def _host_allowed(url):
    """True only for HTTPS URLs on GitHub's own hosts.

    Parses and compares the hostname rather than substring-matching the URL —
    "https://evil.example/github.com/x" contains the allowed host but is not
    on it.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    return any(host == h or host.endswith("." + h) for h in _ALLOWED_HOSTS)


class Release:
    """A GitHub release we could update to."""

    def __init__(self, data):
        self.version = (data.get("tag_name") or data.get("name") or "").strip()
        self.name = (data.get("name") or self.version).strip()
        self.notes = (data.get("body") or "").strip()
        self.page = data.get("html_url") or version.RELEASES_PAGE
        self.asset_url = ""
        self.asset_name = ""
        self.asset_size = 0

        for asset in data.get("assets") or []:
            name = (asset.get("name") or "")
            low = name.lower()
            if low.startswith(ASSET_PREFIX) and low.endswith(ASSET_SUFFIX):
                url = asset.get("browser_download_url") or ""
                if _host_allowed(url):
                    self.asset_url = url
                    self.asset_name = name
                    self.asset_size = int(asset.get("size") or 0)
                break

    def is_newer(self):
        return version.is_newer(self.version)

    def can_auto_apply(self):
        """Auto-apply needs a matching asset AND a frozen install to write to.
        From source there's nothing sensible to overwrite."""
        return bool(self.asset_url) and is_frozen()


def check(timeout=10):
    """Ask GitHub for the latest release. Returns a Release, or None.

    Never raises — a failed update check must not interfere with playing music.
    """
    req = urllib.request.Request(version.LATEST_API)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", _UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        console.debug(f"Update check failed: {e}")
        return None
    if not isinstance(data, dict):
        return None
    return Release(data)


def download(release, progress=None, timeout=60):
    """Fetch the release zip into a temp file. Returns its path.

    `progress` is called with (bytes_so_far, total_bytes) as it goes.
    Raises on anything that doesn't look right.
    """
    if not _host_allowed(release.asset_url):
        raise ValueError("Download URL is not a GitHub address — refusing.")

    req = urllib.request.Request(release.asset_url)
    req.add_header("User-Agent", _UA)
    req.add_header("Accept", "application/octet-stream")

    tmp_dir = tempfile.mkdtemp(prefix="afm_update_")
    dest = os.path.join(tmp_dir, release.asset_name or "update.zip")

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length") or release.asset_size or 0)
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)

    size = os.path.getsize(dest)
    if release.asset_size and size != release.asset_size:
        raise ValueError(
            f"Download is {size} bytes, expected {release.asset_size}. "
            "Aborting rather than installing a truncated build.")
    if not zipfile.is_zipfile(dest):
        raise ValueError("Download isn't a zip file.")
    return dest


def _safe_extract(zip_path, dest_dir):
    """Extract a zip, refusing any entry that would escape dest_dir.

    Python sanitises absolute paths and "..", but this is an archive pulled off
    the internet and about to be copied over an install directory — worth being
    explicit rather than trusting that to stay true.
    """
    dest_root = os.path.abspath(dest_dir)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            target = os.path.abspath(os.path.join(dest_root, member))
            if target != dest_root and not target.startswith(dest_root + os.sep):
                raise ValueError(f"Zip entry escapes the target folder: {member}")
        zf.extractall(dest_root)
    return dest_root


def _find_build_root(extracted):
    """Locate the folder holding AnarchyRadioFM.exe inside an extracted zip.

    The release zip wraps everything in an AnarchyRadioFM/ folder, but don't
    depend on the name — just go looking for the exe.
    """
    for root, _dirs, files in os.walk(extracted):
        if EXE_NAME.lower() in {f.lower() for f in files}:
            return root
    return ""


def stage(zip_path):
    """Extract an update, verify it, and return the folder to copy from.

    Raises if the archive doesn't contain our app, or if it contains a
    build.json that doesn't match what was actually extracted. Verification
    happens HERE, before a single file is copied over someone's install —
    once the swap starts there's no clean way back.

    A build without a manifest verifies trivially. Older releases have none,
    and refusing to install them would be a worse bug than the one this guards
    against.
    """
    staging = os.path.join(os.path.dirname(zip_path), "staged")
    os.makedirs(staging, exist_ok=True)
    _safe_extract(zip_path, staging)
    build_root = _find_build_root(staging)
    if not build_root:
        raise ValueError(f"{EXE_NAME} not found in the download — not applying it.")

    manifest = build_manifest.read(build_root)
    if manifest:
        ok, problems = build_manifest.verify(build_root, manifest)
        if not ok:
            shown = "\n  ".join(problems[:5])
            more = f"\n  ...and {len(problems) - 5} more" if len(problems) > 5 else ""
            raise ValueError(
                "The download didn't survive the trip intact:\n  "
                f"{shown}{more}\n"
                "Nothing has been changed. Try again, or download it by hand.")
        console.debug(
            f"Update verified: {len(manifest.get('files') or {})} files, "
            f"version {manifest.get('version') or '?'}")
    else:
        console.debug("Update has no build.json — installing without verification.")
    return build_root


def apply_and_restart(build_root, install_dir=None, exe_path=None):
    """Hand off to a helper that swaps the files once we've exited.

    Returns the helper script path. The caller should quit immediately after —
    the helper is waiting on our PID.
    """
    install_dir = os.path.abspath(install_dir or os.path.dirname(sys.executable))
    exe_path = exe_path or sys.executable
    helper_dir = tempfile.mkdtemp(prefix="afm_apply_")
    helper = os.path.join(helper_dir, "apply_update.bat")

    excludes = " ".join(_KEEP)

    # Paths arrive as ARGUMENTS, never baked into the script text. cmd reads a
    # .bat in the console's OEM codepage, so a path written into the file as
    # UTF-8 is misread the moment it leaves ASCII — and "C:\Users\Jörg\Music"
    # is an entirely ordinary thing to have. Arguments come through the
    # process API as UTF-16 and survive intact.
    #
    # The body below is therefore kept strictly ASCII. Do not put an em dash in
    # here: the shipped v2.2-v2.4 script had one, and non-ASCII bytes in a .bat
    # are exactly the kind of thing that works on your machine and not theirs.
    script = f"""@echo off
setlocal
rem Anarchy Radio FM updater - written by the app, not shipped with it.
rem Waits for the running app to exit, swaps the new build in, relaunches.
rem   %1 = new build   %2 = install dir   %3 = exe to relaunch   %4 = staging

set "SRC=%~1"
set "DST=%~2"
set "APP=%~3"
set "STAGING=%~4"
set "LOG=%TEMP%\\anarchyfm_update.log"

echo Anarchy Radio FM update log - %DATE% %TIME% > "%LOG%"
echo   from: %SRC% >> "%LOG%"
echo   to  : %DST% >> "%LOG%"

rem System32 tools by full path. "find" in particular is a byword for being
rem shadowed - Git for Windows, the WSL shims and half the unix ports for
rem Windows all ship one. If the wrong find answers here it errors instead of
rem matching, the loop exits immediately, and robocopy then tries to overwrite
rem an exe that is still running. Silent, and miserable to reproduce.
set "SYS=%SystemRoot%\\System32"

echo Waiting for Anarchy Radio FM to close...
:waitloop
"%SYS%\\tasklist.exe" /FI "PID eq {os.getpid()}" 2>nul | "%SYS%\\find.exe" "{os.getpid()}" >nul
if not errorlevel 1 (
    "%SYS%\\ping.exe" -n 2 127.0.0.1 >nul
    goto waitloop
)

echo Applying update...

rem Pass 1 - the install root, ADDITIVE. Shared with the user: their config,
rem presets and quite possibly their whole music library live here.
echo [pass 1] root, additive >> "%LOG%"
"%SYS%\\robocopy.exe" "%SRC%" "%DST%" /E /R:3 /W:1 /XF {excludes} /XD "%SRC%\\_internal" >> "%LOG%" 2>&1
if errorlevel 8 goto failed

rem Pass 2 - _internal, MIRRORED. Entirely PyInstaller's; the app never writes
rem here. Mirroring clears out files dropped between versions, which an
rem additive copy left behind forever.
if exist "%SRC%\\_internal" (
    echo [pass 2] _internal, mirrored >> "%LOG%"
    robocopy "%SRC%\\_internal" "%DST%\\_internal" /MIR /R:3 /W:1 >> "%LOG%" 2>&1
    if errorlevel 8 goto failed
)

rem Don't relaunch something that isn't there - a missing exe here means the
rem swap went wrong in a way robocopy's exit code didn't cover.
if not exist "%DST%\\{EXE_NAME}" goto failed

echo [done] update applied >> "%LOG%"
start "" "%APP%"
rem Clean up staging on success only; on failure it's the manual fallback.
if not "%STAGING%"=="" rmdir /S /Q "%STAGING%" >nul 2>&1
exit /b 0

:failed
echo [FAILED] >> "%LOG%"
echo.
echo The update could not be applied cleanly.
echo.
echo Anarchy Radio FM has NOT been started, in case the install is
echo half-updated. You can finish it by hand: copy everything from
echo   %SRC%
echo over
echo   %DST%
echo.
echo A log of what happened is at:
echo   %LOG%
echo.
pause
exit /b 1
"""
    # ASCII, so the file is byte-identical under every Windows codepage.
    with open(helper, "w", encoding="ascii", newline="\r\n") as f:
        f.write(script)

    creation = 0
    if sys.platform == "win32":
        creation = getattr(subprocess, "DETACHED_PROCESS", 0) | \
                   getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["cmd", "/c", helper, build_root, install_dir, exe_path,
                      os.path.dirname(build_root)],
                     cwd=helper_dir, creationflags=creation, close_fds=True)
    console.shen("Update staged — closing so it can be applied.")
    return helper


def report_install():
    """Log what version is actually running, and flag a half-applied update.

    The version compiled into the exe and the version in build.json come from
    opposite ends of an update: one from the new exe, one from the new build's
    manifest. They disagree only if the swap didn't finish — which used to be
    completely silent, so "the updater ran and nothing changed" and "the
    updater ran and everything changed" looked identical from the outside.

    Never raises, never blocks startup. Worst case it says nothing.
    """
    running = version.__version__
    if not is_frozen():
        console.debug(f"Anarchy Radio FM {running} (from source)")
        return

    try:
        install_dir = os.path.dirname(sys.executable)
        recorded = build_manifest.installed_version(install_dir)
    except Exception:
        return

    if not recorded:
        console.debug(f"Anarchy Radio FM {running}")
        return

    if version.parse(recorded) == version.parse(running):
        console.debug(f"Anarchy Radio FM {running} (build verified)")
        return

    console.warn(
        f"This install looks half-updated: the app reports {running}, but the "
        f"build alongside it says {recorded}. Re-run the update, or unzip a "
        f"fresh copy over this folder.")


def open_releases_page():
    """Fallback for source installs, or when auto-apply isn't possible."""
    import webbrowser
    webbrowser.open(version.RELEASES_PAGE)
