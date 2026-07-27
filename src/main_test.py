"""Manual test harness — runs the engine against a local log file.

Open the log file in a text editor and append lines like:
    XIPOD: STATE_AVENGER
    XIPOD: PLAY
    XIPOD: NEXT
to drive the engine without launching XCOM 2.
For automated tests, see tests/test_smoke.py.
"""

import os
import time

from audio_engine import XiPodEngine
from log_watcher import Bridge

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC_PATH = os.path.join(_ROOT, "music")
LOG_PATH = os.path.join(_ROOT, "test_log.txt")

player = XiPodEngine()
player.load_library(MUSIC_PATH, LOG_PATH)

bridge = Bridge(LOG_PATH, player)
bridge.start()

try:
    print(f"Anarchy Radio FM test harness running. Append 'XIPOD: PLAY' to {LOG_PATH} to test.")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    bridge.stop()
    player.shutdown()
