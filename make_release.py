"""Build a release: PyInstaller, then build.json, then the zip.

    venv\\Scripts\\python.exe make_release.py

Produces exactly what helpers/naming_conventions.txt asks for:

    dist/AnarchyRadioFM_APP_v<version>/
    dist/AnarchyRadioFM_APP_v<version>.zip

The naming is the point of having this script rather than running PyInstaller
by hand. `updater.ASSET_PREFIX` requires a release asset beginning with
"anarchyradiofm_app" — so a zip uploaded under any other name doesn't fail
loudly, it just makes every existing install stop finding updates and quietly
fall back to opening the releases page. That is not a mistake worth leaving
available.

Inside the zip the folder stays plain "AnarchyRadioFM/", matching every
release so far: people unzip it over the folder they already have, and a
versioned folder there would leave their config and music behind in the old
one.
"""

import datetime
import os
import shutil
import stat
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

import build_manifest  # noqa: E402
import version  # noqa: E402

DIST = os.path.join(ROOT, "dist")

# What PyInstaller's COLLECT is named in the spec, and what the folder inside
# the zip must stay called.
PYI_NAME = "AnarchyRadioFM"


# Anything here means the app was RUN from the build folder and left its
# runtime state behind. PyInstaller doesn't clean these up, so without the
# scrub below a release would ship the developer's own config, their music
# tree, and whatever packs they were testing.
_LEAKS = ("xipod_config.json", "xipod_presets.json", ".spotify_cache.json",
          "music", "addon_test", "addon_projects", "build.json")


def _run(cmd):
    print(f"> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"FAILED: {' '.join(cmd)}")


def _force_rmtree(path):
    """rmtree that copes with read-only flags Windows leaves lying around.

    Running the app from dist/ creates folders that come back marked read-only
    often enough — a synced drive is usually the culprit — that a plain rmtree
    fails with "Access is denied" and takes the whole build with it.
    """
    def _clear(func, target, _exc):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass

    if hasattr(shutil, "rmtree") and sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_clear)
    else:                                   # pragma: no cover - older Pythons
        shutil.rmtree(path, onerror=_clear)


def _check_clean(build_dir):
    """Refuse to package a build that has the developer's own files in it."""
    found = [n for n in _LEAKS if os.path.exists(os.path.join(build_dir, n))]
    if found:
        sys.exit(
            "Build folder contains runtime state, not just build output:\n  "
            + "\n  ".join(found)
            + f"\n\nDelete {build_dir} and build again. Shipping this would "
              "publish your own config and music folders.")


def _pyinstaller():
    exe = os.path.join(ROOT, "venv", "Scripts", "pyinstaller.exe")
    if not os.path.isfile(exe):
        exe = "pyinstaller"
    staged = os.path.join(DIST, PYI_NAME)
    # Always from scratch. PyInstaller overwrites what it produces but never
    # removes what it doesn't, so an incremental build quietly inherits every
    # file any previous version left behind.
    if os.path.isdir(staged):
        _force_rmtree(staged)
    if os.path.isdir(staged):
        sys.exit(f"Couldn't clear {staged} — is the app still running?")
    _run([exe, "AnarchyRadioFM.spec", "--noconfirm"])
    if not os.path.isdir(staged):
        sys.exit(f"PyInstaller produced no {staged}")
    _check_clean(staged)
    return staged


def _zip(build_dir, zip_path):
    """Zip build_dir so its contents sit under AnarchyRadioFM/ in the archive."""
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(build_dir):
            for name in sorted(files):
                full = os.path.join(root, name)
                rel = os.path.relpath(full, build_dir)
                zf.write(full, os.path.join(PYI_NAME, rel))
    return zip_path


def main():
    ver = version.__version__
    release_name = f"AnarchyRadioFM_APP_v{ver}"
    release_dir = os.path.join(DIST, release_name)
    zip_path = os.path.join(DIST, release_name + ".zip")

    print(f"Anarchy Radio FM {ver}")

    staged = _pyinstaller()

    if os.path.isdir(release_dir):
        _force_rmtree(release_dir)
    os.replace(staged, release_dir)

    built_at = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    manifest_path = build_manifest.write(release_dir, ver, built_at)
    manifest = build_manifest.read(release_dir)
    count = len(manifest.get("files") or {})
    print(f"  {os.path.basename(manifest_path)}: {count} files hashed")

    ok, problems = build_manifest.verify(release_dir)
    if not ok:
        sys.exit("Manifest doesn't match the build it just described:\n  "
                 + "\n  ".join(problems[:10]))

    _zip(release_dir, zip_path)
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)

    print()
    print("Done.")
    print(f"  folder : dist/{release_name}/")
    print(f"  zip    : dist/{release_name}.zip  ({size_mb:.0f} MB)")
    print()
    print(f"Upload the zip to the v{ver} release under that exact name — the "
          "updater looks for an asset starting 'anarchyradiofm_app'.")


if __name__ == "__main__":
    main()
