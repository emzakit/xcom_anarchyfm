import sys


def _install_crash_handler():
    """Make an unhandled exception say something instead of vanishing.

    The shipped build is windowless (console=False), so stdout and stderr go
    nowhere — and PySide6 aborts the process when a Python exception escapes a
    slot. Together that means any error in a button handler closes the whole
    app instantly, in total silence, with nothing written down. "It just shuts
    when I click Options" is genuinely all the evidence anyone gets.

    So: write the traceback to the comms log, and put it on screen. A crash the
    user can read out is worth ten they can only describe.
    """
    import traceback

    def _handle(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return

        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            import console
            console.alert(f"Something broke: {exc_type.__name__}: {exc}")
            for line in text.rstrip().splitlines():
                console.faint(line)
        except Exception:
            pass

        # Straight to a file too. The comms log needs a music folder to exist,
        # and TEMP always does — so this survives a failure during startup.
        try:
            import os
            import tempfile
            crash = os.path.join(tempfile.gettempdir(), "anarchyfm_crash.log")
            with open(crash, "a", encoding="utf-8") as f:
                import datetime
                f.write(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
                f.write(text)
        except Exception:
            crash = ""

        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                box = QMessageBox()
                box.setWindowTitle("Anarchy Radio FM — that wasn't meant to happen")
                box.setText(f"{exc_type.__name__}: {exc}")
                box.setInformativeText(
                    (f"Written to:\n{crash}\n\n" if crash else "")
                    + "The app is still running. If it misbehaves after this, "
                      "restart it — and please send that file in with a bug "
                      "report.")
                box.setDetailedText(text)
                box.exec()
        except Exception:
            pass

    sys.excepthook = _handle


def main():
    # Must run before anything spawns a child process: when launched
    # windowless (pythonw), each spawn would otherwise flash a console window
    # and steal focus from the game.
    import win_quiet
    win_quiet.silence_child_console_windows()

    _install_crash_handler()

    # The way back in when none of the below works — see bootstrap.py. Only
    # the batch file: writing a config here would make it look like setup had
    # already run, and nobody would ever see the wizard again.
    try:
        import bootstrap
        bootstrap.ensure_rescue_script()
    except Exception:
        pass

    # Says what's actually running, and warns if an update only half landed.
    # Cheap, and it's the first line anyone will want when a build misbehaves.
    try:
        import updater
        updater.report_install()
    except Exception:
        pass

    if "--cli" in sys.argv:
        from main_cli import main_cli
        main_cli()
    else:
        from gui import run_gui
        run_gui()


if __name__ == "__main__":
    main()
