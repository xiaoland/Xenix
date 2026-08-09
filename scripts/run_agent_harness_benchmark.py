"""Thin pytest entry point for explicit real-provider Agent Harness benchmarks."""

from __future__ import annotations

import sys

from run_pytest import main as run_pytest


_PYTEST_PLUGIN = "benchmarks.agent_harness._infra.pytest_plugin"
_BENCHMARK_ROOT = "benchmarks/agent_harness"
_INFRA_TEST_ROOT = "benchmarks/agent_harness/_infra_tests"


def main(argv: list[str] | None = None) -> int:
    """Delegate all collection, selection, and lifecycle control to pytest."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    return run_pytest(_pytest_arguments(arguments))


def _pytest_arguments(arguments: list[str]) -> list[str]:
    explicit_targets = tuple(
        argument
        for argument in arguments
        if _benchmark_target(argument) is not None
    )
    invalid_python_targets = tuple(
        argument
        for argument in arguments
        if _looks_like_python_target(argument)
        and _benchmark_target(argument) is None
    )
    if invalid_python_targets:
        raise SystemExit(
            "Agent Harness selectors must name a live case under "
            f"{_BENCHMARK_ROOT}."
        )
    collection_targets = list(explicit_targets) or [_BENCHMARK_ROOT]
    return [
        "--direct",
        "-p",
        _PYTEST_PLUGIN,
        f"--ignore={_INFRA_TEST_ROOT}",
        *collection_targets,
        "--run-agent-harness",
        *(
            argument
            for argument in arguments
            if argument not in explicit_targets
        ),
    ]


def _benchmark_target(argument: str) -> str | None:
    normalized = argument.replace("\\", "/").removeprefix("./")
    path = normalized.split("::", 1)[0].rstrip("/")
    if not (
        path == _BENCHMARK_ROOT
        or path.startswith(f"{_BENCHMARK_ROOT}/test_")
    ):
        return None
    if path == _INFRA_TEST_ROOT or "/_infra" in path:
        return None
    return argument


def _looks_like_python_target(argument: str) -> bool:
    normalized = argument.replace("\\", "/")
    path = normalized.split("::", 1)[0]
    return not normalized.startswith("-") and path.endswith(".py")


if __name__ == "__main__":
    raise SystemExit(main())
