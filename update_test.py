"""Try the real update path against a local zip, without publishing anything.

    update_test.bat

Asks for a release zip (defaults to the newest in dist/) and an install folder
to update, then runs the genuine `updater` code over them: the same verify, the
same staging, the same helper batch, the same side-by-side install and settings
migration. Nothing is downloaded and GitHub is never contacted.

The point is that the update path is the one piece of this app that cannot be
tested by using the app. It only runs during an update, only on a real install,
and when it goes wrong it does so in a detached console window nobody sees. So
it gets a harness.

Run it against a copy of an OLD install to check that upgrading works, and read
%TEMP%\\anarchyfm_update.log afterwards.
"""

import glob
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

import build_manifest  # noqa: E402
import updater  # noqa: E402


def _newest_zip():
    zips = sorted(glob.glob(os.path.join(ROOT, "dist", "*.zip")),
                  key=os.path.getmtime, reverse=True)
    return zips[0] if zips else ""


def _ask(prompt, default=""):
    shown = f" [{default}]" if default else ""
    answer = input(f"{prompt}{shown}: ").strip().strip('"')
    return answer or default


def main():
    print("Anarchy Radio FM - update path tester")
    print("=" * 60)
    print("Updates the OLD install you point at, using the NEW zip you point")
    print("at. Runs the real updater: same verify, same helper, same move-aside")
    print("and backup. Nothing is downloaded.")
    print()

    # --- 1. The old version, the thing being updated -------------------- #
    install_dir = _ask("1. OLD version folder (the one with the exe in it)")
    if not install_dir or not os.path.isdir(install_dir):
        sys.exit(f"Not a folder: {install_dir}")

    current_exe = updater.find_app_exe(install_dir)
    old_version = updater.installed_version_of(install_dir)
    print(f"     exe     : {os.path.basename(current_exe) or '(none found)'}")
    print(f"     version : {old_version or '(unknown)'}")
    if not current_exe:
        print("     WARNING: that folder has no Anarchy Radio FM exe in it.")
        if _ask("     Carry on anyway? (y/N)", "N").lower() != "y":
            return

    # --- 2. The new version, as a release zip --------------------------- #
    print()
    zip_path = _ask("2. NEW version zip", _newest_zip())
    if not zip_path or not os.path.isfile(zip_path):
        sys.exit(f"Not a file: {zip_path}")

    # --- The real thing, from here down --------------------------------- #

    print("\nStaging and verifying...")
    # Into TEMP, not beside the zip — otherwise pointing this at dist/ grows a
    # staged/ folder inside the release output.
    build_root = updater.stage(
        zip_path, staging_dir=tempfile.mkdtemp(prefix="afm_testupdate_"))
    manifest = build_manifest.read(build_root) or {}
    print(f"     staged  : {build_root}")
    print(f"     version : {manifest.get('version') or '(no build.json)'}")
    print(f"     files   : {len(manifest.get('files') or {})}")

    backup = updater.backup_dir_name(old_version)

    print("\n" + "-" * 62)
    print(f"  updating in place : {install_dir}")
    print(f"  {old_version or 'pre-2.4.1':>16} -> {manifest.get('version') or '?'}")
    print(f"  old version kept  : {backup}\\")
    print("-" * 62)
    existing = updater.find_backups(install_dir)
    if any(b["name"].lower() == backup.lower() for b in existing):
        print("  NOTE: a backup of that version already exists and will be")
        print("        replaced by this one.")
    print("  Settings and music stay exactly where they are.")

    if _ask("\nGo? (y/N)", "N").lower() != "y":
        print("Stopped. Nothing was changed.")
        return

    # The helper waits for THIS process to exit before it touches anything, so
    # quitting promptly is part of the test rather than an afterthought.
    helper = updater.apply_and_restart(build_root, install_dir=install_dir)
    print(f"\nHelper: {helper}")
    print("Exiting so it can run — it opens its own window, watch that.")
    print(r"Log: %TEMP%\anarchyfm_update.log")


if __name__ == "__main__":
    main()
