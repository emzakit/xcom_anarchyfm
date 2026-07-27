import sys


def main():
    # Must run before anything spawns a child process: when launched
    # windowless (pythonw), each spawn would otherwise flash a console window
    # and steal focus from the game.
    import win_quiet
    win_quiet.silence_child_console_windows()

    if "--cli" in sys.argv:
        from main_cli import main_cli
        main_cli()
    else:
        from gui import run_gui
        run_gui()


if __name__ == "__main__":
    main()
