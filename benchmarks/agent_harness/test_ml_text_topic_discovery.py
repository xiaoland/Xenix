"""Clean-room paid-live Agent case for bilingual topic discovery."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import unicodedata
from typing import Any, Final

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
    is_within,
    sha256_file,
    source_dataset_ids_for_external_digest,
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
_EXPECTED_RESOURCE_IDENTITY_DIGEST = "4a90373f81203fe0c091d125eb86e016af556441d78aa74119984ebd961e9d75"
_EXPECTED_SPECIFICATION_DIGEST = "fbdd0c8df797beba6435abfec9701238045d171c472710342e203e7bf0d05ea4"
_EXPECTED_PREPARED_TEXT_DIGEST = "4c2a2e7a66867eff9ed49615a4a9849aa5c8d25fbad5146d7224951417e1d8ba"
_EXPECTED_GROUP_ASSIGNMENT_DIGEST = "bb5137e13acefc5556f369e1df3914bdba96e4bd59748ccee488c18290a53224"
_DOCUMENT_COLUMN = "feedback_ref"
_RAW_TEXT_COLUMN = "feedback"
_TOPIC_COLUMN = "dominant_topic"
_TOPIC_SHARE_COLUMNS = ("topic_1_share", "topic_2_share", "topic_3_share")
_OUTPUT_COLUMNS = {
    _DOCUMENT_COLUMN,
    _RAW_TEXT_COLUMN,
    _TOPIC_COLUMN,
    "topic_score",
    *_TOPIC_SHARE_COLUMNS,
}
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
_ARTIFACT_URI = re.compile(r"artifact://[A-Za-z0-9]+(?:\?[^)\s>]+)?")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"(?i)\bPULSE-[A-Z0-9-]+\b")
_URL_OR_EMAIL = re.compile(r"(?i)(?:https?://|www\.|\S+@\S+)")
_WINDOWS_PATH = re.compile(r"(?i)[A-Z]:[\\/]")


@dataclass(frozen=True)
class _TopicApiContract:
    model_key: str
    evaluation_kind: str
    task_kind: str
    text_role: str
    group_role: str
    parameter_names: frozenset[str]
    evaluation_facts_key: str
    apply_facts_key: str
    public_result_columns: frozenset[str]
    maximum_topics: int
    maximum_terms_per_topic: int


_CANDIDATE_API = _TopicApiContract(
    model_key="text.topic_modeling.multilingual_lda",
    evaluation_kind="topic_modeling",
    task_kind="text_analyzer",
    text_role="text",
    group_role="group",
    parameter_names=frozenset(
        {
            "preparation_profile",
            "phrase_mode",
            "max_features",
            "topic_count",
            "displayed_term_count",
            "custom_dictionary_dataset_ids",
            "stopword_dataset_ids",
        }
    ),
    evaluation_facts_key="text_topic_evaluation",
    apply_facts_key="text_topic_apply_facts",
    public_result_columns=frozenset(_OUTPUT_COLUMNS),
    maximum_topics=20,
    maximum_terms_per_topic=12,
)
_FROZEN_API: Final[_TopicApiContract] = _CANDIDATE_API

BUSINESS_PROMPT = (
    "附件为无标签双语场地反馈。先画像并用 model.metadata 核对 "
    "text.topic_modeling.multilingual_lda 的 raw text 角色和 7 项参数；将 feedback 绑定 text，"
    "使用 multilingual_business_v1、unigram、max_features=5000、topic_count=3、"
    "displayed_term_count=5，两个 resource Dataset ID 列表为空。交付 FIT assignment Dataset/Artifact "
    "与 held-out Evaluate report Artifact；再用全量 analyzer 对同附件 raw apply，交付 APPLY "
    "Dataset/Artifact。最终列出两个 result_dataset_id、三个 Artifact 链接和 7 个参数名。"
    "仅用报告内有限 top terms、perplexity/coherence/stability 和零重叠隔离事实解释结果；说明主题编号可置换、"
    "主题只是探索结构，离线证据不证明因果效果，也不授予自动业务决策权。最终回答不得复述任何 feedback "
    "原文、任何 feedback_ref 值或任何本地路径；说明隐私边界时也只使用字段名，不举示例值。"
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


@dataclass(frozen=True)
class _TopicOutcome:
    fit_dataset: Any | None
    fit_frame: pl.DataFrame | None
    fit_artifact: Any | None
    apply_dataset: Any | None
    apply_frame: pl.DataFrame | None
    apply_artifact: Any | None


class TextTopicDiscoveryCase:
    """Measure final public topic outcomes without prescribing a Tool trace."""

    case_id = CASE_ID

    def __init__(self, source_path: Path = _FIXTURE_PATH) -> None:
        self.source_path = source_path

    def validate_input(self) -> str:
        return _validate_fixture(self.source_path)

    def build_submission(self, *, thread_id: str, fq_model_key: str) -> SubmitUserTurnInput:
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
        outcome = _resolve_topic_outcomes(context)
        report_artifact, report = _resolve_evaluation_report(context)
        frames_agree = _topic_outputs_agree(outcome.fit_frame, outcome.apply_frame)
        grounding_gaps = _final_answer_grounding_gaps(
            _terminal_text(context.snapshot),
            report,
            fit_dataset=outcome.fit_dataset,
            apply_dataset=outcome.apply_dataset,
        )
        terminal_privacy_failures = _terminal_privacy_failure_kinds(_terminal_text(context.snapshot))
        terminal_safe = not terminal_privacy_failures
        completed = canonical_completion(context.snapshot)
        source_unchanged = _source_unchanged(self, context)
        isolated = _state_isolated(
            context,
            (outcome.fit_artifact, outcome.apply_artifact, report_artifact),
        )
        semantic_checks = (
            OutcomeCheck(
                "fit_topic_assignments",
                outcome.fit_frame is not None and outcome.fit_artifact is not None,
                (
                    "fit_assignment_dataset_and_artifact_observed"
                    if outcome.fit_frame is not None and outcome.fit_artifact is not None
                    else "fit_assignment_dataset_or_artifact_missing"
                ),
            ),
            OutcomeCheck(
                "apply_topic_assignments",
                outcome.apply_frame is not None and outcome.apply_artifact is not None,
                (
                    "apply_assignment_dataset_and_artifact_observed"
                    if outcome.apply_frame is not None and outcome.apply_artifact is not None
                    else "apply_assignment_dataset_or_artifact_missing"
                ),
            ),
            OutcomeCheck(
                "stable_fit_apply_identity",
                frames_agree,
                ("fit_and_apply_topic_outputs_agree" if frames_agree else "fit_and_apply_topic_outputs_diverge"),
            ),
            OutcomeCheck(
                "public_group_safe_evaluation",
                report is not None and report_artifact is not None,
                (
                    "topic_quality_stability_and_isolation_facts_observed"
                    if report is not None and report_artifact is not None
                    else "topic_evaluation_report_missing_or_invalid"
                ),
            ),
            OutcomeCheck(
                "grounded_final_answer",
                not grounding_gaps,
                (
                    "topic_evidence_and_limits_grounded"
                    if not grounding_gaps
                    else "topic_explanation_not_grounded:" + ",".join(grounding_gaps)
                ),
            ),
            OutcomeCheck(
                "privacy_safe_public_outcome",
                terminal_safe,
                (
                    "final_answer_contains_only_bounded_public_facts"
                    if terminal_safe
                    else "final_answer_private_values:" + ",".join(terminal_privacy_failures)
                ),
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
        deterministic_passed = all(check.passed for check in semantic_checks)
        integrity_passed = all(check.passed for check in integrity_checks)
        judge_input = (
            _build_judge_input(report) if deterministic_passed and integrity_passed and report is not None else None
        )
        terminal_frame = outcome.apply_frame if outcome.apply_frame is not None else outcome.fit_frame
        return BenchmarkCaseAssessment(
            semantic_checks=semantic_checks,
            integrity_checks=integrity_checks,
            judge_input=judge_input,
            judge_required=True,
            terminal_shape=((terminal_frame.height, terminal_frame.width) if terminal_frame is not None else None),
        )


def _validate_fixture(path: Path) -> str:
    if not path.is_file():
        raise BenchmarkInputError("missing_fixture")
    if path.stat().st_size != _EXPECTED_SIZE:
        raise BenchmarkInputError("fixture_size_mismatch")
    digest = sha256_file(path)
    if digest != _EXPECTED_SHA256:
        raise BenchmarkInputError("fixture_hash_mismatch")
    return digest


def _resolve_topic_outcomes(context: BenchmarkCaseContext) -> _TopicOutcome:
    source_ids = source_dataset_ids_for_external_digest(
        snapshot=context.snapshot,
        services=context.services,
        digest=_EXPECTED_SHA256,
    )
    datasets = list(context.services.datasets.list_datasets())
    by_id = {str(dataset.id): dataset for dataset in datasets}
    artifacts = _linked_artifacts(context)
    fit_dataset = fit_frame = fit_artifact = None
    apply_dataset = apply_frame = apply_artifact = None
    for dataset in datasets:
        if not _is_run_descendant(
            dataset,
            by_id,
            source_ids,
            context.run_dataset_ids,
        ):
            continue
        try:
            frame = load_tabular_frame(Path(dataset.source_path), dataset.source_format)
        except Exception:
            continue
        if not _matches_topic_assignments(frame):
            continue
        if apply_dataset is None:
            candidate_apply = _resolve_apply_artifact(
                dataset,
                artifacts,
                context.runtime_home,
            )
            if candidate_apply is not None and _artifact_matches_assignments(candidate_apply):
                apply_dataset, apply_frame, apply_artifact = dataset, frame, candidate_apply
                continue
        if fit_dataset is None:
            candidate_fit = _resolve_fit_artifact(
                dataset,
                artifacts,
                context.runtime_home,
            )
            if candidate_fit is not None and _artifact_matches_assignments(candidate_fit):
                fit_dataset, fit_frame, fit_artifact = dataset, frame, candidate_fit
    if fit_dataset is not None and apply_dataset is not None and str(fit_dataset.id) == str(apply_dataset.id):
        return _TopicOutcome(None, None, None, None, None, None)
    return _TopicOutcome(
        fit_dataset,
        fit_frame,
        fit_artifact,
        apply_dataset,
        apply_frame,
        apply_artifact,
    )


def _matches_topic_assignments(frame: pl.DataFrame) -> bool:
    if frame.height != 36 or set(frame.columns) != _FROZEN_API.public_result_columns:
        return False
    try:
        source = pl.read_csv(_FIXTURE_PATH)
        expected_text = dict(source.select(_DOCUMENT_COLUMN, _RAW_TEXT_COLUMN).iter_rows())
        observed_documents: set[str] = set()
        for row in frame.to_dicts():
            document = str(row[_DOCUMENT_COLUMN]).strip()
            raw_text = str(row[_RAW_TEXT_COLUMN])
            dominant_topic = int(row[_TOPIC_COLUMN])
            score = float(row["topic_score"])
            shares = [float(row[column]) for column in _TOPIC_SHARE_COLUMNS]
            if (
                document in observed_documents
                or expected_text.get(document) != raw_text
                or dominant_topic not in (1, 2, 3)
                or not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in shares)
                or not math.isfinite(score)
                or not math.isclose(sum(shares), 1.0, rel_tol=1e-9, abs_tol=1e-9)
                or not math.isclose(score, max(shares), rel_tol=1e-9, abs_tol=1e-9)
                or dominant_topic != shares.index(max(shares)) + 1
            ):
                return False
            observed_documents.add(document)
    except KeyError, OSError, TypeError, ValueError:
        return False
    return bool(
        observed_documents == set(expected_text) and _matches_private_topic_partition(frame, topic_column=_TOPIC_COLUMN)
    )


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


def _topic_outputs_agree(
    fit_frame: pl.DataFrame | None,
    apply_frame: pl.DataFrame | None,
) -> bool:
    if fit_frame is None or apply_frame is None:
        return False
    try:
        columns = [_DOCUMENT_COLUMN, _TOPIC_COLUMN, "topic_score", *_TOPIC_SHARE_COLUMNS]
        left = fit_frame.select(columns).sort(_DOCUMENT_COLUMN)
        right = apply_frame.select(columns).sort(_DOCUMENT_COLUMN)
        return left.equals(right)
    except Exception:
        return False


def _resolve_fit_artifact(
    dataset: Any,
    artifacts: tuple[Any, ...],
    runtime_home: Path,
) -> Any | None:
    task_id = str(getattr(dataset, "ml_task_id", "") or "")
    if not task_id:
        return None
    for artifact in artifacts:
        metadata = getattr(artifact, "metadata_payload", {})
        path = Path(str(getattr(artifact, "absolute_path", "")))
        if (
            enum_value(getattr(artifact, "kind", None)) == "file"
            and bool(getattr(artifact, "ready_to_open", False))
            and bool(getattr(artifact, "exists", False))
            and is_within(path, runtime_home)
            and isinstance(metadata, dict)
            and metadata.get("ml_task_id") == task_id
            and metadata.get("ml_task_artifact_kind") == "export_file"
        ):
            return artifact
    return None


def _resolve_apply_artifact(
    dataset: Any,
    artifacts: tuple[Any, ...],
    runtime_home: Path,
) -> Any | None:
    for artifact in artifacts:
        metadata = getattr(artifact, "metadata_payload", {})
        path = Path(str(getattr(artifact, "absolute_path", "")))
        if (
            enum_value(getattr(artifact, "kind", None)) == "prediction"
            and bool(getattr(artifact, "ready_to_open", False))
            and bool(getattr(artifact, "exists", False))
            and is_within(path, runtime_home)
            and isinstance(metadata, dict)
            and metadata.get("result_dataset_id") == dataset.id
            and metadata.get("ml_task_artifact_kind") == "apply_result"
        ):
            return artifact
    return None


def _artifact_matches_assignments(artifact: Any) -> bool:
    path = Path(str(getattr(artifact, "absolute_path", "")))
    try:
        return path.suffix.lower() == ".csv" and _matches_topic_assignments(pl.read_csv(path))
    except Exception:
        return False


def _resolve_evaluation_report(
    context: BenchmarkCaseContext,
) -> tuple[Any | None, dict[str, Any] | None]:
    for artifact in _linked_artifacts(context):
        if enum_value(getattr(artifact, "kind", None)) != "report":
            continue
        payload = _read_json_artifact(artifact, context.runtime_home)
        if payload is not None and _matches_evaluation_report(payload):
            return artifact, payload
    return None, None


def _matches_evaluation_report(payload: dict[str, Any]) -> bool:
    evaluation = payload.get("evaluation")
    facts = payload.get(_FROZEN_API.evaluation_facts_key)
    if not (
        payload.get("model_key") == _FROZEN_API.model_key
        and payload.get("evaluation_kind") == _FROZEN_API.evaluation_kind
        and isinstance(evaluation, dict)
        and payload.get("baseline_evaluation") is None
        and payload.get("comparison") is None
        and payload.get("split_facts") is None
        and isinstance(facts, dict)
        and _candidate_metrics_match(evaluation, facts)
        and _topic_facts_match(facts)
        and _facts_are_bounded(facts)
        and _report_is_privacy_safe(payload)
    ):
        return False
    return True


def _candidate_metrics_match(evaluation: dict[str, Any], facts: dict[str, Any]) -> bool:
    metrics = evaluation.get("metrics")
    details = evaluation.get("details")
    quality = facts.get("quality")
    stability = facts.get("stability")
    if not all(isinstance(value, dict) for value in (metrics, details, quality, stability)):
        return False
    assert isinstance(metrics, dict)
    assert isinstance(details, dict)
    assert isinstance(quality, dict)
    assert isinstance(stability, dict)
    try:
        return bool(
            evaluation.get("primary_metric_name") == "heldout_perplexity"
            and set(metrics)
            == {
                "heldout_perplexity",
                "coherence",
                "topic_diversity",
                "resampling_stability",
            }
            and math.isclose(
                float(evaluation.get("primary_metric_value")),
                float(quality.get("heldout_perplexity")),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            and math.isclose(
                float(metrics.get("heldout_perplexity")),
                float(quality.get("heldout_perplexity")),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            and math.isclose(
                float(metrics.get("coherence")),
                float(quality.get("mean_coherence")),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            and math.isclose(
                float(metrics.get("topic_diversity")),
                float(quality.get("term_diversity")),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            and math.isclose(
                float(metrics.get("resampling_stability")),
                float(stability.get("mean_matched_cosine")),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            and details.get("dominant_topic_digest") == quality.get("dominant_topic_digest")
            and details.get("topic_label_identity_digest") == facts.get("topic_label_identity_digest")
        )
    except TypeError, ValueError:
        return False


def _topic_facts_match(facts: dict[str, Any]) -> bool:
    specification = facts.get("specification")
    preparation = facts.get("preparation")
    isolation = facts.get("isolation")
    vectorization = facts.get("vectorization")
    split = facts.get("split")
    quality = facts.get("quality")
    stability = facts.get("stability")
    prevalence = facts.get("prevalence")
    profiles = facts.get("profiles")
    limitations = facts.get("limitations")
    if not all(
        isinstance(value, expected_type)
        for value, expected_type in (
            (specification, dict),
            (preparation, dict),
            (isolation, dict),
            (vectorization, dict),
            (split, dict),
            (quality, dict),
            (stability, dict),
            (prevalence, list),
            (profiles, list),
            (limitations, list),
        )
    ):
        return False
    assert isinstance(specification, dict)
    assert isinstance(preparation, dict)
    assert isinstance(isolation, dict)
    assert isinstance(vectorization, dict)
    assert isinstance(split, dict)
    assert isinstance(quality, dict)
    assert isinstance(stability, dict)
    assert isinstance(prevalence, list)
    assert isinstance(profiles, list)
    assert isinstance(limitations, list)
    try:
        return bool(
            facts.get("protocol_key") == "multilingual_topic_discovery.v1"
            and _specification_matches(specification)
            and _preparation_matches(preparation, specification)
            and _isolation_matches(isolation)
            and _vectorization_matches(vectorization)
            and _split_matches(split)
            and _quality_matches(quality)
            and _stability_matches(stability)
            and _prevalence_matches(prevalence)
            and _profiles_match(profiles)
            and _is_sha256(facts.get("topic_label_identity_digest"))
            and bool(limitations)
            and len(limitations) <= 8
            and all(isinstance(value, str) and 1 <= len(value) <= 512 for value in limitations)
        )
    except TypeError, ValueError:
        return False


def _specification_matches(specification: dict[str, Any]) -> bool:
    return bool(
        specification.get("profile_key") == "multilingual_business_v1"
        and specification.get("normalization_policy_key") == "unicode_nfkc_casefold_mask_entities.v1"
        and specification.get("tokenizer_policy_key") == "jieba_multilingual_business.v1"
        and specification.get("phrase_mode") == "unigram"
        and specification.get("ngram_max") == 1
        and specification.get("custom_dictionary_references") == []
        and specification.get("stopword_references") == []
        and specification.get("resource_identity_digest") == _EXPECTED_RESOURCE_IDENTITY_DIGEST
        and specification.get("specification_digest") == _EXPECTED_SPECIFICATION_DIGEST
    )


def _preparation_matches(
    preparation: dict[str, Any],
    specification: dict[str, Any],
) -> bool:
    return bool(
        preparation.get("specification_digest") == specification.get("specification_digest")
        and preparation.get("source_row_count") == 36
        and preparation.get("eligible_row_count") == 36
        and preparation.get("missing_text_row_count") == 0
        and preparation.get("non_empty_text_row_count") == 36
        and preparation.get("empty_after_preparation_row_count") == 0
        and preparation.get("cjk_text_row_count") == 0
        and preparation.get("latin_text_row_count") == 0
        and preparation.get("mixed_script_text_row_count") == 36
        and preparation.get("token_count") == 285
        and preparation.get("custom_dictionary_term_count") == 0
        and preparation.get("stopword_term_count") == 49
        and preparation.get("custom_term_match_count") == 0
        and preparation.get("collapsed_exact_duplicate_row_count") == 24
        and preparation.get("collapsed_template_duplicate_row_count") == 24
        and preparation.get("prepared_text_digest") == _EXPECTED_PREPARED_TEXT_DIGEST
    )


def _isolation_matches(isolation: dict[str, Any]) -> bool:
    return bool(
        isolation.get("policy_key") == "business_template_connected_union.v1"
        and isolation.get("business_group_supplied") is False
        and isolation.get("eligible_row_count") == 36
        and isolation.get("business_group_count") == 0
        and isolation.get("template_group_count") == 12
        and isolation.get("connected_group_count") == 12
        and isolation.get("near_duplicate_edge_count") == 0
        and isolation.get("partition_group_overlap_count") == 0
        and isolation.get("group_assignment_digest") == _EXPECTED_GROUP_ASSIGNMENT_DIGEST
    )


def _vectorization_matches(vectorization: dict[str, Any]) -> bool:
    transformed = vectorization.get("transformed_feature_count")
    return bool(
        vectorization.get("fit_row_count") == 27
        and vectorization.get("inspected_row_count") == 9
        and vectorization.get("empty_after_preparation_row_count") == 0
        and vectorization.get("out_of_vocabulary_row_count") == 0
        and isinstance(transformed, int)
        and 15 <= transformed <= 5_000
        and _is_sha256(vectorization.get("vocabulary_digest"))
    )


def _split_matches(split: dict[str, Any]) -> bool:
    return bool(
        split.get("policy_key") == "connected_group_hash_holdout.v1"
        and split.get("eligible_row_count") == 36
        and split.get("train_row_count") == 27
        and split.get("holdout_row_count") == 9
        and split.get("connected_group_count") == 12
        and split.get("train_group_count") == 9
        and split.get("holdout_group_count") == 3
        and split.get("group_overlap_count") == 0
        and _is_sha256(split.get("source_dataset_snapshot_digest"))
        and _is_sha256(split.get("train_membership_digest"))
        and _is_sha256(split.get("holdout_membership_digest"))
    )


def _quality_matches(quality: dict[str, Any]) -> bool:
    try:
        return bool(
            quality.get("policy_key") == "heldout_topic_quality.v1"
            and quality.get("topic_count") == 3
            and quality.get("train_document_count") == 27
            and quality.get("heldout_document_count") == 9
            and math.isfinite(float(quality.get("heldout_perplexity")))
            and float(quality.get("heldout_perplexity")) > 0.0
            and -1.0 <= float(quality.get("mean_coherence")) <= 1.0
            and 0.0 <= float(quality.get("term_diversity")) <= 1.0
            and _is_sha256(quality.get("dominant_topic_digest"))
        )
    except TypeError, ValueError:
        return False


def _stability_matches(stability: dict[str, Any]) -> bool:
    try:
        requested = int(stability.get("requested_run_count"))
        successful = int(stability.get("successful_run_count"))
        failed = int(stability.get("failed_run_count"))
        mean = float(stability.get("mean_matched_cosine"))
        minimum = float(stability.get("minimum_matched_cosine"))
        return bool(
            stability.get("policy_key") == "permutation_matched_topic_stability_5seed.v1"
            and requested == 5
            and successful + failed == requested
            and successful >= 4
            and 0.0 <= minimum <= mean <= 1.0
        )
    except TypeError, ValueError:
        return False


def _prevalence_matches(prevalence: list[Any]) -> bool:
    labels: set[int] = set()
    dominant_count = 0
    mean_total = 0.0
    try:
        for raw_fact in prevalence:
            if not isinstance(raw_fact, dict):
                return False
            label = int(raw_fact.get("topic_label"))
            count = int(raw_fact.get("dominant_document_count"))
            mean = float(raw_fact.get("mean_prevalence"))
            if label in labels or count < 0 or not 0.0 <= mean <= 1.0:
                return False
            labels.add(label)
            dominant_count += count
            mean_total += mean
    except TypeError, ValueError:
        return False
    return bool(
        labels == {1, 2, 3} and dominant_count == 9 and math.isclose(mean_total, 1.0, rel_tol=1e-9, abs_tol=1e-9)
    )


def _profiles_match(profiles: list[Any]) -> bool:
    if len(profiles) != 3:
        return False
    labels: set[int] = set()
    topic_terms: list[list[Any]] = []
    try:
        for raw_profile in profiles:
            if not isinstance(raw_profile, dict):
                return False
            label = int(raw_profile.get("topic_label"))
            raw_terms = raw_profile.get("top_terms")
            if label in labels or not isinstance(raw_terms, list) or len(raw_terms) != 5:
                return False
            labels.add(label)
            terms: list[Any] = []
            for raw_term in raw_terms:
                if not isinstance(raw_term, dict) or set(raw_term) != {"term", "weight"}:
                    return False
                weight = float(raw_term.get("weight"))
                if not math.isfinite(weight) or weight < 0.0:
                    return False
                terms.append(raw_term.get("term"))
            topic_terms.append(terms)
    except TypeError, ValueError:
        return False
    return bool(
        labels == {1, 2, 3}
        and _bounded_sanitized_terms(
            topic_terms,
            maximum_topics=3,
            maximum_terms_per_topic=5,
        )
    )


def _bounded_sanitized_terms(
    topic_terms: list[list[Any]],
    *,
    maximum_topics: int,
    maximum_terms_per_topic: int,
) -> bool:
    """Accept finite explanatory terms, never a vocabulary or identifier dump."""

    if not 1 <= len(topic_terms) <= maximum_topics:
        return False
    for terms in topic_terms:
        if not 1 <= len(terms) <= maximum_terms_per_topic:
            return False
        normalized: set[str] = set()
        for raw_term in terms:
            if not isinstance(raw_term, str):
                return False
            term = raw_term.strip()
            folded = term.casefold()
            if (
                not term
                or len(term) > 48
                or folded in normalized
                or _IDENTIFIER.search(term) is not None
                or _URL_OR_EMAIL.search(term) is not None
                or _WINDOWS_PATH.search(term) is not None
                or term.isdigit()
            ):
                return False
            normalized.add(folded)
    return True


def _facts_are_bounded(facts: dict[str, Any]) -> bool:
    specification = facts.get("specification")
    preparation = facts.get("preparation")
    isolation = facts.get("isolation")
    vectorization = facts.get("vectorization")
    split = facts.get("split")
    quality = facts.get("quality")
    stability = facts.get("stability")
    if not all(
        isinstance(value, dict)
        for value in (
            specification,
            preparation,
            isolation,
            vectorization,
            split,
            quality,
            stability,
        )
    ):
        return False
    assert isinstance(specification, dict)
    assert isinstance(preparation, dict)
    assert isinstance(isolation, dict)
    assert isinstance(vectorization, dict)
    assert isinstance(split, dict)
    assert isinstance(quality, dict)
    assert isinstance(stability, dict)
    return bool(
        set(facts)
        == {
            "protocol_key",
            "specification",
            "preparation",
            "isolation",
            "vectorization",
            "split",
            "quality",
            "stability",
            "topic_label_identity_digest",
            "prevalence",
            "profiles",
            "limitations",
        }
        and set(specification)
        == {
            "profile_key",
            "normalization_policy_key",
            "tokenizer_policy_key",
            "phrase_mode",
            "ngram_max",
            "custom_dictionary_references",
            "stopword_references",
            "resource_identity_digest",
            "specification_digest",
        }
        and set(preparation)
        == {
            "specification_digest",
            "source_row_count",
            "eligible_row_count",
            "missing_text_row_count",
            "non_empty_text_row_count",
            "empty_after_preparation_row_count",
            "cjk_text_row_count",
            "latin_text_row_count",
            "mixed_script_text_row_count",
            "token_count",
            "custom_dictionary_term_count",
            "stopword_term_count",
            "custom_term_match_count",
            "collapsed_exact_duplicate_row_count",
            "collapsed_template_duplicate_row_count",
            "prepared_text_digest",
        }
        and set(isolation)
        == {
            "policy_key",
            "business_group_supplied",
            "eligible_row_count",
            "business_group_count",
            "template_group_count",
            "connected_group_count",
            "near_duplicate_edge_count",
            "partition_group_overlap_count",
            "group_assignment_digest",
        }
        and set(vectorization)
        == {
            "fit_row_count",
            "transformed_feature_count",
            "vocabulary_digest",
            "inspected_row_count",
            "empty_after_preparation_row_count",
            "out_of_vocabulary_row_count",
        }
        and set(split)
        == {
            "policy_key",
            "source_dataset_snapshot_digest",
            "eligible_row_count",
            "train_row_count",
            "holdout_row_count",
            "connected_group_count",
            "train_group_count",
            "holdout_group_count",
            "train_membership_digest",
            "holdout_membership_digest",
            "group_overlap_count",
        }
        and set(quality)
        == {
            "policy_key",
            "topic_count",
            "train_document_count",
            "heldout_document_count",
            "heldout_perplexity",
            "mean_coherence",
            "term_diversity",
            "dominant_topic_digest",
        }
        and set(stability)
        == {
            "policy_key",
            "requested_run_count",
            "successful_run_count",
            "failed_run_count",
            "mean_matched_cosine",
            "minimum_matched_cosine",
        }
        and len(json.dumps(facts, ensure_ascii=False, sort_keys=True)) <= 32_768
    )


def _report_is_privacy_safe(payload: dict[str, Any]) -> bool:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    try:
        frame = pl.read_csv(_FIXTURE_PATH)
        raw_texts = {str(value) for value in frame.get_column(_RAW_TEXT_COLUMN).to_list()}
        private_ids = {str(value) for value in frame.get_column(_DOCUMENT_COLUMN).to_list()}
    except Exception:
        return False
    prohibited_keys = (
        '"raw_text":',
        '"raw_texts":',
        '"documents":',
        '"document_ids":',
        '"vocabulary":',
        '"feature_names":',
        '"matched_text":',
    )
    return not (
        len(serialized) > 65_536
        or any(text in serialized for text in raw_texts)
        or any(identifier in serialized for identifier in private_ids)
        or _WINDOWS_PATH.search(serialized) is not None
        or any(key in serialized for key in prohibited_keys)
    )


def _terminal_is_privacy_safe(text: str) -> bool:
    return not _terminal_privacy_failure_kinds(text)


def _terminal_privacy_failure_kinds(text: str) -> tuple[str, ...]:
    if not text:
        return ("missing_final_answer",)
    try:
        frame = pl.read_csv(_FIXTURE_PATH)
        raw_texts = {str(value) for value in frame.get_column(_RAW_TEXT_COLUMN).to_list()}
        private_ids = {str(value) for value in frame.get_column(_DOCUMENT_COLUMN).to_list()}
    except Exception:
        return ("fixture_unavailable",)
    failures: list[str] = []
    if _WINDOWS_PATH.search(text) is not None:
        failures.append("windows_path")
    if any(raw_text in text for raw_text in raw_texts):
        failures.append("raw_text")
    if any(identifier in text for identifier in private_ids):
        failures.append("private_document_id")
    return tuple(failures)


def _final_answer_grounding_gaps(
    text: str,
    report: dict[str, Any] | None,
    *,
    fit_dataset: Any | None,
    apply_dataset: Any | None,
) -> tuple[str, ...]:
    if not text:
        return ("missing_final_answer",)
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).lower())
    parameter_schema = all(name in normalized for name in _FROZEN_API.parameter_names)
    topic_count = any(
        marker in normalized
        for marker in ("3个主题", "三个主题", "3个topic", "三个topic", "3topics")
    )
    top_terms = any(marker in normalized for marker in ("topterms", "关键词", "主题词", "术语"))
    quality_metrics = all(marker in normalized for marker in ("perplexity", "coherence", "stability"))
    metric_values = _evaluation_values_grounded(normalized, report)
    group = any(marker in normalized for marker in ("connectedgroup", "连接组", "联合组", "group"))
    template = any(marker in normalized for marker in ("模板", "template"))
    zero_overlap = any(marker in normalized for marker in ("零重叠", "无重叠", "0重叠", "zerooverlap"))
    permutation = any(marker in normalized for marker in ("置换", "编号可变", "编号任意", "permutation"))
    exploratory = any(marker in normalized for marker in ("探索", "exploratory"))
    offline = "离线" in normalized or "offline" in normalized
    authority_limit = any(
        marker in normalized for marker in ("不能证明因果", "非因果", "人工复核", "不能自动决策", "不授予自动")
    )
    fit_dataset_id = str(getattr(fit_dataset, "id", "") or "")
    apply_dataset_id = str(getattr(apply_dataset, "id", "") or "")
    public_datasets = bool(
        fit_dataset_id
        and apply_dataset_id
        and fit_dataset_id != apply_dataset_id
        and fit_dataset_id in text
        and apply_dataset_id in text
    )
    checks = (
        ("evaluation_artifact", report is not None),
        ("three_topic_delivery", topic_count),
        ("bounded_top_terms", top_terms),
        ("quality_metrics", quality_metrics and metric_values),
        ("seven_parameter_schema", parameter_schema),
        ("group_template_isolation", group and template and zero_overlap),
        ("topic_label_permutation", permutation),
        ("exploratory_offline_boundary", exploratory and offline and authority_limit),
        ("fit_and_apply_dataset_ids", public_datasets),
        ("fit_apply_and_evaluate_artifact_links", len(_ARTIFACT_URI.findall(text)) >= 3),
    )
    return tuple(name for name, passed in checks if not passed)


def _evaluation_values_grounded(
    normalized_text: str,
    report: dict[str, Any] | None,
) -> bool:
    if report is None:
        return False
    facts = report.get(_FROZEN_API.evaluation_facts_key)
    if not isinstance(facts, dict):
        return False
    quality = facts.get("quality")
    stability = facts.get("stability")
    if not isinstance(quality, dict) or not isinstance(stability, dict):
        return False
    try:
        expected = (
            float(quality["heldout_perplexity"]),
            float(quality["mean_coherence"]),
            float(stability["mean_matched_cosine"]),
        )
    except KeyError, TypeError, ValueError:
        return False
    observed: list[float] = []
    for raw_value, percent in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(%)?", normalized_text):
        value = float(raw_value)
        observed.append(value / 100.0 if percent else value)
    return all(
        any(math.isclose(value, target, rel_tol=5e-4, abs_tol=5e-4) for value in observed) for target in expected
    )


def _build_judge_input(report: dict[str, Any]) -> JudgeInput:
    facts = report[_FROZEN_API.evaluation_facts_key]
    quality = facts["quality"]
    stability = facts["stability"]
    split = facts["split"]
    isolation = facts["isolation"]
    return JudgeInput(
        rubric=TOPIC_DISCOVERY_RUBRIC,
        task_intent=BUSINESS_PROMPT,
        facts=(
            "目标要求交付 FIT 与 raw APPLY 两份公共 assignment Dataset/Artifact，私有真值按主题置换不变。",
            "主题质量必须来自 connected-template holdout；公开报告只允许有限净化术语与聚合事实。",
            "主题是探索结构而非观测真值；离线 perplexity、coherence 与 stability 不证明因果效果。",
            "最终结论不得泄露文档标识、原始文本、完整词表、路径或文档级转储。",
        ),
        artifact_evidence=(
            "public_assignments: fit_rows=36; apply_rows=36; topics=3; permutation_invariant_oracle=true",
            (
                "public_quality: metric=heldout_perplexity; "
                f"perplexity={float(quality['heldout_perplexity']):.6f}; "
                f"coherence={float(quality['mean_coherence']):.6f}; "
                f"stability={float(stability['mean_matched_cosine']):.6f}"
            ),
            (
                "public_isolation: "
                f"connected_groups={int(isolation['connected_group_count'])}; "
                f"template_groups={int(isolation['template_group_count'])}; "
                f"overlap={int(split['group_overlap_count'])}; "
                f"holdout_rows={int(split['holdout_row_count'])}"
            ),
            (
                "public_identity: fit_dataset_linked=true; apply_dataset_linked=true; "
                "fit_artifact_linked=true; apply_artifact_linked=true; "
                "evaluation_artifact_linked=true; source_immutability_verified=true"
            ),
        ),
    )


def _linked_artifacts(context: BenchmarkCaseContext) -> tuple[Any, ...]:
    artifacts: list[Any] = []
    seen: set[str] = set()
    for uri in _ARTIFACT_URI.findall(_terminal_text(context.snapshot)):
        try:
            artifact = context.services.artifacts.resolve_uri(uri)
        except Exception:
            continue
        artifact_id = str(getattr(artifact, "artifact_id", "") or uri)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        artifacts.append(artifact)
    return tuple(artifacts)


def _read_json_artifact(artifact: Any, runtime_home: Path) -> dict[str, Any] | None:
    path = Path(str(getattr(artifact, "absolute_path", "")))
    if not (
        bool(getattr(artifact, "ready_to_open", False))
        and bool(getattr(artifact, "exists", False))
        and is_within(path, runtime_home)
        and path.suffix.lower() == ".json"
    ):
        return None
    try:
        if path.stat().st_size > 524_288:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError, UnicodeError, json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _terminal_text(snapshot: Any | None) -> str:
    messages = list(getattr(snapshot, "messages", [])) if snapshot is not None else []
    if not messages:
        return ""
    return str(getattr(messages[-1], "text", "") or "")


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


def _source_unchanged(case: TextTopicDiscoveryCase, context: BenchmarkCaseContext) -> bool:
    state = context.source_state
    if not isinstance(state, AttachedSourceState):
        return False
    try:
        return bool(
            attached_source_unchanged(
                source_path=case.source_path,
                source_state=state,
                services=context.services,
            )
            and source_dataset_ids_for_external_digest(
                snapshot=context.snapshot,
                services=context.services,
                digest=state.external_sha256,
            )
        )
    except Exception:
        return False


def _state_isolated(context: BenchmarkCaseContext, artifacts: tuple[Any | None, ...]) -> bool:
    if not context.settings_unchanged:
        return False
    try:
        datasets_confined = all(
            is_within(Path(str(dataset.source_path)), context.runtime_home)
            for dataset in context.services.datasets.list_datasets()
        )
        artifacts_confined = all(
            artifact is None
            or is_within(
                Path(str(getattr(artifact, "absolute_path", ""))),
                context.runtime_home,
            )
            for artifact in artifacts
        )
        return datasets_confined and artifacts_confined
    except Exception:
        return False


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value.lower()) is not None


def test_ml_text_topic_discovery(agent_harness_benchmark) -> None:
    """Measure public bilingual topic outcomes without prescribing a Tool trace."""

    agent_harness_benchmark.run(TextTopicDiscoveryCase())
