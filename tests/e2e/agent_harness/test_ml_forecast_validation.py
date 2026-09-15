"""Clean-room paid-live Agent case for native forecast validation and apply."""

from __future__ import annotations

from datetime import date, datetime
import math
from pathlib import Path
from typing import Any, Final

import polars as pl
import pytest

from xenix.services.agent import SourceAttachmentInput, SubmitUserTurnInput

from ._infra.case_support import (
    AttachedSourceState,
    attached_source_unchanged,
    canonical_completion,
    capture_attached_source_state,
    linked_tables,
    linked_json_reports,
    sha256_file,
)
from ._infra.contracts import (
    BenchmarkCaseAssessment,
    BenchmarkCaseContext,
    BenchmarkCaseServices,
    BenchmarkInputError,
    JudgeInput,
    JudgeRubric,
    OutcomeCheck,
)


CASE_ID: Final = "ml.forecast_validation_v1"
_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "ml_capabilities" / "monthly_regional_demand.csv"
_EXPECTED_SIZE = 4226
_EXPECTED_SHA256 = "28F3BAD3A223D2CA18A17F5C673834E4CCB5A2EAE371C3F719EEFEF03EC53F68"
_EXPECTED_GROUPS = ("NORTH_HUB", "SOUTH_HUB")
_EXPECTED_FORECAST_MONTHS = (
    "2026-01-01",
    "2026-02-01",
    "2026-03-01",
    "2026-04-01",
    "2026-05-01",
    "2026-06-01",
)
_MODEL_KEYS = frozenset(
    {
        "forecasting.seasonal_naive",
        "forecasting.holt_winters",
        "forecasting.sarima",
    }
)
_OUTPUT_COLUMNS = {
    "region",
    "forecast_time",
    "forecast",
    "lower_bound",
    "upper_bound",
    "model_key",
    "interval_method",
    "interval_level",
    "horizon",
}

BUSINESS_PROMPT = (
    "请根据这份各地区月度需求历史，为两个区域分别预测 2026 年 1—6 月的需求，"
    "提供 80% 预测区间。请比较适合这类数据的预测方案，用历史回测支持选择，"
    "交付可继续使用的预测表和评估报告，并说明预测的不确定性及采购使用建议。"
)

FORECAST_VALIDATION_RUBRIC = JudgeRubric(
    rubric_id="ml.forecast_validation.business_explanation.v1",
    score_dimensions=(
        "business_intent_alignment",
        "public_evidence_grounding",
        "temporal_and_interval_reasoning",
        "decision_usefulness_and_limits",
    ),
    allowed_reason_codes=(
        "missing_public_outcome",
        "incomparable_model_claim",
        "future_leakage_claim",
        "interval_guarantee_overclaim",
        "ungrounded_model_selection",
        "clear_grounded_explanation",
    ),
)

pytestmark = pytest.mark.agent_harness_live


class ForecastValidationCase:
    """Measure public temporal evidence and a horizon-only future outcome."""

    case_id = CASE_ID

    def __init__(self, source_path: Path = _FIXTURE_PATH) -> None:
        self.source_path = source_path

    def validate_input(self) -> str:
        if not self.source_path.is_file():
            raise BenchmarkInputError("missing_fixture")
        if self.source_path.stat().st_size != _EXPECTED_SIZE:
            raise BenchmarkInputError("fixture_size_mismatch")
        digest = sha256_file(self.source_path)
        if digest != _EXPECTED_SHA256:
            raise BenchmarkInputError("fixture_hash_mismatch")
        return digest

    def build_submission(self, *, thread_id: int, fq_model_key: str) -> SubmitUserTurnInput:
        return SubmitUserTurnInput(
            thread_id=thread_id,
            text=BUSINESS_PROMPT,
            source_attachments=[SourceAttachmentInput(file_path=str(self.source_path.resolve()))],
            fq_model_key=fq_model_key,
        )

    def capture_source_state(
        self,
        *,
        snapshot: Any,
        services: BenchmarkCaseServices,
    ) -> AttachedSourceState:
        return capture_attached_source_state(
            source_path=self.source_path,
            snapshot=snapshot,
            services=services,
        )

    def assess(self, *, context: BenchmarkCaseContext) -> BenchmarkCaseAssessment:
        frame, selected_model = _resolve_forecast_outcome(context)
        report_artifact, report_payload = _resolve_evaluation_report(
            context,
            selected_model,
        )
        final_text = _terminal_text(context.snapshot)
        completed = canonical_completion(context.snapshot)
        source_unchanged = _source_unchanged(self.source_path, context)

        semantic_checks = (
            OutcomeCheck(
                "exact_future_forecast_dataset",
                frame is not None,
                "two_group_six_month_forecast_observed"
                if frame is not None
                else "two_group_six_month_forecast_missing",
            ),
            OutcomeCheck(
                "public_future_artifact",
                frame is not None,
                "linked_future_artifact_observed" if frame is not None else "linked_future_artifact_missing",
            ),
            OutcomeCheck(
                "public_temporal_evaluation",
                report_payload is not None,
                "linked_same_fold_evaluation_observed"
                if report_payload is not None
                else "linked_same_fold_evaluation_missing",
            ),
        )
        integrity_checks = (
            OutcomeCheck(
                "canonical_completion",
                completed,
                "canonical_completion_observed" if completed else "canonical_completion_missing",
            ),
            OutcomeCheck(
                "source_unchanged",
                source_unchanged,
                "source_unchanged" if source_unchanged else "source_changed_or_unverifiable",
            ),
        )
        deterministic_passed = all(check.passed for check in semantic_checks)
        integrity_passed = all(check.passed for check in integrity_checks)
        judge_input = (
            _build_judge_input(report_payload, final_text, selected_model)
            if deterministic_passed and integrity_passed and report_payload is not None and selected_model is not None
            else None
        )
        return BenchmarkCaseAssessment(
            semantic_checks=semantic_checks,
            integrity_checks=integrity_checks,
            judge_input=judge_input,
            judge_required=True,
            terminal_shape=(frame.height, frame.width) if frame is not None else None,
        )


def _resolve_forecast_outcome(context: BenchmarkCaseContext) -> tuple[pl.DataFrame | None, str | None]:
    for frame in linked_tables(context).values():
        selected_model = _matching_forecast_model(frame)
        if selected_model is not None:
            return frame, selected_model
    return None, None


def _matching_forecast_model(frame: pl.DataFrame) -> str | None:
    if frame.height != 12 or not _OUTPUT_COLUMNS.issubset(frame.columns):
        return None
    expected_keys = {
        (group, forecast_month) for group in _EXPECTED_GROUPS for forecast_month in _EXPECTED_FORECAST_MONTHS
    }
    observed_keys: set[tuple[str, str]] = set()
    model_keys: set[str] = set()
    try:
        for row in frame.to_dicts():
            group = str(row["region"])
            forecast_time = _date_value(row["forecast_time"])
            point = float(row["forecast"])
            lower = float(row["lower_bound"])
            upper = float(row["upper_bound"])
            model_key = str(row["model_key"])
            interval_level = float(row["interval_level"])
            horizon = int(row["horizon"])
            if not (
                all(math.isfinite(value) for value in (point, lower, upper, interval_level))
                and lower <= point <= upper
                and row["interval_method"] == "residual_quantile.v1"
                and math.isclose(interval_level, 0.8, abs_tol=1e-9)
                and horizon == 6
                and model_key in _MODEL_KEYS
            ):
                return None
            observed_keys.add((group, forecast_time))
            model_keys.add(model_key)
    except KeyError, TypeError, ValueError:
        return None
    if observed_keys != expected_keys or len(model_keys) != 1:
        return None
    return next(iter(model_keys))


def _date_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    normalized = str(value).strip()
    return normalized[:10]


def _resolve_evaluation_report(
    context: BenchmarkCaseContext,
    selected_model: str | None,
) -> tuple[Any | None, dict[str, Any] | None]:
    if selected_model is None:
        return None, None
    for uri, payload in linked_json_reports(context).items():
        if payload is not None and _matches_evaluation_report(payload, selected_model):
            return uri, payload
    return None, None


def _matches_evaluation_report(payload: dict[str, Any], selected_model: str) -> bool:
    evaluation = payload.get("evaluation")
    comparison = payload.get("comparison")
    facts = payload.get("forecast_evaluation")
    if not (
        payload.get("model_key") == selected_model
        and isinstance(evaluation, dict)
        and isinstance(comparison, dict)
        and isinstance(facts, dict)
    ):
        return False
    split = facts.get("split")
    preparation = facts.get("preparation")
    intervals = facts.get("intervals")
    per_group = facts.get("per_group")
    if not (
        isinstance(split, dict)
        and isinstance(preparation, dict)
        and isinstance(intervals, dict)
        and isinstance(per_group, list)
    ):
        return False
    metric_names = evaluation.get("metrics")
    if not (
        evaluation.get("primary_metric_name") == "mae"
        and _finite_number(evaluation.get("primary_metric_value"))
        and isinstance(metric_names, dict)
        and {"mae", "rmse", "smape", "mase"}.issubset(metric_names)
        and comparison.get("primary_metric_name") == "mae"
        and comparison.get("direction") == "min"
    ):
        return False
    if not (
        split.get("frequency") == "monthly"
        and split.get("seasonal_period") == 12
        and split.get("horizon") == 6
        and int(split.get("rolling_windows", 0)) > 0
        and split.get("group_count") == 2
        and split.get("observation_count") == 168
        and split.get("future_overlap_count") == 0
        and isinstance(split.get("folds"), list)
        and len(split["folds"]) == split["rolling_windows"]
        and isinstance(split.get("fold_identity_digest"), str)
        and bool(split["fold_identity_digest"])
    ):
        return False
    if not (
        preparation.get("fit_scope") == "chronological_training_prefixes"
        and preparation.get("time_column") == "month"
        and preparation.get("target_column") == "demand_units"
        and preparation.get("group_column") == "region"
        and preparation.get("duplicate_key_count") == 0
        and preparation.get("missing_period_count") == 0
        and preparation.get("non_finite_target_count") == 0
    ):
        return False
    return bool(
        intervals.get("method") == "residual_quantile.v1"
        and math.isclose(float(intervals.get("interval_level")), 0.8, abs_tol=1e-9)
        and int(intervals.get("calibration_count")) > 0
        and _finite_number(intervals.get("empirical_coverage"))
        and _finite_number(intervals.get("mean_width"))
        and intervals.get("coverage_guaranteed") is False
        and len(per_group) == 2
    )


def _finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except TypeError, ValueError:
        return False


def _build_judge_input(
    report: dict[str, Any],
    final_text: str,
    selected_model: str,
) -> JudgeInput:
    evaluation = report["evaluation"]
    facts = report["forecast_evaluation"]
    split = facts["split"]
    intervals = facts["intervals"]
    evidence = (
        (
            "public_forecast_dataset: row_count=12; groups=2; horizon=6; "
            f"model_key={selected_model}; interval_method=residual_quantile.v1"
        ),
        (
            "public_evaluation: primary_metric=mae; "
            f"candidate_mae={float(evaluation['primary_metric_value']):.6f}; "
            f"folds={int(split['rolling_windows'])}; future_overlap=0"
        ),
        (
            "public_interval: level=0.8; "
            f"calibration_count={int(intervals['calibration_count'])}; "
            f"empirical_coverage={float(intervals['empirical_coverage']):.6f}; "
            f"mean_width={float(intervals['mean_width']):.6f}; coverage_guaranteed=false"
        ),
        f"final_answer: {final_text}",
    )
    return JudgeInput(
        rubric=FORECAST_VALIDATION_RUBRIC,
        task_intent=BUSINESS_PROMPT,
        facts=(
            "业务要求比较适合的预测方案；历史回测需使用一致的预测跨度和指标口径。",
            "未来结果必须是两个区域乘六个月的 12 行公共 Dataset，并链接评估与预测 Artifact。",
            "residual_quantile.v1 区间是训练侧经验校准，coverage_guaranteed=false。",
        ),
        artifact_evidence=evidence,
    )


def _terminal_text(snapshot: Any | None) -> str:
    messages = list(getattr(snapshot, "messages", [])) if snapshot is not None else []
    if not messages:
        return ""
    return str(getattr(messages[-1], "text", "") or "")


def _source_unchanged(source_path: Path, context: BenchmarkCaseContext) -> bool:
    state = context.source_state
    if not isinstance(state, AttachedSourceState) or not state.source_dataset_ids:
        return False
    return attached_source_unchanged(
        source_path=source_path,
        source_state=state,
        services=context.services,
    )


def test_ml_forecast_validation(agent_harness_benchmark) -> None:
    """Measure the public forecast outcome without prescribing a Tool trace."""

    agent_harness_benchmark.run(ForecastValidationCase())
