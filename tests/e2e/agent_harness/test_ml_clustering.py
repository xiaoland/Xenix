"""Clean-room Agent benchmark for a deterministic two-segment outcome."""

from __future__ import annotations

from pathlib import Path
import re
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

    def build_submission(self, *, thread_id: str, fq_model_key: str) -> SubmitUserTurnInput:
        return SubmitUserTurnInput(
            thread_id=thread_id,
            text=(
                "请仅按 visits 和 avg_order_value，使用 KMeans 将这些账户分成 2 个群组。"
                "请生成保留原始三列并新增 cluster_id 的可继续使用结果，给出可打开的链接，"
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
        dataset, frame = _resolve_outcome(context)
        artifact = _resolve_linked_artifact(context, dataset)
        completed = canonical_completion(context.snapshot)
        source_unchanged = _source_unchanged(self.source_path, context)
        isolated = _state_isolated(context, artifact)
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
                artifact is not None,
                "public_artifact_link_observed" if artifact is not None else "public_artifact_link_missing",
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
    required = {"account_id", "visits", "avg_order_value", "cluster_id"}
    if frame.height != 6 or set(frame.columns) != required:
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


def test_ml_clustering(agent_harness_benchmark) -> None:
    """Measure the public two-cluster result without prescribing a Tool trace."""

    agent_harness_benchmark.run(CustomerSegmentationCase())
