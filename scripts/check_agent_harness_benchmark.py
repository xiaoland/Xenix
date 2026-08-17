"""CLI entry point for the provider-free benchmark infrastructure check."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from run_pytest import main as run_pytest  # noqa: E402
from tests.e2e.agent_harness._infra.dispatch import (  # noqa: E402
    INFRA_TEST_ROOT,
    safe_check_pytest_options,
)


def main(argv: list[str] | None = None) -> int:
    forwarded = list(sys.argv[1:] if argv is None else argv)
    return run_pytest(
        ["--direct", INFRA_TEST_ROOT, *safe_check_pytest_options(forwarded)]
    )


if __name__ == "__main__":
    raise SystemExit(main())
