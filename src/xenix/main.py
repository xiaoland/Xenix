from __future__ import annotations

import argparse
from multiprocessing import freeze_support
from typing import Sequence

from .app import run
from .single_instance import SingleInstanceGuard


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
    # Both development and packaged GUI entry points arrive here.  Workers
    # branch before this module, so one guard protects the only Conversation
    # writer without making worker startup part of recovery semantics.
    guard = SingleInstanceGuard()
    try:
        return run(smoke_test=args.smoke_test)
    finally:
        guard.close()


if __name__ == "__main__":
    raise SystemExit(main())
