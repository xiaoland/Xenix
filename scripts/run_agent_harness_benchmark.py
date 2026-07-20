"""Explicit real-provider benchmark command for the Agent Harness."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for candidate in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from agent_harness_benchmark.runner import (  # noqa: E402
    DEFAULT_OUTPUT_DIRECTORY,
    BenchmarkSettingsError,
    dry_run_models,
    run_benchmark,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run isolated real-LLM Agent Harness benchmark cells.",
    )
    parser.add_argument(
        "--llm-settings",
        type=Path,
        help="External LLM settings JSON; otherwise XENIX_AGENT_BENCHMARK_LLM_SETTINGS_PATH.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Pinned benchmark source workbook.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Ignored directory for one sanitized JSON result per cell.",
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Optional provider/model selection; repeat to narrow diagnosis.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only enumerate selected configured provider/model keys.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.dry_run:
        try:
            for model_key in dry_run_models(
                settings_path=arguments.llm_settings,
                requested_models=arguments.model,
            ):
                print(model_key)
        except BenchmarkSettingsError as exc:
            print(f"benchmark setup failed: {exc.code}", file=sys.stderr)
            return 2
        return 0

    if arguments.source is None:
        _parser().error("--source is required unless --dry-run is used")
    runs = run_benchmark(
        settings_path=arguments.llm_settings,
        source_path=arguments.source,
        output_directory=arguments.output_dir,
        requested_models=arguments.model,
    )
    for run in runs:
        result = run.result
        print(
            " ".join(
                (
                    result.case_id,
                    result.provider_model,
                    result.run_status.value,
                    f"outcome_passed={result.outcome_passed}",
                    f"persisted={run.persisted}",
                )
            )
        )
    if not runs or any(not run.persisted for run in runs):
        return 2
    # Outcome failures are benchmark observations, not an infrastructure
    # failure.  Runtime/setup/measurement failures remain non-zero.
    return 1 if any(run.result.run_status.value != "completed" for run in runs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
