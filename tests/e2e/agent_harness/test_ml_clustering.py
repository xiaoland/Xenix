"""Clean-room Agent benchmark for a deterministic two-segment outcome."""

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


CASE_ID = "ml.clustering_two_segments"
_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "ml_capabilities"
    / "customer_segmentation_points.csv"
)
_EXPECTED_SIZE = 120
_EXPECTED_SHA256 = "FB8D3E8D646A64E7901070752CF47E91475A3B4D6F3BC4E2191F40851F827FC5"
_LOW_ACCOUNTS = {"ACCT-001", "ACCT-002", "ACCT-003"}
_HIGH_ACCOUNTS = {"ACCT-004", "ACCT-005", "ACCT-006"}
_EXPECTED_FEATURES = {
    "ACCT-001": (1.0, 12.0),
    "ACCT-002": (2.0, 14.0),
    "ACCT-003": (1.0, 16.0),
    "ACCT-004": (9.0, 88.0),
    "ACCT-005": (10.0, 92.0),
    "ACCT-006": (11.0, 96.0),
}


pytestmark = pytest.mark.agent_harness_live


class CustomerSegmentationCase:
    """Measure the public partition and interpretation, not a particular Tool trace."""

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
                "请按访问频次和平均客单值把这些账户分成两个运营群组。"
                "请生成保留原始记录并带有 cluster_id 群组标签列的结果表，给出可打开的链接，"
                "并简要说明两个群组在访问频次和平均客单值上的业务差异。"
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
                "exact_two_segment_partition",
                frame is not None,
                "exact_two_segment_partition_observed"
                if frame is not None
                else "exact_two_segment_partition_missing",
            ),
            OutcomeCheck(
                "public_artifact_linked",
                bool(tables),
                "public_table_link_observed" if tables else "public_table_link_missing",
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
    required = {"account_id", "visits", "avg_order_value", "cluster_id"}
    if frame.height != 6 or not required.issubset(frame.columns):
        return False
    try:
        labels: dict[str, str] = {}
        features: dict[str, tuple[float, float]] = {}
        for row in frame.to_dicts():
            account_id = str(row["account_id"]).strip()
            raw_label = row["cluster_id"]
            if raw_label is None or not str(raw_label).strip():
                return False
            labels[account_id] = str(raw_label).strip()
            features[account_id] = (
                float(row["visits"]),
                float(row["avg_order_value"]),
            )
    except (KeyError, TypeError, ValueError):
        return False
    if set(labels) != _LOW_ACCOUNTS | _HIGH_ACCOUNTS or features != _EXPECTED_FEATURES:
        return False
    low_labels = {labels[account] for account in _LOW_ACCOUNTS}
    high_labels = {labels[account] for account in _HIGH_ACCOUNTS}
    return len(low_labels) == 1 and len(high_labels) == 1 and low_labels != high_labels


def _source_unchanged(source_path: Path, context: BenchmarkCaseContext) -> bool:
    state = context.source_state
    if not isinstance(state, AttachedSourceState) or not state.source_dataset_ids:
        return False
    return attached_source_unchanged(
        source_path=source_path,
        source_state=state,
        services=context.services,
    )


def test_ml_clustering(agent_harness_benchmark) -> None:
    """Measure the public two-cluster result without prescribing a Tool trace."""

    agent_harness_benchmark.run(CustomerSegmentationCase())
