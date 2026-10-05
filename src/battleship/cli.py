import sys
from pathlib import Path

from poethepoet.app import PoeThePoet

ROOT = Path(__file__).resolve().parents[2]


def main():
    args = sys.argv[1:] or ["up"]
    sys.exit(PoeThePoet(cwd=ROOT)(cli_args=args))
