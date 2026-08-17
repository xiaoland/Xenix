"""Case-agnostic pytest dispatch for the Agent Harness end-to-end benchmark.

The CLI entry points under ``scripts/`` are thin shells over this module, and
the offline ``_infra_tests`` import the same functions directly.  Keeping the
selector validation and argument building here means tests depend on the
benchmark's own package rather than reaching back into ``scripts/`` (which is
only on ``sys.path`` as a side effect of an in-process pytest launch).
"""

from __future__ import annotations

BENCHMARK_PLUGIN = "tests.e2e.agent_harness._infra.pytest_plugin"
BENCHMARK_ROOT = "tests/e2e/agent_harness"
INFRA_TEST_ROOT = "tests/e2e/agent_harness/_infra_tests"


def benchmark_pytest_arguments(arguments: list[str]) -> list[str]:
    """Build the live benchmark runner's pytest argument list.

    Pytest owns collection, selection, and lifecycle; this only turns the
    command line into one case-agnostic runner invocation.
    """

    explicit_targets = tuple(
        argument for argument in arguments if _benchmark_target(argument) is not None
    )
    invalid_python_targets = tuple(
        argument
        for argument in arguments
        if _looks_like_python_target(argument) and _benchmark_target(argument) is None
    )
    if invalid_python_targets:
        raise SystemExit(
            "Agent Harness selectors must name a live case under "
            f"{BENCHMARK_ROOT}."
        )
    collection_targets = list(explicit_targets) or [BENCHMARK_ROOT]
    return [
        "--direct",
        "-p",
        BENCHMARK_PLUGIN,
        f"--ignore={INFRA_TEST_ROOT}",
        *collection_targets,
        "--run-agent-harness",
        *(
            argument
            for argument in arguments
            if argument not in explicit_targets
        ),
    ]


def safe_check_pytest_options(arguments: list[str]) -> list[str]:
    """Keep the provider-free check fixed to its owned ``_infra_tests`` tree."""

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


def _benchmark_target(argument: str) -> str | None:
    normalized = argument.replace("\\", "/").removeprefix("./")
    path = normalized.split("::", 1)[0].rstrip("/")
    if not (
        path == BENCHMARK_ROOT
        or path.startswith(f"{BENCHMARK_ROOT}/test_")
    ):
        return None
    if path == INFRA_TEST_ROOT or "/_infra" in path:
        return None
    return argument


def _looks_like_python_target(argument: str) -> bool:
    normalized = argument.replace("\\", "/")
    path = normalized.split("::", 1)[0]
    return not normalized.startswith("-") and path.endswith(".py")
