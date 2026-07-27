"""Console log capture — mirrors console output into the GUI comms log.

install_log_hooks() wraps each console.* print helper so every message goes
BOTH to the terminal/file log (original behaviour) and to a Qt signal the
main window renders. Wrapping keeps every call site untouched — modules just
keep calling console.shen()/warn()/etc.
"""

from PySide6.QtCore import Signal, QObject
import console
from gui.theme import GREEN, CYAN, AMBER, GREEN_DIM, RED_DIM, BORDER


class LogSignal(QObject):
    message = Signal(str, str)  # (text, color)


log_signal = LogSignal()


def install_log_hooks():
    """Wrap the console helpers so they also emit Qt signals for the GUI log."""
    original_shen = console.shen
    original_track = console.track
    original_signal = console.signal
    original_debug = console.debug
    original_warn = console.warn
    original_error = console.error
    original_faint = console.faint
    original_divider = console.divider

    def shen(msg):
        original_shen(msg)
        log_signal.message.emit(f"SHEN: {msg}", GREEN)

    def track(label, name):
        original_track(label, name)
        log_signal.message.emit(f"{label}: {name}", CYAN)

    def signal(msg):
        original_signal(msg)
        log_signal.message.emit(f">> {msg}", AMBER)

    def debug(msg):
        original_debug(msg)
        log_signal.message.emit(f"   {msg}", GREEN_DIM)

    def warn(msg):
        original_warn(msg)
        log_signal.message.emit(f"SHEN: {msg}", AMBER)

    def error(msg):
        original_error(msg)
        log_signal.message.emit(f"SHEN: {msg}", RED_DIM)

    def faint(msg):
        original_faint(msg)
        log_signal.message.emit(f"   {msg}", "#555555")

    def divider():
        original_divider()
        log_signal.message.emit("─" * 52, BORDER)

    console.shen = shen
    console.track = track
    console.signal = signal
    console.debug = debug
    console.warn = warn
    console.error = error
    console.faint = faint
    console.divider = divider
