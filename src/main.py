import sys


def main():
    # Must run before anything spawns a child process: when launched
    # windowless (pythonw), each spawn would otherwise flash a console window
    # and steal focus from the game.
    import win_quiet
    win_quiet.silence_child_console_windows()

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
