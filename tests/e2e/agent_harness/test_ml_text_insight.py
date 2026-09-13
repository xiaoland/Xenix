"""Clean-room Agent benchmark for tokenization followed by keyword frequency."""

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


CASE_ID = "ml.text_keyword_frequency"
_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "ml_capabilities"
    / "support_feedback_keywords.csv"
)
_EXPECTED_SIZE = 167
_EXPECTED_SHA256 = "380229FA5B500CF99ED6B0B42207A03C2C8B0BA9ACE04599A3CA290FB5354C40"
_EXPECTED_COUNTS = {
    "物流": 2,
    "延误": 2,
    "refund": 2,
    "packaging": 1,
    "damaged": 1,
    "客服": 1,
    "回复": 1,
    "approved": 1,
    "pending": 1,
}


pytestmark = pytest.mark.agent_harness_live


class FeedbackKeywordFrequencyCase:
    """Measure a public keyword-frequency Dataset without prescribing a Tool trace."""

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
                "请统计这些客户反馈中各个有意义词语的出现次数，帮助我们了解关注重点。"
                "请交付词语和频次的汇总表（列名 token、count），"
                "给出可打开的链接，并在最终答复中指出并列出现最多的词及其次数。"
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
        semantic_checks = (
            OutcomeCheck(
                "exact_keyword_frequency_dataset",
                frame is not None,
                "exact_keyword_frequency_dataset_observed"
                if frame is not None
                else "exact_keyword_frequency_dataset_missing",
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
        )
        return BenchmarkCaseAssessment(
            semantic_checks=semantic_checks,
            integrity_checks=integrity_checks,
            terminal_shape=(frame.height, frame.width) if frame is not None else None,
        )


def _resolve_outcome(context: BenchmarkCaseContext) -> tuple[Any | None, pl.DataFrame | None]:
    datasets = list(context.services.datasets.list_datasets())
    by_id = {dataset.id: dataset for dataset in datasets}
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
    if set(frame.columns) != {"token", "count"}:
        return False
    observed: dict[str, int] = {}
    try:
        for row in frame.to_dicts():
            observed[str(row["token"]).strip().lower()] = int(row["count"])
    except (KeyError, TypeError, ValueError):
        return False
    # Neutral words may be retained or treated as stopwords; the business
    # request does not prescribe the tokenizer's private stopword list.
    allowed = _EXPECTED_COUNTS | {"这次": 1, "整体": 1, "正常": 1}
    return (
        frame.height == len(observed)
        and all(observed.get(word) == count for word, count in _EXPECTED_COUNTS.items())
        and all(allowed.get(word) == count for word, count in observed.items())
    )


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


def _source_ids(context: BenchmarkCaseContext) -> set[int]:
    state = context.source_state
    return set(state.source_dataset_ids) if isinstance(state, AttachedSourceState) else set()


def _is_run_descendant(
    dataset: Any,
    by_id: dict[int, Any],
    source_ids: set[int],
    run_ids: frozenset[int],
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


def test_ml_text_insight(agent_harness_benchmark) -> None:
    """Measure the public keyword-frequency result without prescribing a Tool trace."""

    agent_harness_benchmark.run(FeedbackKeywordFrequencyCase())
