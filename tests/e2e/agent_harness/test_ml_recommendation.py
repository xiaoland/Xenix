"""Clean-room Agent benchmark for an exact item-similarity recommendation."""

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


CASE_ID = "ml.recommendation_item_similarity"
_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "ml_capabilities"
    / "item_similarity_ratings.csv"
)
_EXPECTED_SIZE = 263
_EXPECTED_SHA256 = "A45CC8B727D1BA85002552245EEB9F1C4C8020B061221906AC2CFD97D67DD9F1"
_EXPECTED_RECOMMENDATIONS = (
    (1, "SKU-B", 1.0, 4),
    (2, "SKU-C", 1.0, 3),
)


pytestmark = pytest.mark.agent_harness_live


class ItemSimilarityRecommendationCase:
    """Measure the public ranked result, independent of the chosen Tool route."""

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
                "我们想给 SKU-A 的顾客推荐两个相似商品。请根据附件评分记录选出候选，"
                "评分不足 3 条的商品暂不考虑。请交付按推荐顺序排列的结果表，给出可打开"
                "的链接。结果表包含 base_item、rank、recommended_item 列，并在最终答复中按顺序列出两个推荐商品。"
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
                "exact_ranked_recommendations",
                frame is not None,
                "exact_ranked_recommendations_observed"
                if frame is not None
                else "exact_ranked_recommendations_missing",
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
    required = {"base_item", "rank", "recommended_item"}
    if frame.height != 2 or not required.issubset(frame.columns):
        return False
    try:
        rows = sorted(frame.to_dicts(), key=lambda row: int(row["rank"]))
        observed = tuple((int(row["rank"]), str(row["recommended_item"]).strip())
                         for row in rows if str(row["base_item"]).strip() == "SKU-A")
    except (KeyError, TypeError, ValueError):
        return False
    return observed == tuple((rank, item) for rank, item, _score, _count in _EXPECTED_RECOMMENDATIONS)


def _source_unchanged(source_path: Path, context: BenchmarkCaseContext) -> bool:
    state = context.source_state
    if not isinstance(state, AttachedSourceState) or not state.source_dataset_ids:
        return False
    return attached_source_unchanged(
        source_path=source_path,
        source_state=state,
        services=context.services,
    )


def test_ml_recommendation(agent_harness_benchmark) -> None:
    """Measure the public ranked recommendations without prescribing a Tool trace."""

    agent_harness_benchmark.run(ItemSimilarityRecommendationCase())
