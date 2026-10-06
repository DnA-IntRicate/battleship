import argparse
import os
import sys
from pathlib import Path

from battleship.client.uart import DEFAULT_COM_PORT

from poethepoet.app import PoeThePoet

ROOT = Path(__file__).resolve().parents[2]


def parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        prog="battleship",
        description="Build, flash and run the Battleship client against the STM32 server.",
        epilog="Any other arguments are passed through to poe (default task: up).",
    )
    parser.add_argument(
        "-p",
        "--port",
        default=os.environ.get("BATTLESHIP_PORT", DEFAULT_COM_PORT),
        help="serial port, e.g. COM4 or /dev/ttyACM0 "
        "(default: $BATTLESHIP_PORT or %(default)s)",
    )

    return parser.parse_known_args(argv)


def main():
    args, rest = parse_args(sys.argv[1:])

    # Poe tasks run as subprocesses and inherit this, so 'battleship-client'
    # picks it up through its own BATTLESHIP_PORT default.
    os.environ["BATTLESHIP_PORT"] = args.port

    sys.exit(PoeThePoet(cwd=ROOT)(cli_args=rest or ["up"]))
