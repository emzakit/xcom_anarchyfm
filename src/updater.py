"""Self-update from GitHub Releases.

Checks the repo's latest release, and if it's newer, downloads the app zip and
swaps it over the running install.

The awkward part is that this is a PyInstaller *onedir* build: Windows won't
let a running exe be overwritten. So applying an update is a three-step dance:

  1. Download and extract the new build into a staging folder in %TEMP%.
  2. Write a small .bat that waits for our PID to exit, copies the staged
     files over the install folder, and relaunches us.
  3. Spawn that .bat detached and quit.

The copy is deliberately a plain copy-over rather than a mirror. A mirror
(robocopy /MIR) would delete anything not in the new build — which is to say
the user's xipod_config.json, their presets, and their entire music library if
they unzipped the app into their music folder. Stale files from an old version
lingering is a much smaller problem than that.

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
    """Extract an update and return the folder to copy from. Raises if the
    archive doesn't contain our app."""
    staging = os.path.join(os.path.dirname(zip_path), "staged")
    os.makedirs(staging, exist_ok=True)
    _safe_extract(zip_path, staging)
    build_root = _find_build_root(staging)
    if not build_root:
        raise ValueError(f"{EXE_NAME} not found in the download — not applying it.")
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
    script = f"""@echo off
setlocal
rem Anarchy Radio FM updater — written by the app, not shipped with it.
rem Waits for the running app to exit, copies the new build over the install,
rem then relaunches. Deliberately NOT /MIR: mirroring would delete the user's
rem config and any music they keep alongside the exe.

echo Waiting for Anarchy Radio FM to close...
:waitloop
tasklist /FI "PID eq {os.getpid()}" 2>nul | find "{os.getpid()}" >nul
if not errorlevel 1 (
    ping -n 2 127.0.0.1 >nul
    goto waitloop
)

echo Applying update...
robocopy "{build_root}" "{install_dir}" /E /R:3 /W:1 /XF {excludes} >nul
if errorlevel 8 (
    echo.
    echo The update could not be applied automatically.
    echo Your existing install has not been changed.
    echo You can copy the new files over manually from:
    echo   {build_root}
    echo.
    pause
    exit /b 1
)

start "" "{exe_path}"
rem Clean up the staging folder; leave this script's own folder to the OS.
rmdir /S /Q "{os.path.dirname(build_root)}" >nul 2>&1
exit /b 0
"""
    with open(helper, "w", encoding="utf-8") as f:
        f.write(script)

    creation = 0
    if sys.platform == "win32":
        creation = getattr(subprocess, "DETACHED_PROCESS", 0) | \
                   getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["cmd", "/c", helper], cwd=helper_dir,
                     creationflags=creation, close_fds=True)
    console.shen("Update staged — closing so it can be applied.")
    return helper


def open_releases_page():
    """Fallback for source installs, or when auto-apply isn't possible."""
    import webbrowser
    webbrowser.open(version.RELEASES_PAGE)
