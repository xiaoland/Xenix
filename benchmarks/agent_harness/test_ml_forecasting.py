"""Clean-room Agent benchmark for an explicit seasonal-naive transformation.

This case does not claim that Xenix exposes a native forecasting model or service.
It measures whether the Agent can materialize a business-requested, deterministic
lag-four transformation as a public Dataset.
"""

from __future__ import annotations

from pathlib import Path
import re
import unicodedata
from typing import Any

import polars as pl
import pytest

from xenix.services.agent import SourceAttachmentInput, SubmitUserTurnInput
from xenix.services.tabular import load_tabular_frame

from ._infra.case_support import (
    AttachedSourceState,
    attached_source_unchanged,
    canonical_completion,
    capture_attached_source_state,
    is_within,
    sha256_file,
)
from ._infra.contracts import (
    BenchmarkCaseAssessment,
    BenchmarkCaseContext,
    BenchmarkCaseServices,
    BenchmarkInputError,
    OutcomeCheck,
)


CASE_ID = "ml.forecasting_seasonal_naive_transform"
_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "ml_capabilities"
    / "weekly_demand_history.csv"
)
_EXPECTED_SIZE = 202
_EXPECTED_SHA256 = "BA11796DD0ABB14FEC10BCFFB6D6A52FC758944CFBB77404C658D29CDC5CC889"
_EXPECTED_FORECAST = {
    "2026-03-30": 100.0,
    "2026-04-06": 120.0,
    "2026-04-13": 110.0,
    "2026-04-20": 140.0,
}
_EXPECTED_METHOD = "seasonal_naive_lag4"


pytestmark = pytest.mark.agent_harness_live


class SeasonalNaiveForecastCase:
    """Measure an exact public lag-four result without implying a forecast service."""

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
            text=(
                "请使用 4 周季节朴素法生成未来 4 周需求预测：每个未来周直接采用 4 周前"
                "的实际 demand_units。结果只保留 forecast_week、forecast_units 和 method 三列，"
                "其中 method 写为 seasonal_naive_lag4。请生成可继续使用的数据集并给出可打开"
                "的链接，最终说明采用的是明确公式的数据变换，而不是原生预测模型。"
            ),
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
        dataset, frame = _resolve_outcome(context)
        artifact = _resolve_linked_artifact(context, dataset)
        completed = canonical_completion(context.snapshot)
        source_unchanged = _source_unchanged(self.source_path, context)
        isolated = _state_isolated(context, artifact)
        grounded_answer = _grounded_final_answer(context.snapshot)
        semantic_checks = (
            OutcomeCheck(
                "exact_seasonal_naive_dataset",
                frame is not None,
                "exact_seasonal_naive_dataset_observed"
                if frame is not None
                else "exact_seasonal_naive_dataset_missing",
            ),
            OutcomeCheck(
                "public_artifact_linked",
                artifact is not None,
                "public_artifact_link_observed" if artifact is not None else "public_artifact_link_missing",
            ),
            OutcomeCheck(
                "grounded_final_answer",
                grounded_answer,
                "seasonal_naive_method_grounded"
                if grounded_answer
                else "seasonal_naive_method_not_grounded",
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
        return BenchmarkCaseAssessment(
            semantic_checks=semantic_checks,
            integrity_checks=integrity_checks,
            terminal_shape=(frame.height, frame.width) if frame is not None else None,
        )


def _resolve_outcome(context: BenchmarkCaseContext) -> tuple[Any | None, pl.DataFrame | None]:
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
        if _matches_expected(frame):
            return dataset, frame
    return None, None


def _matches_expected(frame: pl.DataFrame) -> bool:
    required = {"forecast_week", "forecast_units", "method"}
    if frame.height != len(_EXPECTED_FORECAST) or set(frame.columns) != required:
        return False
    observed: dict[str, float] = {}
    try:
        for row in frame.to_dicts():
            week = str(row["forecast_week"])[:10]
            if str(row["method"]).strip().lower() != _EXPECTED_METHOD:
                return False
            observed[week] = float(row["forecast_units"])
    except (KeyError, TypeError, ValueError):
        return False
    return observed == _EXPECTED_FORECAST


def _grounded_final_answer(snapshot: Any | None) -> bool:
    text = _terminal_text(snapshot)
    if not text:
        return False
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).lower())
    method_named = "seasonal_naive_lag4" in normalized or "季节朴素" in normalized
    formula_named = "4周前" in normalized or "lag4" in normalized
    non_native = (
        "不是原生预测模型" in normalized
        or "并非原生预测模型" in normalized
        or "非原生预测模型" in normalized
        or "未使用原生预测模型" in normalized
        or "没有使用原生预测模型" in normalized
    )
    return method_named and formula_named and non_native


def _resolve_linked_artifact(context: BenchmarkCaseContext, dataset: Any | None) -> Any | None:
    if dataset is None:
        return None
    for uri in _artifact_uris(_terminal_text(context.snapshot)):
        try:
            artifact = context.services.artifacts.resolve_uri(uri)
        except Exception:
            continue
        if _artifact_matches_dataset(artifact, dataset, context.runtime_home):
            return artifact
    return None


def _artifact_matches_dataset(artifact: Any, dataset: Any, runtime_home: Path) -> bool:
    path = Path(str(getattr(artifact, "absolute_path", "")))
    metadata = getattr(artifact, "metadata_payload", {})
    return (
        bool(getattr(artifact, "ready_to_open", False))
        and bool(getattr(artifact, "exists", False))
        and is_within(path, runtime_home)
        and isinstance(metadata, dict)
        and (
            metadata.get("dataset_id") == dataset.id
            or (
                getattr(dataset, "ml_task_id", None)
                and metadata.get("ml_task_id") == dataset.ml_task_id
            )
        )
    )


def _artifact_uris(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"artifact://[A-Za-z0-9]+(?:\?[^)\s>]+)?", text))


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


def _state_isolated(context: BenchmarkCaseContext, artifact: Any | None) -> bool:
    if not context.settings_unchanged:
        return False
    try:
        datasets_confined = all(
            is_within(Path(str(dataset.source_path)), context.runtime_home)
            for dataset in context.services.datasets.list_datasets()
        )
        artifact_confined = artifact is None or is_within(
            Path(str(getattr(artifact, "absolute_path", ""))),
            context.runtime_home,
        )
        return datasets_confined and artifact_confined
    except Exception:
        return False


def test_ml_forecasting(agent_harness_benchmark) -> None:
    """Measure the public lag-four transform without prescribing a Tool trace."""

    agent_harness_benchmark.run(SeasonalNaiveForecastCase())
