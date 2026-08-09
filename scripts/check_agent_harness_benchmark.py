from __future__ import annotations

import sys

from run_pytest import main as run_pytest


INFRA_TEST_ROOT = "benchmarks/agent_harness/_infra_tests"


def main(argv: list[str] | None = None) -> int:
    forwarded = list(sys.argv[1:] if argv is None else argv)
    return run_pytest(["--direct", INFRA_TEST_ROOT, *_safe_pytest_options(forwarded)])


def _safe_pytest_options(arguments: list[str]) -> list[str]:
    """Keep the provider-free check fixed to its owned test tree."""

    allowed_exact = {
        "--collect-only",
        "--disable-warnings",
        "--help",
        "-q",
        "-s",
        "-v",
        "-vv",
        "-vvv",
        "-x",
    }
    allowed_prefixes = ("--capture=", "--durations=", "--maxfail=", "--tb=")
    rejected = tuple(
        argument
        for argument in arguments
        if argument not in allowed_exact
        and not argument.startswith(allowed_prefixes)
    )
    if rejected:
        raise SystemExit(
            "benchmark-agent-harness-check accepts reporting options only; "
            "its offline test selection is fixed."
        )
    return arguments


if __name__ == "__main__":
    raise SystemExit(main())
