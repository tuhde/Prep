import argparse
import sys


def run_cli(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="prep")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("input", type=str)
    run_parser.add_argument("--output", type=str)
    run_parser.add_argument("--set", action="append", default=[])
    run_parser.add_argument("--driver", type=str)
    run_parser.add_argument("--port", type=str)
    run_parser.add_argument("--baud", type=int)

    send_parser = subparsers.add_parser("send")
    send_parser.add_argument("input", type=str)
    send_parser.add_argument("--set", action="append", default=[])
    send_parser.add_argument("--driver", type=str)
    send_parser.add_argument("--port", type=str)
    send_parser.add_argument("--baud", type=int)

    subparsers.add_parser("ui")

    args = parser.parse_args(argv)

    if args.command == "ui":
        print("UI not yet implemented")
        return

    if args.command in ("run", "send"):
        print(f"CLI for {args.command} not yet fully implemented")
        return

    parser.print_help()
    sys.exit(1)