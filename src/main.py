import sys


def main():
    # Must run before pydub spawns ffmpeg: otherwise, when launched windowless
    # (pythonw), each ffmpeg decode flashes a console window and steals focus
    # from the game on every music-state change.
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
