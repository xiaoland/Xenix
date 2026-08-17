"""CLI entry point for explicit real-provider Agent Harness benchmarks."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from run_pytest import main as run_pytest  # noqa: E402
from tests.e2e.agent_harness._infra.dispatch import (  # noqa: E402
    benchmark_pytest_arguments,
)


def main(argv: list[str] | None = None) -> int:
    """Delegate all collection, selection, and lifecycle control to pytest."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    return run_pytest(benchmark_pytest_arguments(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
