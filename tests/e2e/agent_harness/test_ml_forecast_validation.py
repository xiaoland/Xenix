"""Clean-room paid-live Agent case for native forecast validation and apply."""

from __future__ import annotations

from datetime import date, datetime
import json
import math
from pathlib import Path
import re
import unicodedata
from typing import Any, Final

import polars as pl
import pytest

from xenix.services.agent import SourceAttachmentInput, SubmitUserTurnInput
from xenix.services.tabular import load_tabular_frame

from ._infra.case_support import (
    AttachedSourceState,
    attached_source_unchanged,
    canonical_completion,
    capture_attached_source_state,
    enum_value,
    is_within,
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
_EXPECTED_SELECTED_MODEL = "forecasting.holt_winters"
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
_ARTIFACT_URI = re.compile(r"artifact://[A-Za-z0-9]+(?:\?[^)\s>]+)?")
_LONG_ID = re.compile(r"\b[A-Fa-f0-9]{24,64}\b")
_WINDOWS_PATH = re.compile(r"(?<!\w)[A-Za-z]:[\\/][^\s]+")

BUSINESS_PROMPT = (
    "请先画像，把 month 绑定为月度 time、demand_units 绑定为 target、region 绑定为独立 "
    "group；先确认时间键无重复、无缺期且两个区域截止期一致。请用 model.metadata 浏览 "
    "forecasting，并分别读取 forecasting.seasonal_naive、forecasting.holt_winters 和 "
    "forecasting.sarima 的 param_schema。请为三者填写相同的 6 个月 horizon、12 个月季节周期、"
    "monthly 频率、80% 区间和 3 个滚动窗口，在同一折叠上比较 MAE/RMSE/sMAPE/MASE；不要"
    "发明 SARIMA orders、优化器参数或扩大搜索预算。根据公共评估证据选择保留模型，再仅用"
    "horizon=6 做未来 apply，生成两个区域 2026 年 1—6 月的公共预测 Dataset。最终链接未来"
    "预测 Artifact 和所选模型的评估 Artifact，并说明三模型结果、选择依据、区间非保证、使用"
    "限制和重训建议。"
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

    def build_submission(self, *, thread_id: str, fq_model_key: str) -> SubmitUserTurnInput:
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
        dataset, frame, selected_model = _resolve_forecast_outcome(context)
        apply_artifact = _resolve_apply_artifact(context, dataset)
        report_artifact, report_payload = _resolve_evaluation_report(
            context,
            selected_model,
        )
        final_text = _terminal_text(context.snapshot)
        grounding_gaps = _final_answer_grounding_gaps(final_text, selected_model)
        grounded_answer = not grounding_gaps
        completed = canonical_completion(context.snapshot)
        source_unchanged = _source_unchanged(self.source_path, context)
        isolated = _state_isolated(context, (apply_artifact, report_artifact))

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
                apply_artifact is not None,
                "linked_future_artifact_observed" if apply_artifact is not None else "linked_future_artifact_missing",
            ),
            OutcomeCheck(
                "public_temporal_evaluation",
                report_payload is not None,
                "linked_same_fold_evaluation_observed"
                if report_payload is not None
                else "linked_same_fold_evaluation_missing",
            ),
            OutcomeCheck(
                "grounded_final_answer",
                grounded_answer,
                "three_model_selection_and_interval_limits_grounded"
                if grounded_answer
                else "forecast_explanation_not_grounded:" + ",".join(grounding_gaps),
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
            OutcomeCheck(
                "state_isolated",
                isolated,
                "runtime_state_isolated" if isolated else "runtime_state_not_isolated",
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


def _resolve_forecast_outcome(
    context: BenchmarkCaseContext,
) -> tuple[Any | None, pl.DataFrame | None, str | None]:
    datasets = list(context.services.datasets.list_datasets())
    by_id = {str(dataset.id): dataset for dataset in datasets}
    source_ids = _source_ids(context)
    for dataset in datasets:
        if not _is_run_descendant(dataset, by_id, source_ids, context.run_dataset_ids):
            continue
        try:
            frame = load_tabular_frame(Path(dataset.source_path), dataset.source_format)
        except Exception:
            continue
        selected_model = _matching_forecast_model(frame)
        if selected_model is not None:
            return dataset, frame, selected_model
    return None, None, None


def _matching_forecast_model(frame: pl.DataFrame) -> str | None:
    if frame.height != 12 or set(frame.columns) != _OUTPUT_COLUMNS:
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
    if observed_keys != expected_keys or model_keys != {_EXPECTED_SELECTED_MODEL}:
        return None
    return _EXPECTED_SELECTED_MODEL


def _date_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    normalized = str(value).strip()
    return normalized[:10]


def _resolve_apply_artifact(context: BenchmarkCaseContext, dataset: Any | None) -> Any | None:
    if dataset is None:
        return None
    for artifact in _linked_artifacts(context):
        metadata = getattr(artifact, "metadata_payload", {})
        path = Path(str(getattr(artifact, "absolute_path", "")))
        if (
            enum_value(getattr(artifact, "kind", None)) == "prediction"
            and bool(getattr(artifact, "ready_to_open", False))
            and bool(getattr(artifact, "exists", False))
            and is_within(path, context.runtime_home)
            and isinstance(metadata, dict)
            and metadata.get("result_dataset_id") == dataset.id
        ):
            return artifact
    return None


def _resolve_evaluation_report(
    context: BenchmarkCaseContext,
    selected_model: str | None,
) -> tuple[Any | None, dict[str, Any] | None]:
    if selected_model is None:
        return None, None
    for artifact in _linked_artifacts(context):
        if enum_value(getattr(artifact, "kind", None)) != "report":
            continue
        payload = _read_json_artifact(artifact, context.runtime_home)
        if payload is not None and _matches_evaluation_report(payload, selected_model):
            return artifact, payload
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
        and split.get("rolling_windows") == 3
        and split.get("group_count") == 2
        and split.get("observation_count") == 168
        and split.get("future_overlap_count") == 0
        and isinstance(split.get("folds"), list)
        and len(split["folds"]) == 3
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


def _final_answer_grounding_gaps(text: str, selected_model: str | None) -> tuple[str, ...]:
    if not text or selected_model is None:
        return ("missing_final_answer_or_selection",)
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).lower())
    normalized_model_text = normalized.replace("_", "").replace("-", "")
    seasonal_naive = any(
        marker in normalized_model_text
        for marker in ("seasonalnaive", "季节朴素", "季节性朴素")
    )
    holt_winters = any(
        marker in normalized_model_text
        for marker in ("holtwinters", "霍尔特温特斯", "霍尔特温特", "霍尔特")
    )
    sarima = "sarima" in normalized_model_text
    selected_markers = {
        "forecasting.seasonal_naive": ("seasonalnaive", "季节朴素", "季节性朴素"),
        "forecasting.holt_winters": ("holtwinters", "霍尔特温特斯", "霍尔特温特", "霍尔特"),
        "forecasting.sarima": ("sarima",),
    }[selected_model]
    selected_grounded = any(marker in normalized_model_text for marker in selected_markers)
    metrics = "mae" in normalized and any(marker in normalized for marker in ("rmse", "smape", "mase"))
    interval = "80%" in normalized or "0.8" in normalized
    non_guarantee = any(marker in normalized for marker in ("不保证", "非保证", "经验覆盖", "empirical"))
    limitations = any(
        marker in normalized
        for marker in ("局限", "限制", "重训", "重新训练", "监控", "更新模型", "滚动更新", "复核")
    )
    checks = (
        ("seasonal_naive_candidate", seasonal_naive),
        ("holt_winters_candidate", holt_winters),
        ("sarima_candidate", sarima),
        ("selected_model", selected_grounded),
        ("metrics", metrics),
        ("interval_level", interval),
        ("coverage_non_guarantee", non_guarantee),
        ("limitations", limitations),
        ("dataset_and_artifact_links", len(_ARTIFACT_URI.findall(text)) >= 2),
    )
    return tuple(name for name, passed in checks if not passed)


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
        f"final_answer: {_safe_final_text(final_text)}",
    )
    return JudgeInput(
        rubric=FORECAST_VALIDATION_RUBRIC,
        task_intent=BUSINESS_PROMPT,
        facts=(
            "业务要求三种原生方法在同一月度滚动折叠、horizon 和指标口径上比较。",
            "未来结果必须是两个区域乘六个月的 12 行公共 Dataset，并链接评估与预测 Artifact。",
            "residual_quantile.v1 区间是训练侧经验校准，coverage_guaranteed=false。",
        ),
        artifact_evidence=evidence,
    )


def _safe_final_text(text: str) -> str:
    value = _ARTIFACT_URI.sub("[public artifact link]", text)
    value = _LONG_ID.sub("[stable id]", value)
    value = _WINDOWS_PATH.sub("[local path]", value)
    lines = [
        "[row-like content omitted]" if len([part for part in line.split(",") if part.strip()]) >= 4 else line
        for line in value.splitlines()
    ]
    return " ".join(" ".join(lines).split())[:480]


def _linked_artifacts(context: BenchmarkCaseContext) -> tuple[Any, ...]:
    artifacts: list[Any] = []
    seen: set[str] = set()
    for uri in _ARTIFACT_URI.findall(_terminal_text(context.snapshot)):
        try:
            artifact = context.services.artifacts.resolve_uri(uri)
        except Exception:
            continue
        artifact_id = str(getattr(artifact, "artifact_id", "") or uri)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        artifacts.append(artifact)
    return tuple(artifacts)


def _read_json_artifact(artifact: Any, runtime_home: Path) -> dict[str, Any] | None:
    path = Path(str(getattr(artifact, "absolute_path", "")))
    if not (
        bool(getattr(artifact, "ready_to_open", False))
        and bool(getattr(artifact, "exists", False))
        and is_within(path, runtime_home)
        and path.suffix.lower() == ".json"
    ):
        return None
    try:
        if path.stat().st_size > 524_288:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError, UnicodeError, json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _terminal_text(snapshot: Any | None) -> str:
    messages = list(getattr(snapshot, "messages", [])) if snapshot is not None else []
    if not messages:
        return ""
    return str(getattr(messages[-1], "text", "") or "")


def _source_ids(context: BenchmarkCaseContext) -> set[str]:
    state = context.source_state
    return set(state.source_dataset_ids) if isinstance(state, AttachedSourceState) else set()


def _is_run_descendant(
    dataset: Any,
    by_id: dict[str, Any],
    source_ids: set[str],
    run_ids: frozenset[str],
) -> bool:
    if dataset.id not in run_ids:
        return False
    parent_id = getattr(dataset, "derived_from_dataset_id", None)
    seen: set[str] = set()
    while isinstance(parent_id, str) and parent_id and parent_id not in seen:
        if parent_id in source_ids:
            return True
        seen.add(parent_id)
        parent = by_id.get(parent_id)
        if parent is None or parent_id not in run_ids:
            return False
        parent_id = getattr(parent, "derived_from_dataset_id", None)
    return False


def _source_unchanged(source_path: Path, context: BenchmarkCaseContext) -> bool:
    state = context.source_state
    if not isinstance(state, AttachedSourceState) or not state.source_dataset_ids:
        return False
    try:
        return attached_source_unchanged(
            source_path=source_path,
            source_state=state,
            services=context.services,
        )
    except Exception:
        return False


def _state_isolated(context: BenchmarkCaseContext, artifacts: tuple[Any | None, ...]) -> bool:
    if not context.settings_unchanged:
        return False
    try:
        datasets_confined = all(
            is_within(Path(str(dataset.source_path)), context.runtime_home)
            for dataset in context.services.datasets.list_datasets()
        )
        artifacts_confined = all(
            artifact is None or is_within(Path(str(getattr(artifact, "absolute_path", ""))), context.runtime_home)
            for artifact in artifacts
        )
        return datasets_confined and artifacts_confined
    except Exception:
        return False


def test_ml_forecast_validation(agent_harness_benchmark) -> None:
    """Measure the public forecast outcome without prescribing a Tool trace."""

    agent_harness_benchmark.run(ForecastValidationCase())
