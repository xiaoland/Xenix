"""Outcome oracle for applying a Knowledge Library rule to inventory data."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import time
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
    BenchmarkCasePreparationServices,
    BenchmarkCaseServices,
    BenchmarkInputError,
    OutcomeCheck,
)


CASE_ID = "knowledge.rainy_season_restock"
_FIXTURE_DIRECTORY = Path(__file__).resolve().parent / "fixtures"
_INVENTORY_PATH = _FIXTURE_DIRECTORY / "rainy_season_inventory.csv"
_RULE_PATH = _FIXTURE_DIRECTORY / "rainy_season_restock_rule.txt"
_INVENTORY_SIZE = 201
_INVENTORY_SHA256 = "6DB0E521DB7FF9867F23BDD4123F0E0E0DAF603EA845381B40F0DB3B462B79BC"
_RULE_SIZE = 316
_RULE_SHA256 = "43A1BB0D8CCA73C2348017597754965F6C6F3276D45B31749E5082051D8E90BC"
_EXPECTED_RESTOCK = {"U100": 130.0, "R200": 75.0}


pytestmark = pytest.mark.agent_harness_live


class RainySeasonRestockCase:
    """Apply one imported business rule without prescribing the Agent's route."""

    case_id = CASE_ID

    def __init__(
        self,
        inventory_path: Path = _INVENTORY_PATH,
        rule_path: Path = _RULE_PATH,
    ) -> None:
        self.inventory_path = inventory_path
        self.rule_path = rule_path

    def validate_input(self) -> str:
        inventory_digest = _validate_fixture(
            self.inventory_path,
            expected_size=_INVENTORY_SIZE,
            expected_sha256=_INVENTORY_SHA256,
        )
        rule_digest = _validate_fixture(
            self.rule_path,
            expected_size=_RULE_SIZE,
            expected_sha256=_RULE_SHA256,
        )
        return sha256(f"{inventory_digest}:{rule_digest}".encode("ascii")).hexdigest().upper()

    def prepare(self, *, services: BenchmarkCasePreparationServices) -> None:
        imported = services.knowledge_import.import_file(self.rule_path, timeout=60.0)
        deadline = time.monotonic() + 60.0
        while time.monotonic() < deadline:
            status = services.knowledge_derivation.status_for_import(imported.import_id)
            if status is not None and status.status == "succeeded":
                if status.phase != "completed":
                    raise BenchmarkInputError("knowledge_rule_not_retrieval_ready")
                task_id = services.knowledge_index.enqueue_rebuild(
                    ("text_vector",),
                    trigger="manual",
                )
                index_result = services.knowledge_index.rebuild_now(task_id)
                if index_result.status != "succeeded":
                    raise BenchmarkInputError("knowledge_vector_index_failed")
                return
            if status is not None and status.status == "failed":
                raise BenchmarkInputError("knowledge_rule_derivation_failed")
            time.sleep(0.02)
        raise BenchmarkInputError("knowledge_rule_derivation_timeout")

    def build_submission(self, *, thread_id: str, fq_model_key: str) -> SubmitUserTurnInput:
        return SubmitUserTurnInput(
            thread_id=thread_id,
            text=(
                "请用 semantic 模式检索知识库中与‘季节性采购边界’含义相关的经验，"
                "并基于这份库存表创建需要补货的商品清单。"
                "新数据集只保留需要补货的商品，并包含 SKU 和补货数量。"
                "最终答复请简要说明采用的补货规则，并列出需要补货的 SKU 与数量。"
            ),
            source_attachments=[
                SourceAttachmentInput(file_path=str(self.inventory_path.resolve()))
            ],
            fq_model_key=fq_model_key,
        )

    def capture_source_state(
        self,
        *,
        snapshot: Any,
        services: BenchmarkCaseServices,
    ) -> AttachedSourceState:
        return capture_attached_source_state(
            source_path=self.inventory_path,
            snapshot=snapshot,
            services=services,
        )

    def assess(self, *, context: BenchmarkCaseContext) -> BenchmarkCaseAssessment:
        source_state = context.source_state
        source_dataset_ids = (
            set(source_state.source_dataset_ids)
            if isinstance(source_state, AttachedSourceState)
            else set()
        )
        terminal, derived_seen = _resolve_exact_derived_dataset(
            context=context,
            source_dataset_ids=source_dataset_ids,
        )
        completed = canonical_completion(context.snapshot)
        source_unchanged = (
            attached_source_unchanged(
                source_path=self.inventory_path,
                source_state=source_state,
                services=context.services,
            )
            if isinstance(source_state, AttachedSourceState)
            else False
        )
        dataset_and_settings_isolated = _dataset_and_settings_are_isolated(context)
        exact_rows = terminal is not None
        semantic_checks = (
            OutcomeCheck(
                "derived_dataset_created",
                derived_seen,
                "source_linked_derived_dataset"
                if derived_seen
                else "no_source_linked_derived_dataset",
            ),
            OutcomeCheck(
                "exact_restock_rows",
                exact_rows,
                "expected_sku_quantity_mapping" if exact_rows else "unexpected_restock_rows",
            ),
        )
        integrity_checks = (
            OutcomeCheck(
                "canonical_completion",
                completed,
                "canonical_assistant_completion"
                if completed
                else "not_a_terminal_assistant_completion",
            ),
            OutcomeCheck(
                "source_unchanged",
                source_unchanged,
                "external_and_registered_source_unchanged"
                if source_unchanged
                else "source_changed_or_unreadable",
            ),
            OutcomeCheck(
                "dataset_and_settings_isolated",
                dataset_and_settings_isolated,
                "dataset_paths_and_settings_confined_to_cell_runtime"
                if dataset_and_settings_isolated
                else "dataset_path_or_settings_escaped_cell_runtime",
            ),
        )
        return BenchmarkCaseAssessment(
            semantic_checks=semantic_checks,
            integrity_checks=integrity_checks,
            terminal_shape=(terminal.height, terminal.width) if terminal is not None else None,
        )


def _validate_fixture(path: Path, *, expected_size: int, expected_sha256: str) -> str:
    if not path.is_file():
        raise BenchmarkInputError("missing_fixture")
    if path.stat().st_size != expected_size:
        raise BenchmarkInputError("fixture_size_mismatch")
    digest = sha256_file(path)
    if digest != expected_sha256:
        raise BenchmarkInputError("fixture_hash_mismatch")
    return digest


def _resolve_exact_derived_dataset(
    *,
    context: BenchmarkCaseContext,
    source_dataset_ids: set[str],
) -> tuple[pl.DataFrame | None, bool]:
    derived_seen = False
    for dataset in context.services.datasets.list_datasets():
        if (
            dataset.id not in context.run_dataset_ids
            or dataset.derived_from_dataset_id not in source_dataset_ids
        ):
            continue
        try:
            frame = load_tabular_frame(Path(dataset.source_path), dataset.source_format)
        except Exception:
            continue
        derived_seen = True
        if _contains_exact_restock_mapping(frame):
            return frame, True
    return None, derived_seen


def _contains_exact_restock_mapping(frame: pl.DataFrame) -> bool:
    if frame.height != len(_EXPECTED_RESTOCK) or frame.width < 2:
        return False
    rows = frame.to_dicts()
    for sku_column in frame.columns:
        skus = [str(row.get(sku_column) or "").strip() for row in rows]
        if set(skus) != set(_EXPECTED_RESTOCK) or len(set(skus)) != len(skus):
            continue
        for quantity_column in frame.columns:
            if quantity_column == sku_column:
                continue
            try:
                actual = {
                    sku: float(row[quantity_column])
                    for sku, row in zip(skus, rows, strict=True)
                }
            except (KeyError, TypeError, ValueError):
                continue
            if actual == _EXPECTED_RESTOCK:
                return True
    return False


def _dataset_and_settings_are_isolated(context: BenchmarkCaseContext) -> bool:
    if not context.settings_unchanged:
        return False
    try:
        return all(
            is_within(Path(dataset.source_path), context.runtime_home)
            for dataset in context.services.datasets.list_datasets()
        )
    except Exception:
        return False


def test_rainy_season_restock(agent_harness_benchmark) -> None:
    """Measure the final exact restock Dataset without prescribing a Tool trace."""

    agent_harness_benchmark.run(RainySeasonRestockCase())