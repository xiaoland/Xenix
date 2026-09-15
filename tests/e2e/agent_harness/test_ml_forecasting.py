"""Clean-room Agent benchmark for an explicit seasonal-naive transformation.

This case does not claim that Xenix exposes a native forecasting model or service.
It measures whether the Agent can materialize a business-requested, deterministic
lag-four transformation as a public Dataset.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
import pytest

from xenix.services.agent import SourceAttachmentInput, SubmitUserTurnInput

from ._infra.case_support import (
    AttachedSourceState,
    attached_source_unchanged,
    canonical_completion,
    capture_attached_source_state,
    linked_tables,
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

    def build_submission(self, *, thread_id: int, fq_model_key: str) -> SubmitUserTurnInput:
        return SubmitUserTurnInput(
            thread_id=thread_id,
            text=(
                "这份需求数据有四周一轮的规律。请按延续最近一轮需求的口径，给出未来四周的备货参考。"
                "结果表列名为 forecast_week、forecast_units、method，提供可打开的链接，并说明这种估算的局限。"
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
        tables = linked_tables(context)
        frame = next((frame for frame in tables.values() if _matches_expected(frame)), None)
        completed = canonical_completion(context.snapshot)
        source_unchanged = _source_unchanged(self.source_path, context)
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
                bool(tables),
                "public_artifact_link_observed" if tables else "public_artifact_link_missing",
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
        return BenchmarkCaseAssessment(
            semantic_checks=semantic_checks,
            integrity_checks=integrity_checks,
            terminal_shape=(frame.height, frame.width) if frame is not None else None,
        )


def _matches_expected(frame: pl.DataFrame) -> bool:
    required = {"forecast_week", "forecast_units", "method"}
    if frame.height != len(_EXPECTED_FORECAST) or not required.issubset(frame.columns):
        return False
    observed: dict[str, float] = {}
    try:
        for row in frame.to_dicts():
            week = str(row["forecast_week"])[:10]
            if not str(row["method"]).strip():
                return False
            observed[week] = float(row["forecast_units"])
    except (KeyError, TypeError, ValueError):
        return False
    return observed == _EXPECTED_FORECAST


def _source_unchanged(source_path: Path, context: BenchmarkCaseContext) -> bool:
    state = context.source_state
    if not isinstance(state, AttachedSourceState) or not state.source_dataset_ids:
        return False
    return attached_source_unchanged(
        source_path=source_path,
        source_state=state,
        services=context.services,
    )


def test_ml_forecasting(agent_harness_benchmark) -> None:
    """Measure the public lag-four transform without prescribing a Tool trace."""

    agent_harness_benchmark.run(SeasonalNaiveForecastCase())
