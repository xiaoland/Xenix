"""Outcome oracle for the real April dine-in sales cleaning benchmark."""

from __future__ import annotations

from pathlib import Path
import json
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
    linked_tables,
    sha256_file,
)
from ._infra.contracts import (
    BenchmarkCaseAssessment,
    BenchmarkCaseContext,
    BenchmarkCaseServices,
    BenchmarkInputError,
    JudgeInput,
    JudgeRubric,
    OutcomeCheck,
)


CASE_ID = "cleaning.april_dine_in_sales"
EXPECTED_FILE_SIZE = 116_459_191
EXPECTED_SHA256 = "6B902DE50277E727FE936FFC4FE072B4D8B1C3D60A7D85413E114B72C4140E31"
DELIVERY_RUBRIC = JudgeRubric(
    rubric_id="cleaning.april.primary_delivery.v1",
    score_dimensions=("primary_delivery_correctness", "delivery_explanation_consistency"),
    allowed_reason_codes=("primary_delivery_preserved", "primary_delivery_loses_business_rows", "primary_delivery_ambiguous"),
    scoring_guidance=("以用户被告知应使用的主要清洗结果为准。正确的核对文件或中间产物不能补救主要交付物的数据损失。",),
)


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

    def build_submission(self, *, thread_id: int, fq_model_key: str) -> SubmitUserTurnInput:
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

    def assess(self, *, context: BenchmarkCaseContext) -> BenchmarkCaseAssessment:
        state = context.source_state
        completed = canonical_completion(context.snapshot)
        available = isinstance(state, AttachedSourceState) and bool(state.source_dataset_ids)
        unchanged = available and attached_source_unchanged(
            source_path=self.source_path, source_state=state, services=context.services,
        )
        integrity = (
            OutcomeCheck("canonical_completion", completed, _completion_summary(completed)),
            OutcomeCheck("source_unchanged", unchanged, _source_summary(unchanged)),
        )
        tables = linked_tables(context) if available else {}
        if not tables:
            return BenchmarkCaseAssessment(
                semantic_checks=(OutcomeCheck("public_cleaned_table", False, "linked_table_missing"),),
                integrity_checks=integrity,
            )
        source = _load_dataset_frame(context.services.datasets.get_dataset(state.source_dataset_ids[0]))
        # A response may link several exports; inspect the delivered values, not
        # whichever intermediate Dataset happened to be created last.
        candidates = [(uri, frame, _cleaning_checks(source_frame=source, output_frame=frame)) for uri, frame in tables.items()]
        _, frame, checks = max(candidates, key=lambda candidate: sum(check.passed for check in candidate[2]))
        judge = None
        if all(check.passed for check in (*checks, *integrity)):
            evidence = [{"uri": uri, "shape": candidate.shape, "checks": [check.to_payload() for check in candidate_checks]} for uri, candidate, candidate_checks in candidates]
            judge = JudgeInput(
                rubric=DELIVERY_RUBRIC,
                task_intent="清洗上传的 4 月堂食销售表。",
                facts=(
                    "业务真值为 486119 条销售明细；报告行、表头行和合计行应剔除，全空列可省略。",
                    "这些相同外观的销售行参与订单金额对账，不能以行值相等为依据删去；business_rows_preserved 已独立核验全部业务值及重复次数。",
                    "根据最终说明识别主要交付表，要求其 business_rows_preserved=true。主要推荐损失业务行的表，即使同时链接正确中间表或承认假设，也应判失败。",
                ),
                artifact_evidence=(
                    f"final_answer: {getattr(context.snapshot.messages[-1], 'text', '')}",
                    json.dumps(evidence, ensure_ascii=False),
                ),
            )
        return BenchmarkCaseAssessment(
            semantic_checks=(OutcomeCheck("public_cleaned_table", True, "linked_table_readable"), *checks),
            integrity_checks=integrity,
            judge_input=judge,
            judge_required=True,
            terminal_shape=frame.shape,
        )


def _cleaning_checks(*, source_frame: pl.DataFrame, output_frame: pl.DataFrame) -> tuple[OutcomeCheck, ...]:
    expected_headers = tuple(_cell_text(value) for value in source_frame.row(1))
    first = source_frame.columns[0]
    business = source_frame.slice(2).filter((pl.col(first) != "合计").fill_null(True))
    business.columns = list(expected_headers)
    nonempty = business.select([_cell_text_expression(name).is_not_null().any().alias(name) for name in expected_headers]).row(0)
    required = [name for name, populated in zip(expected_headers, nonempty, strict=True) if populated]
    normalized_name = lambda name: re.sub(r"[\W_]+", "", name).removesuffix("元")
    output_names = {normalized_name(name): name for name in output_frame.columns}
    names_unique = len(output_names) == output_frame.width
    missing = [name for name in required if normalized_name(name) not in output_names]
    unassigned = [name for name in output_frame.columns if normalized_name(name) not in {normalized_name(header) for header in expected_headers}]
    if len(missing) == len(unassigned) == 1:
        # Infer a lone renamed column from the remaining slot. Full row-value
        # comparison below still proves whether that interpretation is correct.
        output_names[normalized_name(missing[0])] = unassigned[0]
    headers_match = names_unique and all(normalized_name(name) in output_names for name in required)
    preserved = False
    if headers_match:
        selected = [name for name in expected_headers if normalized_name(name) in output_names]
        output = output_frame.select([pl.col(output_names[normalized_name(name)]).alias(name) for name in selected])
        business = business.select(selected)
        # Equal-looking sale lines can be real repeated purchases. Compare the
        # multiset, including multiplicity; unique() would silently lose sales.
        preserved = (
            output.height == business.height
            and _normalization_preserves_values(business)
            and _normalization_preserves_values(output)
            and _row_hashes(business).sort().equals(_row_hashes(output).sort())
        )
    return (
        OutcomeCheck("header_promoted", headers_match, "business_headers_present" if headers_match else "business_columns_missing_or_ambiguous"),
        OutcomeCheck("business_rows_preserved", preserved, "business_multiset_matches" if preserved else "business_rows_or_values_differ"),
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
