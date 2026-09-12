from __future__ import annotations

import argparse
from pathlib import Path

from .server import run


def main() -> None:
    parser = argparse.ArgumentParser(prog='UStracker')
    parser.add_argument('--root', default='.', help='portable product root')
    args = parser.parse_args()
    run(Path(args.root))


if __name__ == '__main__':
    main()
