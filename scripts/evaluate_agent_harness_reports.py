"""Apply the versioned Agent-only benchmark report policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_root in (_PROJECT_ROOT, _PROJECT_ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from benchmarks.agent_harness._infra.judge_calibration import (  # noqa: E402
    JudgeCalibrationError,
    load_calibration_report,
)
from benchmarks.agent_harness._infra.report_policy import (  # noqa: E402
    ReportPolicyError,
    compare_report_cohorts,
    evaluate_characterization,
    evaluate_formal_acceptance,
    load_agent_reports,
    write_policy_payload,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        calibrations = tuple(
            load_calibration_report(path) for path in getattr(args, "calibration", ())
        )
        if args.command == "characterize":
            decision = evaluate_characterization(load_agent_reports(args.reports))
            payload = decision.to_payload()
            successful = decision.qualified
        elif args.command == "formal":
            decision = evaluate_formal_acceptance(
                load_agent_reports(args.reports),
                calibrations=calibrations,
            )
            payload = decision.to_payload()
            successful = decision.accepted
        else:
            comparison = compare_report_cohorts(
                load_agent_reports(args.baseline),
                load_agent_reports(args.candidate),
                calibrations=calibrations,
            )
            payload = comparison.to_payload()
            successful = comparison.passed
        if args.output is not None:
            write_policy_payload(args.output, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if successful else 1
    except (ReportPolicyError, JudgeCalibrationError) as exc:
        _write_error(exc.code)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate privacy-bounded Agent Harness JSON reports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    characterize = subparsers.add_parser(
        "characterize",
        help="Qualify exactly one headless v5 measurement without creating a gate.",
    )
    characterize.add_argument("reports", nargs="+", type=Path)
    characterize.add_argument("--output", type=Path)

    formal = subparsers.add_parser(
        "formal",
        help="Gate exactly three headless and one headed v5 Agent reports.",
    )
    formal.add_argument("reports", nargs="+", type=Path)
    formal.add_argument("--calibration", action="append", default=[], type=Path)
    formal.add_argument("--output", type=Path)

    compare = subparsers.add_parser(
        "compare",
        help="Compare like-shaped Agent report cohorts.",
    )
    compare.add_argument("--baseline", nargs="+", required=True, type=Path)
    compare.add_argument("--candidate", nargs="+", required=True, type=Path)
    compare.add_argument("--calibration", action="append", default=[], type=Path)
    compare.add_argument("--output", type=Path)
    return parser


def _write_error(code: str) -> None:
    payload: dict[str, Any] = {
        "report_kind": "xenix.agent_harness.policy_error",
        "schema_version": 1,
        "error_code": code,
    }
    print(json.dumps(payload, sort_keys=True), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
