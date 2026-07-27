"""Anarchy Radio FM GUI package — PySide6 Avenger-style control panel.

All imports happen inside run_gui() on purpose: submodules of this package
(gui.theme, etc.) are imported by non-GUI modules like setup_gui, and
importing any `gui.*` submodule executes this __init__ first. Keeping the
package init dependency-free avoids circular imports and keeps `--cli`
startup light.
"""


def run_gui():
    """Main entry: setup check, then launch the GUI."""
    import sys

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    from setup import config_exists, load_config
    from setup_gui import run_setup_gui
    from gui.theme import STYLESHEET
    from gui.log_hooks import install_log_hooks
    from gui.main_window import XiPodWindow

    install_log_hooks()

    force_setup = "--setup" in sys.argv

    if force_setup and config_exists():
        cfg = run_setup_gui(existing_cfg=load_config())
        if cfg is None:
            cfg = load_config()
    elif not config_exists():
        cfg = run_setup_gui()
        if cfg is None:
            print("Setup cancelled. Can't run without a config, Commander.")
            return
    else:
        cfg = load_config()

    # The setup wizard may already have created the QApplication (its own
    # exec loop has exited by now). Either way, no event loop is running
    # here — so always exec, otherwise the main window dies instantly on
    # first run.
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = XiPodWindow(cfg)
    window.setStyleSheet(STYLESHEET)
    window.show()

    QTimer.singleShot(100, window.start_engine)

    app.exec()
