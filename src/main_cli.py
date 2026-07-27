"""Anarchy Radio FM CLI mode — headless console-only operation (use --cli flag)."""

import time
import os
import sys

from audio_engine import XiPodEngine
from log_watcher import Bridge
from setup import config_exists, load_config, discover_addons
from setup_gui import run_setup_gui
import console
import process_utils


def main_cli():
    console.show_boot_art()

    force_setup = "--setup" in sys.argv

    if force_setup and config_exists():
        console.shen("Re-opening setup wizard...")
        cfg = run_setup_gui(existing_cfg=load_config())
        if cfg is None:
            console.shen("Setup cancelled — using existing config.")
            cfg = load_config()
        else:
            console.shen("Config updated.")
    elif not config_exists():
        console.shen("No config found — opening setup wizard...")
        cfg = run_setup_gui()
        if cfg is None:
            console.shen("Setup cancelled. Can't run without a config, Commander.")
            return
    else:
        cfg = load_config()
        console.divider()
        console.shen("Commander, I've been working on something. Let me get it fired up.")
        console.divider()
        print()

    music_path         = cfg.get("music_folder", "")
    log_path           = cfg.get("log_path", "")
    game_config_folder = cfg.get("game_config_folder", "")
    default_vol        = float(cfg.get("default_volume", 0.8))
    shuffle            = cfg.get("shuffle", True)
    crossfade_ms       = int(cfg.get("crossfade_ms", 2500))
    auto_close         = cfg.get("auto_close_with_game", True)

    if not music_path or not os.path.exists(music_path):
        console.error(f"Music library not found at: {music_path}")
        console.shen("Run setup again or check xipod_config.json, Commander.")
        return

    if not log_path:
        console.error("No log path configured.")
        return

    if not os.path.exists(log_path):
        console.warn(f"Log file not found yet: {log_path}")
        console.shen("I'll keep an eye out. XCOM will create it when it launches.")

    if not game_config_folder:
        console.warn("No game_config_folder in xipod_config.json — MMS toggle sync disabled.")
        console.shen("Run setup again to set your game config folder, Commander.")
    elif not os.path.isdir(game_config_folder):
        console.warn(f"Game config folder not found: {game_config_folder}")
        console.shen("MMS toggle sync will be skipped until the folder exists.")

    console.init_file_log(music_path)

    console.shen("Calibrating audio subsystems...")
    engine = XiPodEngine()
    engine.load_library(music_path, log_path, game_config_folder=game_config_folder,
                        shuffle=shuffle, addons=discover_addons(cfg))
    engine.set_volume(default_vol)
    engine.set_crossfade(crossfade_ms)
    engine.set_radio_chunk_minutes(cfg.get("radio_chunk_minutes", 10))

    console.shen("Patching into XCOM's comms relay...")
    bridge = Bridge(log_path, engine)
    bridge.start()

    if not process_utils.is_game_running(default=True):
        process_utils.launch_game(cfg)
    else:
        console.shen("XCOM is already running. Patching in.")

    print()
    console.divider()
    console.shen("All systems nominal, Commander. Anarchy Radio FM is online.")
    console.debug(f"Monitoring: {log_path}")
    if auto_close:
        console.debug("Auto-shutdown enabled — I'll close up when XCOM signs off.")
    console.divider()
    print()

    # Dual-gate lifecycle: keep the radio warm while EITHER the game or
    # the launcher (AML) is running, so the user can relaunch after a
    # crash without restarting Anarchy Radio FM. Shut down once both are gone.
    watched = process_utils.watched_names(cfg.get("game_exe", ""))
    xcom_was_running = False
    try:
        while True:
            time.sleep(3)
            if not auto_close:
                continue
            running = process_utils.running_processes(watched)
            if running is None:
                continue  # tasklist hiccup — never shut down on "unknown"
            if process_utils.GAME_PROCESS in running:
                xcom_was_running = True
            elif xcom_was_running and not running:
                print()
                console.divider()
                console.shen("XCOM has signed off. Powering down Anarchy Radio FM.")
                console.divider()
                break
            # else: game closed but launcher still open — standby for relaunch
    except KeyboardInterrupt:
        print()
        console.shen("Copy that, Commander. Shutting down.")

    bridge.stop()
    engine.shutdown()
    console.shen("Anarchy Radio FM offline. Shen out.")
    print()


if __name__ == "__main__":
    main_cli()
