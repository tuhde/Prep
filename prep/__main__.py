"""CLI/UI entry point — never imports Qt on the CLI path."""
import sys


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] not in ("ui",):
        from prep.cli import run_cli
        run_cli(args)
    else:
        from prep.ui.main_window import main as run_ui
        run_ui()


if __name__ == "__main__":
    main()