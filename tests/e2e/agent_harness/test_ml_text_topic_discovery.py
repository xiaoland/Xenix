"""Clean-room paid-live Agent case for bilingual topic discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import polars as pl
import pytest

from xenix.services.agent import SourceAttachmentInput, SubmitUserTurnInput

from ._infra.case_support import (
    AttachedSourceState,
    attached_source_unchanged,
    canonical_completion,
    capture_attached_source_state,
    enum_value,
    linked_artifacts,
    linked_tables,
    linked_json_reports,
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


CASE_ID: Final = "ml.text_topic_discovery_v1"
_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "ml_capabilities" / "learning_module_topic_feedback.csv"
_EXPECTED_SIZE = 2_686
_EXPECTED_SHA256 = "7C597F433FD3236556CA6FB3774DF1CBD774AE29DEC61415143577121338E52A"
_DOCUMENT_COLUMN = "feedback_ref"
_RAW_TEXT_COLUMN = "feedback"
_EXPECTED_THEME_PARTITIONS = frozenset(
    {
        frozenset(
            {
                "PULSE-101",
                "PULSE-105",
                "PULSE-108",
                "PULSE-112",
                "PULSE-114",
                "PULSE-118",
                "PULSE-121",
                "PULSE-125",
                "PULSE-129",
                "PULSE-131",
                "PULSE-134",
                "PULSE-136",
            }
        ),
        frozenset(
            {
                "PULSE-103",
                "PULSE-104",
                "PULSE-109",
                "PULSE-111",
                "PULSE-115",
                "PULSE-117",
                "PULSE-122",
                "PULSE-124",
                "PULSE-127",
                "PULSE-130",
                "PULSE-132",
                "PULSE-135",
            }
        ),
        frozenset(
            {
                "PULSE-102",
                "PULSE-106",
                "PULSE-107",
                "PULSE-110",
                "PULSE-113",
                "PULSE-116",
                "PULSE-119",
                "PULSE-120",
                "PULSE-123",
                "PULSE-126",
                "PULSE-128",
                "PULSE-133",
            }
        ),
    }
)


BUSINESS_PROMPT = (
    "这些中英文场地反馈还没有标签。请归纳出三个便于运营理解的主题，给每条反馈标注主题，"
    "并用同一套主题体系为后续反馈提供可复用的分类结果。请交付标注表和质量评估报告，"
    "解释主题含义及可靠程度。汇报时用概括和代表词，不逐条复述客户反馈。"
)


TOPIC_DISCOVERY_RUBRIC = JudgeRubric(
    rubric_id="ml.text_topic_discovery_v1.business_outcome.v1",
    score_dimensions=(
        "topic_delivery",
        "evaluation_grounding",
        "bounded_interpretation",
        "exploratory_limits",
    ),
    allowed_reason_codes=(
        "complete_grounded_outcome",
        "topic_delivery_incomplete",
        "evaluation_evidence_unsupported",
        "topic_interpretation_unbounded",
        "exploratory_truth_boundary_missing",
    ),
)

pytestmark = pytest.mark.agent_harness_live


class TextTopicDiscoveryCase:
    """Measure final public topic outcomes without prescribing a Tool trace."""

    case_id = CASE_ID

    def __init__(self, source_path: Path = _FIXTURE_PATH) -> None:
        self.source_path = source_path

    def validate_input(self) -> str:
        return _validate_fixture(self.source_path)

    def build_submission(self, *, thread_id: int, fq_model_key: str) -> SubmitUserTurnInput:
        return SubmitUserTurnInput(
            thread_id=thread_id,
            text=BUSINESS_PROMPT,
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
        source = pl.read_csv(self.source_path)
        tables = linked_tables(context)
        frame = next((frame for frame in tables.values() if _matches_topic_assignments(frame, source)), None)
        artifacts = linked_artifacts(context)
        models = tuple(uri for uri, artifact in artifacts.items() if enum_value(artifact.kind) == "model")
        reports = linked_json_reports(context)
        evidence = (*_quality_evidence(reports), *_tabular_quality_evidence(tables, source))
        state = context.source_state
        unchanged = isinstance(state, AttachedSourceState) and attached_source_unchanged(
            source_path=self.source_path, source_state=state, services=context.services,
        )
        completed = canonical_completion(context.snapshot)
        semantic = (
            OutcomeCheck("topic_assignments", frame is not None, "linked_three_theme_partition_matches" if frame is not None else "linked_topic_assignments_missing_or_incorrect"),
            OutcomeCheck("reusable_topic_model", bool(models), "linked_model_available" if models else "linked_model_missing"),
            OutcomeCheck("public_quality_evidence", bool(evidence), "linked_quality_facts_available" if evidence else "linked_quality_facts_missing"),
        )
        integrity = (
            OutcomeCheck("canonical_completion", completed, "canonical_completion_observed" if completed else "canonical_completion_missing"),
            OutcomeCheck("source_unchanged", unchanged, "source_unchanged" if unchanged else "source_changed_or_unverifiable"),
        )
        judge = None
        if all(check.passed for check in (*semantic, *integrity)):
            judge = JudgeInput(
                rubric=TOPIC_DISCOVERY_RUBRIC,
                task_intent=BUSINESS_PROMPT,
                facts=(
                    "交付表保留 36 条原始反馈，三个主题的成员划分符合私有真值，标签命名和排列不限。",
                    "未指定算法；主题模型或归纳主题后训练分类器均可。可复用模型必须对应交付的主题体系。",
                    "评估证据须与实际方案及最终结论一致。自行归纳的标签上获得高分类准确率，仅证明复现标签，不能独立证明主题正确或新反馈泛化效果。",
                    "依据列含义及最终说明识别实际交付的主题；若额外给出的预测列与主题划分矛盾，需要据实扣分。可接受表格或结构化质量报告，但存在一个表不等于已提供充分质量证据。",
                    "检查报告是否解释主题含义、可靠程度和局限。训练内指标、随机拆分相似模板、自己生成的标签等证据限制须如实说明；不暗中要求特定算法或固定评估流程。",
                    "用户要求概括和代表词，不逐条复述反馈。公开表本身需要保留逐条标注。",
                ),
                artifact_evidence=(
                    f"final_answer: {_terminal_text(context.snapshot)}",
                    f"linked_reusable_models: {models}",
                    "public_assignment_columns: " + json.dumps(_topic_projection(frame, source), ensure_ascii=False),
                    *evidence,
                ),
            )
        return BenchmarkCaseAssessment(
            semantic_checks=semantic, integrity_checks=integrity, judge_input=judge, judge_required=True,
            terminal_shape=frame.shape if frame is not None else None,
        )


def _matches_topic_assignments(frame: pl.DataFrame, source: pl.DataFrame) -> bool:
    return _topic_projection(frame, source) is not None


def _topic_projection(frame: pl.DataFrame, source: pl.DataFrame) -> dict[str, Any] | None:
    if frame.height != source.height:
        return None
    expected = dict(source.select(_DOCUMENT_COLUMN, _RAW_TEXT_COLUMN).iter_rows())
    for document_column in frame.columns:
        documents = frame.get_column(document_column).cast(pl.String).to_list()
        if len(set(documents)) != frame.height or set(documents) != set(expected):
            continue
        for text_column in frame.columns:
            if dict(zip(documents, frame.get_column(text_column).to_list(), strict=True)) != expected:
                continue
            candidates = [{
                "column": column,
                "distinct_values": frame.get_column(column).n_unique(),
                "matches_private_themes": _matches_private_topic_partition(frame, topic_column=column, document_column=document_column),
            } for column in frame.columns if column not in {document_column, text_column}]
            if any(candidate["matches_private_themes"] for candidate in candidates):
                return {"document_column": document_column, "text_column": text_column, "candidate_columns": candidates}
    return None


def _tabular_quality_evidence(tables: dict[str, pl.DataFrame], source: pl.DataFrame) -> tuple[str, ...]:
    evidence = []
    source_values = set(source.get_column(_DOCUMENT_COLUMN).to_list()) | set(source.get_column(_RAW_TEXT_COLUMN).to_list())
    for uri, table in tables.items():
        if _matches_topic_assignments(table, source):
            continue
        # Quality tables may use local-language headers. Preserve their facts,
        # leaving sufficiency to the Judge; omit any document-level source data.
        columns = [column for column in table.columns if not source_values.intersection(table.get_column(column).cast(pl.String).to_list())]
        if columns and table.height:
            evidence.append(json.dumps({"uri": uri, "public_quality_table": table.select(columns).to_dicts()}, ensure_ascii=False, default=str))
    return tuple(evidence)


def _quality_evidence(reports: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    evidence = []
    for uri, report in reports.items():
        public = {key: report[key] for key in (
            "model_key", "evaluation_kind", "evaluation", "baseline_evaluation", "comparison", "split_facts", "training_scopes",
        ) if key in report}
        # These are aggregate evaluation sections. Do not send training rows,
        # document-level assignments, complete vocabularies or internal paths.
        for domain in ("text_topic_evaluation", "text_classification_evaluation", "clustering_evaluation"):
            facts = report.get(domain)
            if isinstance(facts, dict):
                public[domain] = {key: facts[key] for key in (
                    "quality", "stability", "split", "isolation", "leakage", "limitations", "prevalence", "profiles", "null_baseline", "sizes",
                ) if key in facts}
        if public.get("evaluation") or any(public.get(key) for key in ("text_topic_evaluation", "text_classification_evaluation", "clustering_evaluation")):
            evidence.append(json.dumps({"uri": uri, "public_evaluation": public}, ensure_ascii=False, default=str))
    return tuple(evidence)


def _validate_fixture(path: Path) -> str:
    if not path.is_file():
        raise BenchmarkInputError("missing_fixture")
    if path.stat().st_size != _EXPECTED_SIZE:
        raise BenchmarkInputError("fixture_size_mismatch")
    digest = sha256_file(path)
    if digest != _EXPECTED_SHA256:
        raise BenchmarkInputError("fixture_hash_mismatch")
    return digest


def _matches_private_topic_partition(
    frame: pl.DataFrame,
    *,
    topic_column: str,
    document_column: str = _DOCUMENT_COLUMN,
) -> bool:
    """Compare document sets so arbitrary topic-label permutations are irrelevant."""

    if document_column not in frame.columns or topic_column not in frame.columns or frame.height != 36:
        return False
    observed: dict[str, set[str]] = {}
    seen_documents: set[str] = set()
    try:
        for row in frame.select(document_column, topic_column).iter_rows(named=True):
            document = str(row[document_column]).strip()
            raw_topic = row[topic_column]
            if not document or document in seen_documents or raw_topic is None:
                return False
            topic = str(raw_topic).strip()
            if not topic:
                return False
            seen_documents.add(document)
            observed.setdefault(topic, set()).add(document)
    except KeyError, TypeError, ValueError:
        return False
    observed_signature = frozenset(frozenset(documents) for documents in observed.values())
    return bool(
        seen_documents == set().union(*_EXPECTED_THEME_PARTITIONS)
        and len(observed) == 3
        and observed_signature == _EXPECTED_THEME_PARTITIONS
    )


def _terminal_text(snapshot: Any | None) -> str:
    messages = list(getattr(snapshot, "messages", [])) if snapshot is not None else []
    if not messages:
        return ""
    return str(getattr(messages[-1], "text", "") or "")


def test_ml_text_topic_discovery(agent_harness_benchmark) -> None:
    """Measure public bilingual topic outcomes without prescribing a Tool trace."""

    agent_harness_benchmark.run(TextTopicDiscoveryCase())
