"""Clean-room Agent benchmark for a deterministic tabular cleaning outcome."""

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


CASE_ID = "ml.cleaning_service_tickets"
_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "ml_capabilities"
    / "service_ticket_cleaning.csv"
)
_EXPECTED_SIZE = 227
_EXPECTED_SHA256 = "AE3663B873183218DF6573071837EA80A507C20E68A5E5D2410C63ACCE88B43C"
_EXPECTED_ROWS = {
    "SHIP-001": ("DEPOT-N", 12.0, "ready"),
    "SHIP-002": ("DEPOT-S", 21.0, "ready"),
    "SHIP-003": ("DEPOT-N", 18.0, "hold"),
    "SHIP-005": ("DEPOT-N", 24.0, "hold"),
    "SHIP-006": ("DEPOT-S", 30.0, "ready"),
}


pytestmark = pytest.mark.agent_harness_live


class ServiceTicketCleaningCase:
    """Measure the public cleaned Dataset, independent of the chosen Tool route."""

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
                "这批履约记录需要进入周报，请整理成可用的数据。重复记录不应重复计数，包裹数不能为负数，"
                "状态文本需去掉首尾空格并统一小写，缺失包裹数按有效记录中位数补齐。请保留原来的四列，生成数据集并"
                "给出可打开的链接；最终简要汇报结果行数和中位数补充值。"
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
                "exact_cleaned_dataset",
                frame is not None,
                "exact_cleaned_dataset_observed" if frame is not None else "exact_cleaned_dataset_missing",
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
    required = {"shipment_id", "depot", "parcel_count", "state"}
    if frame.height != len(_EXPECTED_ROWS) or not required.issubset(frame.columns):
        return False
    observed: dict[str, tuple[str, float, str]] = {}
    try:
        for row in frame.to_dicts():
            shipment_id = str(row["shipment_id"]).strip()
            observed[shipment_id] = (
                str(row["depot"]).strip(),
                float(row["parcel_count"]),
                str(row["state"]).strip(),
            )
    except (KeyError, TypeError, ValueError):
        return False
    return observed == _EXPECTED_ROWS


def _source_unchanged(source_path: Path, context: BenchmarkCaseContext) -> bool:
    state = context.source_state
    if not isinstance(state, AttachedSourceState) or not state.source_dataset_ids:
        return False
    return attached_source_unchanged(
        source_path=source_path,
        source_state=state,
        services=context.services,
    )


def test_ml_cleaning(agent_harness_benchmark) -> None:
    """Measure one exact public cleaning outcome without prescribing a Tool trace."""

    agent_harness_benchmark.run(ServiceTicketCleaningCase())
