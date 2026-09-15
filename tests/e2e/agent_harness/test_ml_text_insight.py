"""Clean-room Agent benchmark for tokenization followed by keyword frequency."""

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
        tables = linked_tables(context)
        frame = next((frame for frame in tables.values() if _matches_expected(frame)), None)
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
    if not {"token", "count"}.issubset(frame.columns):
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


def _source_unchanged(source_path: Path, context: BenchmarkCaseContext) -> bool:
    state = context.source_state
    if not isinstance(state, AttachedSourceState) or not state.source_dataset_ids:
        return False
    return attached_source_unchanged(
        source_path=source_path,
        source_state=state,
        services=context.services,
    )


def test_ml_text_insight(agent_harness_benchmark) -> None:
    """Measure the public keyword-frequency result without prescribing a Tool trace."""

    agent_harness_benchmark.run(FeedbackKeywordFrequencyCase())
