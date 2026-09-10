"""Outcome oracle for the real April dine-in sales cleaning benchmark."""

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
    enum_value,
    sha256_file,
)
from ._infra.contracts import (
    BenchmarkCaseAssessment,
    BenchmarkCaseContext,
    BenchmarkCaseServices,
    BenchmarkInputError,
    OutcomeCheck,
)


CASE_ID = "cleaning.april_dine_in_sales"
EXPECTED_FILE_SIZE = 116_459_191
EXPECTED_SHA256 = "6B902DE50277E727FE936FFC4FE072B4D8B1C3D60A7D85413E114B72C4140E31"
EXPECTED_SHAPE = (485_789, 50)
_DATASET_ID_LINE = re.compile(r"^dataset_id:\s*([A-Za-z0-9_-]+)\s*$", re.MULTILINE)


pytestmark = pytest.mark.agent_harness_live


class AprilDineInSalesCleaningCase:
    """One outcome-first cleaning case; it does not prescribe Tool behavior."""

    case_id = CASE_ID

    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path

    def validate_input(self) -> str:
        if not self.source_path.is_file():
            raise BenchmarkInputError("missing_fixture")
        if self.source_path.stat().st_size != EXPECTED_FILE_SIZE:
            raise BenchmarkInputError("fixture_size_mismatch")
        digest = sha256_file(self.source_path)
        if digest != EXPECTED_SHA256:
            raise BenchmarkInputError("fixture_hash_mismatch")
        return digest

    def build_submission(self, *, thread_id: str, fq_model_key: str) -> SubmitUserTurnInput:
        return SubmitUserTurnInput(
            thread_id=thread_id,
            text="清洗",
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

    def assess(
        self,
        *,
        context: BenchmarkCaseContext,
    ) -> BenchmarkCaseAssessment:
        snapshot = context.snapshot
        source_state = context.source_state
        dataset_service = context.services.datasets
        if snapshot is None or source_state is None or not source_state.source_dataset_ids:
            semantic_checks = (
                OutcomeCheck("terminal_output_resolved", False, "no_canonical_snapshot"),
                OutcomeCheck("header_promoted", False, "no_terminal_dataset"),
                OutcomeCheck("report_row_removed", False, "no_terminal_dataset"),
                OutcomeCheck("header_row_removed", False, "no_terminal_dataset"),
                OutcomeCheck("exact_duplicates_removed", False, "no_terminal_dataset"),
                OutcomeCheck("expected_shape", False, "no_terminal_dataset"),
                OutcomeCheck("business_rows_preserved", False, "no_terminal_dataset"),
            )
            integrity_checks = (
                OutcomeCheck("canonical_completion", False, "no_canonical_snapshot"),
                OutcomeCheck("source_unchanged", False, "source_state_unavailable"),
            )
            return BenchmarkCaseAssessment(
                semantic_checks=semantic_checks,
                integrity_checks=integrity_checks,
            )

        terminal = self._resolve_terminal_dataset(
            snapshot=snapshot,
            dataset_service=dataset_service,
            source_dataset_ids=set(source_state.source_dataset_ids),
            run_dataset_ids=context.run_dataset_ids,
        )
        canonical_complete = canonical_completion(snapshot)
        source_unchanged = attached_source_unchanged(
            source_path=self.source_path,
            source_state=source_state,
            services=context.services,
        )
        if terminal is None:
            semantic_checks = (
                OutcomeCheck("terminal_output_resolved", False, "no_readable_run_output_reference"),
                OutcomeCheck("header_promoted", False, "no_terminal_dataset"),
                OutcomeCheck("report_row_removed", False, "no_terminal_dataset"),
                OutcomeCheck("header_row_removed", False, "no_terminal_dataset"),
                OutcomeCheck("exact_duplicates_removed", False, "no_terminal_dataset"),
                OutcomeCheck("expected_shape", False, "no_terminal_dataset"),
                OutcomeCheck("business_rows_preserved", False, "no_terminal_dataset"),
            )
            integrity_checks = (
                OutcomeCheck("canonical_completion", canonical_complete, _completion_summary(canonical_complete)),
                OutcomeCheck("source_unchanged", source_unchanged, _source_summary(source_unchanged)),
            )
            return BenchmarkCaseAssessment(
                semantic_checks=semantic_checks,
                integrity_checks=integrity_checks,
            )

        terminal_dataset, output_frame = terminal
        source_dataset = dataset_service.get_dataset(source_state.source_dataset_ids[0])
        source_frame = _load_dataset_frame(source_dataset)
        shape = (int(output_frame.height), int(output_frame.width))
        table_checks = _cleaning_checks(source_frame=source_frame, output_frame=output_frame)
        semantic_checks = (
            OutcomeCheck("terminal_output_resolved", True, "readable_run_output_reference"),
            *table_checks,
        )
        integrity_checks = (
            OutcomeCheck("canonical_completion", canonical_complete, _completion_summary(canonical_complete)),
            OutcomeCheck("source_unchanged", source_unchanged, _source_summary(source_unchanged)),
        )
        del terminal_dataset
        return BenchmarkCaseAssessment(
            semantic_checks=semantic_checks,
            integrity_checks=integrity_checks,
            terminal_shape=shape,
        )

    @staticmethod
    def _resolve_terminal_dataset(
        *,
        snapshot: Any,
        dataset_service: Any,
        source_dataset_ids: set[str],
        run_dataset_ids: frozenset[str],
    ) -> tuple[Any, pl.DataFrame] | None:
        for message in reversed(list(getattr(snapshot, "messages", []))):
            if enum_value(getattr(message, "kind", None)) != "tool_result":
                continue
            if enum_value(getattr(message, "result_status", None)) != "succeeded":
                continue
            for dataset_id in _result_dataset_ids(getattr(message, "value_payload", None)):
                if dataset_id in source_dataset_ids or dataset_id not in run_dataset_ids:
                    continue
                try:
                    dataset = dataset_service.get_dataset(dataset_id)
                    frame = _load_dataset_frame(dataset)
                except Exception:
                    continue
                return dataset, frame
        return None


def _cleaning_checks(*, source_frame: pl.DataFrame, output_frame: pl.DataFrame) -> tuple[OutcomeCheck, ...]:
    if source_frame.height < 2 or source_frame.width != output_frame.width:
        return (
            OutcomeCheck("header_promoted", False, "incompatible_source_or_output_schema"),
            OutcomeCheck("report_row_removed", False, "incompatible_source_or_output_schema"),
            OutcomeCheck("header_row_removed", False, "incompatible_source_or_output_schema"),
            OutcomeCheck("exact_duplicates_removed", False, "incompatible_source_or_output_schema"),
            OutcomeCheck("expected_shape", False, "unexpected_terminal_shape"),
            OutcomeCheck("business_rows_preserved", False, "incompatible_source_or_output_schema"),
        )

    expected_headers = tuple(_cell_text(value) for value in source_frame.row(1))
    normalized_name = lambda name: re.sub(r"[\W_]+", "", name).removesuffix("元")
    output_names = {normalized_name(name): name for name in output_frame.columns}
    header_promoted = (
        len(output_names) == len(expected_headers)
        and set(output_names) == {normalized_name(name) for name in expected_headers}
    )
    if header_promoted:
        output_frame = output_frame.select([
            pl.col(output_names[normalized_name(name)]).alias(name) for name in expected_headers
        ])
    # The final 合计 is a report aggregate, not an additional sale. Compare
    # business values after lossless type normalization, not their export text.
    first = source_frame.columns[0]
    business_frame = source_frame.slice(2).filter((pl.col(first) != "合计").fill_null(True))
    business_frame.columns = list(expected_headers)
    output_hashes = _row_hashes(output_frame)
    business_rows_preserved = bool(
        header_promoted
        and _normalization_preserves_values(business_frame)
        and _normalization_preserves_values(output_frame)
        and _row_hashes(business_frame).unique().sort().equals(output_hashes.unique().sort())
    )
    first_values = output_frame.get_column(output_frame.columns[0]).cast(pl.String)
    report_removed = not first_values.eq(_cell_text(source_frame.row(0)[0])).any()
    header_removed = not first_values.eq(expected_headers[0]).any()
    total_removed = not first_values.eq("合计").any()
    duplicates_removed = output_hashes.n_unique() == output_frame.height
    expected_shape = output_frame.shape == EXPECTED_SHAPE
    return (
        OutcomeCheck("header_promoted", header_promoted, "equivalent_headers" if header_promoted else "headers_not_promoted"),
        OutcomeCheck("report_row_removed", report_removed, "report_row_absent" if report_removed else "report_row_retained"),
        OutcomeCheck("header_row_removed", header_removed, "header_row_absent" if header_removed else "header_row_retained"),
        OutcomeCheck("total_row_removed", total_removed, "total_row_absent" if total_removed else "total_row_retained"),
        OutcomeCheck("exact_duplicates_removed", duplicates_removed, "no_exact_duplicates" if duplicates_removed else "exact_duplicates_retained"),
        OutcomeCheck("expected_shape", expected_shape, "expected_terminal_shape" if expected_shape else "unexpected_terminal_shape"),
        OutcomeCheck("business_rows_preserved", business_rows_preserved, "business_rows_match" if business_rows_preserved else "business_rows_differ"),
    )


def _row_hashes(frame: pl.DataFrame) -> pl.Series:
    normalized = frame.select(
        [_normalized_value_expression(column).alias(column) for column in frame.columns]
    )
    return normalized.hash_rows()


def _cell_text_expression(column: str) -> pl.Expr:
    text = pl.col(column).cast(pl.String, strict=False).str.strip_chars()
    return pl.when(text.is_in(["", "--"])).then(None).otherwise(text)


def _normalized_value_expression(column: str) -> pl.Expr:
    text = _cell_text_expression(column)
    if column.endswith("(元)") or column.endswith("数量"):
        return text.cast(pl.Float64, strict=False)
    if column == "营业日期":
        dated = text.str.replace_all("/", "-")
        return pl.coalesce(
            dated.str.to_date("%Y-%m-%d", strict=False),
            dated.str.to_datetime("%Y-%m-%d %H:%M:%S%.f", strict=False).dt.date(),
        )
    if column in {"点菜时间", "下单时间", "接单/结账/退菜时间"}:
        return text.str.replace_all("/", "-").str.to_datetime("%Y-%m-%d %H:%M:%S%.f", strict=False)
    return text


def _normalization_preserves_values(frame: pl.DataFrame) -> bool:
    lost = frame.select([
        (_cell_text_expression(column).is_not_null() & _normalized_value_expression(column).is_null()).any().alias(column)
        for column in frame.columns
    ])
    return not any(lost.row(0))


def _result_dataset_ids(value: Any) -> tuple[str, ...]:
    candidates: list[str] = []
    if isinstance(value, dict):
        direct = value.get("dataset_id")
        if isinstance(direct, str) and direct.strip():
            candidates.append(direct.strip())
        multiple = value.get("dataset_ids")
        if isinstance(multiple, list):
            candidates.extend(item.strip() for item in multiple if isinstance(item, str) and item.strip())
    elif isinstance(value, str):
        metadata = value.split("\n\n", 1)[0]
        candidates.extend(match.group(1) for match in _DATASET_ID_LINE.finditer(metadata))
    return tuple(dict.fromkeys(candidates))


def _load_dataset_frame(dataset: Any) -> pl.DataFrame:
    return load_tabular_frame(Path(dataset.source_path), dataset.source_format)


def _cell_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _completion_summary(passed: bool) -> str:
    return "canonical_assistant_completion" if passed else "not_a_terminal_assistant_completion"


def _source_summary(passed: bool) -> str:
    return "external_and_registered_source_unchanged" if passed else "source_changed_or_unreadable"


def test_cleaning_april(agent_harness_benchmark) -> None:
    """Measure the public cleaning outcome with an explicitly supplied source."""

    agent_harness_benchmark.run(
        AprilDineInSalesCleaningCase(agent_harness_benchmark.require_source())
    )
