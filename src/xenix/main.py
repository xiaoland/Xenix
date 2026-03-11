from __future__ import annotations

from multiprocessing import freeze_support

from .app import run


def main() -> int:
    freeze_support()
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
