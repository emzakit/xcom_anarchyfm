"""Self-update from GitHub Releases.

Checks the repo's latest release, and if it's newer, downloads the app zip and
swaps it over the running install.

The awkward part is that this is a PyInstaller *onedir* build, and Windows will
not let a running exe be overwritten. Every earlier version of this module
tried to work around that by waiting for the app to close and then copying over
the top — and when that went wrong it went wrong in total silence, which is how
an update could appear to succeed and change nothing at all.

It doesn't overwrite anything now. Windows is perfectly happy to RENAME a
running exe, so applying an update is:

  1. Download and extract the new build into a staging folder in %TEMP%.
  2. Verify it against the build.json it ships with, BEFORE touching anything.
  3. Write a .bat that waits for our PID to exit, MOVES the current exe and
     _internal into a version-stamped backup folder, copies the new build into
     the space they left, and starts it.
  4. Spawn that .bat in its own console and quit.

Why a move rather than a copy-over:

  * Nothing is ever overwritten while running, so the failure mode is gone.
  * A move within one volume is instant, whatever the size.
  * Settings, presets and music never move, so there is nothing to migrate and
    nothing to orphan. The install folder and any desktop shortcut keep working.
  * _internal is written into empty space, so files dropped between versions
    can't accumulate — which an additive copy used to allow forever.
  * The backup is a complete, working previous version. Reverting is moving two
    things back, and it stays put until the user deletes it.

_internal is backed up alongside the exe deliberately: it holds the Python
runtime and every DLL the exe loads, and a onedir exe embeds a PYZ whose module
set must match it. An old exe against a new _internal doesn't start, so backing
up one without the other would leave a revert that quietly fails.

Everything here is stdlib. Nothing is executed from the download: we extract a
zip of data files and copy them, and the only thing spawned is a .bat we wrote
ourselves.
"""

import json
import os
import shutil
import stat
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

# What our exe looks like inside a build. Matched as a prefix rather than a
# fixed name so a folder is still recognised whatever the exe ended up called.
EXE_PREFIX = "anarchyradiofm"
EXE_SUFFIX = ".exe"


def find_app_exe(folder):
    """The app exe inside `folder`, or "". Newest-looking name wins."""
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return ""
    matches = [n for n in names
               if n.lower().startswith(EXE_PREFIX)
               and n.lower().endswith(EXE_SUFFIX)]
    if not matches:
        return ""
    # A versioned name beats a bare one, so a folder holding both picks the
    # real build rather than a leftover.
    matches.sort(key=lambda n: ("_v" not in n.lower(), n.lower()))
    return os.path.join(folder, matches[0])

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
    """Locate the folder holding our exe inside an extracted zip.

    The release zip wraps everything in a folder named after the version, but
    don't depend on the name — just go looking for the exe.
    """
    for root, _dirs, _files in os.walk(extracted):
        if find_app_exe(root):
            return root
    return ""


def stage(zip_path, staging_dir=None):
    """Extract an update, verify it, and return the folder to copy from.

    `staging_dir` overrides where it unpacks. The default sits beside the zip,
    which is a temp folder for a real download — but not for anything pointed
    at a zip in dist/, which would then grow a `staged/` folder inside the
    release output.

    Raises if the archive doesn't contain our app, or if it contains a
    build.json that doesn't match what was actually extracted. Verification
    happens HERE, before a single file is copied over someone's install —
    once the swap starts there's no clean way back.

    A build without a manifest verifies trivially. Older releases have none,
    and refusing to install them would be a worse bug than the one this guards
    against.
    """
    staging = staging_dir or os.path.join(os.path.dirname(zip_path), "staged")
    os.makedirs(staging, exist_ok=True)
    _safe_extract(zip_path, staging)
    build_root = _find_build_root(staging)
    if not build_root:
        raise ValueError("No Anarchy Radio FM exe in the download — not applying it.")

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


BACKUP_PREFIX = "_previous_v"


def exe_file_version(exe_path):
    """The version stamped into an exe's Windows resource, or "".

    Only used as a fallback when there's no build.json to read — which means
    any install from before 2.4.1. Without it those back up into a folder
    called "_previous_vunknown", which tells the user nothing at the exact
    moment they're deciding whether it's safe to delete.

    Shelling out to PowerShell rather than taking a dependency: this runs once,
    during an update, and only when the cheaper answer isn't available.
    """
    if not exe_path or sys.platform != "win32" or not os.path.isfile(exe_path):
        return ""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"(Get-Item -LiteralPath '{exe_path}').VersionInfo.FileVersion"],
            capture_output=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return out.stdout.decode("utf-8", "replace").strip()
    except Exception as e:
        console.debug(f"Couldn't read the exe version: {e}")
        return ""


def installed_version_of(install_dir):
    """Best available version for an install: build.json, then the exe."""
    return (build_manifest.installed_version(install_dir)
            or exe_file_version(find_app_exe(install_dir)))


def backup_dir_name(old_version):
    """Folder the outgoing version is moved into. One item, version stamped.

    Windows refuses to overwrite or delete a running exe, but it is perfectly
    happy to RENAME one. So the update moves the old version aside rather than
    fighting it — which is the whole trick. No second install folder, no
    settings to migrate, no music orphaned in a directory nobody deletes, and
    the shortcut on someone's desktop still points at the right file after.

    `_internal` moves with it. That folder is the Python runtime and every DLL
    the exe loads, and an old exe against a new `_internal` will not start — so
    backing up one without the other would leave a revert that quietly fails.
    Moving it aside also means the incoming `_internal` is written into empty
    space, which is what stops stale files accumulating.

    A folder rather than loose `.old` files, and moved rather than zipped:
    a move within one volume is instant whatever the size, while compressing
    ~174 MB would stall every single update for the better part of a minute to
    produce something that gets deleted on next launch anyway.
    """
    return f"{BACKUP_PREFIX}{old_version or 'unknown'}"


def find_backups(install_dir=None):
    """Previous versions parked in an install folder, newest name last."""
    install_dir = os.path.abspath(install_dir or os.path.dirname(sys.executable))
    try:
        entries = sorted(os.listdir(install_dir))
    except OSError:
        return []
    out = []
    for name in entries:
        full = os.path.join(install_dir, name)
        if name.lower().startswith(BACKUP_PREFIX.lower()) and os.path.isdir(full):
            out.append({
                "name": name,
                "path": full,
                "version": name[len(BACKUP_PREFIX):],
                "bytes": _folder_size(full),
            })
    return out


def _folder_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def apply_and_restart(build_root, install_dir=None, exe_path=None):
    """Hand off to a helper that installs the new build once we've exited.

    Returns the helper script path. The caller should quit immediately after —
    the helper is waiting on our PID.
    """
    install_dir = os.path.abspath(install_dir or os.path.dirname(sys.executable))
    helper_dir = tempfile.mkdtemp(prefix="afm_apply_")
    helper = os.path.join(helper_dir, "apply_update.bat")

    new_exe_name = os.path.basename(find_app_exe(build_root) or "")
    if not new_exe_name:
        raise ValueError("Staged build has no exe to launch.")

    # build.json first, then the exe's own resource, then the running version.
    # The last one is right when the app updates itself — we ARE the old
    # version — but wrong in the test harness, which isn't running it.
    old_version = installed_version_of(install_dir) or version.__version__
    backup_dir = backup_dir_name(old_version)
    current_exe = os.path.basename(find_app_exe(install_dir) or new_exe_name)

    # Paths arrive as ARGUMENTS, never baked into the script text. cmd reads a
    # .bat in the console's OEM codepage, so a path written into the file as
    # UTF-8 is misread the moment it leaves ASCII — and "C:\Users\Jörg\Music"
    # is an entirely ordinary thing to have. Arguments come through the
    # process API as UTF-16 and survive intact.
    #
    # The body below is therefore kept strictly ASCII. Do not put an em dash in
    # here: the shipped v2.2-v2.4 script had one, and non-ASCII bytes in a .bat
    # are exactly the kind of thing that works on your machine and not theirs.
    excludes = " ".join(_KEEP)

    script = f"""@echo off
setlocal
rem Anarchy Radio FM updater - written by the app, not shipped with it.
rem Moves the running version aside (Windows allows RENAMING a running exe,
rem just not overwriting it), then writes the new one into the same folder.
rem Settings, presets and music never move, and the shortcut still works.
rem   %1 = staged build   %2 = install folder   %3 = staging

set "SRC=%~1"
set "DST=%~2"
set "STAGING=%~3"
set "LOG=%TEMP%\\anarchyfm_update.log"
set "BAK=%DST%\\{backup_dir}"

echo Anarchy Radio FM update log - %DATE% %TIME% > "%LOG%"
echo   staged  : %SRC% >> "%LOG%"
echo   install : %DST% >> "%LOG%"
echo   backup  : %BAK% >> "%LOG%"

rem System32 tools by full path. "find" in particular is a byword for being
rem shadowed - Git for Windows, the WSL shims and half the unix ports for
rem Windows all ship one. If the wrong find answers here it errors instead of
rem matching, the loop exits immediately, and the copy starts too early.
set "SYS=%SystemRoot%\\System32"

echo Waiting for Anarchy Radio FM to close...
:waitloop
"%SYS%\\tasklist.exe" /FI "PID eq {os.getpid()}" 2>nul | "%SYS%\\find.exe" "{os.getpid()}" >nul
if not errorlevel 1 (
    "%SYS%\\ping.exe" -n 2 127.0.0.1 >nul
    goto waitloop
)

echo Moving the old version aside...
echo [backup] >> "%LOG%"

rem Replace any backup left by an earlier update of this same version.
if exist "%BAK%" rmdir /S /Q "%BAK%" >nul 2>&1
mkdir "%BAK%" 2>nul

rem A move within one volume is a rename: instant, whatever the size.
if exist "%DST%\\_internal" (
    move "%DST%\\_internal" "%BAK%\\_internal" >> "%LOG%" 2>&1
    if errorlevel 1 goto failed
)
if exist "%DST%\\{current_exe}" (
    move "%DST%\\{current_exe}" "%BAK%\\{current_exe}" >> "%LOG%" 2>&1
    if errorlevel 1 goto revert
)
if exist "%DST%\\build.json" copy /Y "%DST%\\build.json" "%BAK%\\" >nul 2>&1

rem Self-documenting, so the folder still makes sense in six months.
> "%BAK%\\HOW_TO_REVERT.txt" echo Anarchy Radio FM {old_version}
>> "%BAK%\\HOW_TO_REVERT.txt" echo.
>> "%BAK%\\HOW_TO_REVERT.txt" echo This is the version you had before updating. To go back to it:
>> "%BAK%\\HOW_TO_REVERT.txt" echo.
>> "%BAK%\\HOW_TO_REVERT.txt" echo   1. Close Anarchy Radio FM.
>> "%BAK%\\HOW_TO_REVERT.txt" echo   2. In the folder above this one, delete _internal and {new_exe_name}.
>> "%BAK%\\HOW_TO_REVERT.txt" echo   3. Move _internal and {current_exe} from here back up into it.
>> "%BAK%\\HOW_TO_REVERT.txt" echo.
>> "%BAK%\\HOW_TO_REVERT.txt" echo Your settings and music are not in here - they stayed where they
>> "%BAK%\\HOW_TO_REVERT.txt" echo were and work with either version.
>> "%BAK%\\HOW_TO_REVERT.txt" echo.
>> "%BAK%\\HOW_TO_REVERT.txt" echo Nothing needs this folder. Delete it whenever you want the space back.

echo Installing...
rem /E, never /MIR - mirroring would delete the backup we just made, along
rem with the user's config and any music kept beside the exe. _internal is
rem written into empty space because the old one was moved away, so nothing
rem stale can survive anyway. /XD keeps robocopy out of the backup.
echo [copy] build >> "%LOG%"
"%SYS%\\robocopy.exe" "%SRC%" "%DST%" /E /R:3 /W:1 /XF {excludes} /XD "%BAK%" >> "%LOG%" 2>&1
if errorlevel 8 goto revert

if not exist "%DST%\\{new_exe_name}" goto revert

echo [done] installed >> "%LOG%"
start "" "%DST%\\{new_exe_name}"
if not "%STAGING%"=="" rmdir /S /Q "%STAGING%" >nul 2>&1
exit /b 0

:revert
rem Put back exactly what was moved, so a half-finished update leaves a
rem working app rather than a puzzle.
echo [REVERTING] >> "%LOG%"
if exist "%BAK%\\{current_exe}" (
    if exist "%DST%\\{new_exe_name}" del /F /Q "%DST%\\{new_exe_name}" >nul 2>&1
    move /Y "%BAK%\\{current_exe}" "%DST%\\{current_exe}" >> "%LOG%" 2>&1
)
if exist "%BAK%\\_internal" (
    if exist "%DST%\\_internal" rmdir /S /Q "%DST%\\_internal" >nul 2>&1
    move "%BAK%\\_internal" "%DST%\\_internal" >> "%LOG%" 2>&1
)
rmdir /S /Q "%BAK%" >nul 2>&1

:failed
echo [FAILED] >> "%LOG%"
echo.
echo The update could not be installed, so your existing version has been
echo put back. Start it as usual.
echo.
echo To update by hand instead, the new version is unpacked here:
echo   %SRC%
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

    # CREATE_NEW_CONSOLE, not DETACHED_PROCESS. Two reasons, both learned the
    # hard way:
    #
    #  * Lifetime. Detached, the helper died partway through its wait loop when
    #    the process that spawned it went away — the log stopped after its own
    #    header and no install ever happened. Its own console makes it properly
    #    independent of whatever started it.
    #  * Visibility. Detached means no stdout anywhere, so "Installing..." and
    #    the entire failure branch — error text, log path, pause — were written
    #    to nothing at all. Every update failure in this app's history has been
    #    silent, and this is why. A small console that says what it's doing is
    #    worth far more than a tidy one that says nothing.
    creation = 0
    if sys.platform == "win32":
        creation = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) | \
                   getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["cmd", "/c", helper, build_root, install_dir,
                      os.path.dirname(build_root)],
                     cwd=helper_dir, creationflags=creation, close_fds=True)
    console.shen(f"Update staged — your current version is being kept in "
                 f"{backup_dir}. Restarting.")
    return helper


def describe_backups(install_dir=None):
    """A one-line summary of kept previous versions, or "".

    Reported, not prompted. The backup exists so that reverting is always
    possible, which means it has to still be there when someone needs it —
    a dialog nagging to delete it on every launch would defeat the point.
    """
    backups = find_backups(install_dir)
    if not backups:
        return ""
    parts = [f"{b['version']} ({b['bytes'] / (1024 * 1024):.0f} MB)"
             for b in backups]
    return ", ".join(parts)


def remove_backup(path):
    """Delete a kept previous version. Returns (ok, message)."""
    def _clear(func, target, _exc):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass

    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_clear)
        else:                              # pragma: no cover - older Pythons
            shutil.rmtree(path, onerror=_clear)
    except Exception as e:
        return False, str(e)
    if os.path.isdir(path):
        return False, "some files were in use and couldn't be removed."
    return True, ""


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
