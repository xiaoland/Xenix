"""Run one explicit exact-rubric Judge calibration suite."""

from __future__ import annotations

import argparse
import importlib
import json
import multiprocessing
from pathlib import Path
import sys
from typing import Any, Iterable, Sequence

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_root in (_PROJECT_ROOT, _PROJECT_ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tests.e2e.agent_harness._infra.calibration_manifest import (  # noqa: E402
    load_calibration_manifest_suite,
)
from tests.e2e.agent_harness._infra.judge_calibration import (  # noqa: E402
    JudgeCalibrationError,
    JudgeCalibrationPacket,
    run_judge_calibration,
    write_calibration_report,
)
from tests.e2e.agent_harness._infra.runner import (  # noqa: E402
    BenchmarkSettingsError,
    load_settings_snapshot,
    resolve_judge_llm_settings_path,
    selected_model_key,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        suite_symbol, suite = _load_requested_suite(args)
        settings_path = resolve_judge_llm_settings_path(args.judge_llm_settings)
        settings, settings_sha256 = load_settings_snapshot(settings_path)
        judge_model = selected_model_key(settings, args.judge_model)
        configured_provider = next(
            (
                provider
                for provider in settings.providers
                if judge_model.startswith(f"{provider.key}/")
                and judge_model.removeprefix(f"{provider.key}/") in provider.models
            ),
            None,
        )
        if configured_provider is None:
            raise JudgeCalibrationError("calibration_judge_model_invalid")
        if (
            not configured_provider.api_key.strip()
            and not configured_provider.dialect_config.get("secret_source")
        ):
            raise JudgeCalibrationError("calibration_judge_credentials_missing")
        report = run_judge_calibration(
            suite_symbol=suite_symbol,
            packets=suite,
            settings=settings,
            judge_settings_sha256=settings_sha256,
            judge_model=judge_model,
            subject_model=args.subject_model,
        )
        write_calibration_report(args.output, report)
        print(json.dumps(report.to_payload(), ensure_ascii=False, sort_keys=True))
        return 0 if report.passed else 1
    except (JudgeCalibrationError, BenchmarkSettingsError) as exc:
        _write_error(getattr(exc, "code", "calibration_setup_invalid"))
        return 2
    except (AttributeError, ImportError, TypeError, ValueError):
        _write_error("calibration_suite_invalid")
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate an explicit Agent benchmark Judge suite.",
    )
    parser.add_argument(
        "suite_symbol",
        nargs="?",
        help=(
            "Explicit module:symbol returning one case-owned calibration packet "
            "sequence; omit when using --manifest and --manifest-suite."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Versioned calibration manifest; requires --manifest-suite.",
    )
    parser.add_argument(
        "--manifest-suite",
        help="Exact rubric/suite identity selected from --manifest.",
    )
    parser.add_argument("--judge-llm-settings", type=Path)
    parser.add_argument("--judge-model")
    parser.add_argument("--subject-model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def _load_requested_suite(
    args: argparse.Namespace,
) -> tuple[str, Iterable[JudgeCalibrationPacket]]:
    symbol_supplied = isinstance(args.suite_symbol, str) and bool(
        args.suite_symbol.strip()
    )
    manifest_supplied = args.manifest is not None
    manifest_suite_supplied = isinstance(args.manifest_suite, str) and bool(
        args.manifest_suite.strip()
    )
    if symbol_supplied:
        if manifest_supplied or manifest_suite_supplied:
            raise JudgeCalibrationError("calibration_suite_source_invalid")
        return args.suite_symbol, _load_suite(args.suite_symbol)
    if not manifest_supplied or not manifest_suite_supplied:
        raise JudgeCalibrationError("calibration_suite_source_invalid")
    loaded = load_calibration_manifest_suite(
        args.manifest,
        suite_id=args.manifest_suite,
    )
    return loaded.suite_symbol, loaded.packets


def _load_suite(symbol_reference: str) -> Iterable[JudgeCalibrationPacket]:
    module_name, separator, symbol_name = symbol_reference.partition(":")
    if (
        not separator
        or not module_name
        or not symbol_name
        or any(not part.isidentifier() for part in module_name.split("."))
        or not symbol_name.isidentifier()
    ):
        raise JudgeCalibrationError("calibration_suite_symbol_invalid")
    module = importlib.import_module(module_name)
    factory = getattr(module, symbol_name)
    suite: Any = factory() if callable(factory) else factory
    if isinstance(suite, (str, bytes)):
        raise JudgeCalibrationError("calibration_suite_invalid")
    return tuple(suite)


def _write_error(code: str) -> None:
    print(
        json.dumps(
            {
                "report_kind": "xenix.agent_harness.calibration_error",
                "schema_version": 1,
                "error_code": code,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
