from __future__ import annotations

import argparse
from multiprocessing import freeze_support
from typing import Sequence

from .app import run


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xenix")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Initialize the native app and exit after startup validation.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    freeze_support()
    args = build_argument_parser().parse_args(list(argv) if argv is not None else None)
    return run(smoke_test=args.smoke_test)


if __name__ == "__main__":
    raise SystemExit(main())
