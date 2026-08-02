"""Console log capture — mirrors console output into the GUI comms log.

install_log_hooks() wraps each console.* print helper so every message goes
BOTH to the terminal/file log (original behaviour) and to a Qt signal the
main window renders. Wrapping keeps every call site untouched — modules just
keep calling console.shen()/warn()/etc.
"""

from PySide6.QtCore import Signal, QObject
import console
from gui.theme import PRIMARY, ACCENT, AMBER, PRIMARY_DIM, RED_DIM, BORDER, MUTED


class LogSignal(QObject):
    message = Signal(str, str)  # (text, color)


log_signal = LogSignal()


def install_log_hooks():
    """Wrap the console helpers so they also emit Qt signals for the GUI log."""
    original_shen = console.shen
    original_jax = console.jax
    original_silo = console.silo
    original_alert = console.alert
    original_track = console.track
    original_signal = console.signal
    original_debug = console.debug
    original_warn = console.warn
    original_error = console.error
    original_faint = console.faint
    original_divider = console.divider

    def shen(msg):
        original_shen(msg)
        log_signal.message.emit(f"SHEN: {msg}", PRIMARY)

    def jax(msg):
        original_jax(msg)
        log_signal.message.emit(f"JAX: {msg}", ACCENT)

    def silo(msg):
        original_silo(msg)
        log_signal.message.emit(f"SILO: {msg}", AMBER)

    def alert(msg):
        original_alert(msg)
        log_signal.message.emit(f"SHEN: {msg}", RED_DIM)

    def track(label, name):
        original_track(label, name)
        log_signal.message.emit(f"{label}: {name}", ACCENT)

    def signal(msg):
        original_signal(msg)
        log_signal.message.emit(f">> {msg}", AMBER)

    def debug(msg):
        original_debug(msg)
        log_signal.message.emit(f"   {msg}", PRIMARY_DIM)

    def warn(msg):
        original_warn(msg)
        log_signal.message.emit(f"SHEN: {msg}", AMBER)

    def error(msg):
        original_error(msg)
        log_signal.message.emit(f"SHEN: {msg}", RED_DIM)

    def faint(msg):
        original_faint(msg)
        log_signal.message.emit(f"   {msg}", MUTED)

    def divider():
        original_divider()
        log_signal.message.emit("─" * 52, BORDER)

    console.shen = shen
    console.jax = jax
    console.silo = silo
    # alert was never hooked, so every red warning — the ones that
    # matter most — reached the terminal and the file but never the
    # in-app log, which is the only one most people ever see.
    console.alert = alert
    console.track = track
    console.signal = signal
    console.debug = debug
    console.warn = warn
    console.error = error
    console.faint = faint
    console.divider = divider
