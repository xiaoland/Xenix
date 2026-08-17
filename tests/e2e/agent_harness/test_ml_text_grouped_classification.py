"""Clean-room paid-live Agent case for grouped bilingual text classification."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
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


CASE_ID: Final = "ml.text_grouped_classification_v1"
_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "ml_capabilities"
_TRAIN_PATH = _FIXTURE_ROOT / "learning_module_text_training.csv"
_APPLY_PATH = _FIXTURE_ROOT / "learning_module_text_apply.csv"
_EXPECTED_TRAIN_SIZE = 5_983
_EXPECTED_TRAIN_SHA256 = "3EA66D8A70B07934B0EC3CB07DBC62DEA0DF9336A0ABA1EE700EDF1C6E0DE278"
_EXPECTED_APPLY_SIZE = 447
_EXPECTED_APPLY_SHA256 = "D3DFC9466392ED5045FDE2459A9036AB3A9D1165E310F55E21E7FEAFDABA9DC3"
_EXPECTED_COMBINED_SHA256 = "C1B734A25BDBD39D31809165B469F82461622D47EFB5E7FAE4AFC882AB2D98EA"
_EXPECTED_RESOURCE_IDENTITY_DIGEST = "4a90373f81203fe0c091d125eb86e016af556441d78aa74119984ebd961e9d75"
_EXPECTED_SPECIFICATION_DIGEST = "fbdd0c8df797beba6435abfec9701238045d171c472710342e203e7bf0d05ea4"
_EXPECTED_PREPARED_TEXT_DIGEST = "3cc51524721ea6a44d202ec74c4b0622ecd5285fcd9af1c915f8910e78ab6d7e"
_EXPECTED_GROUP_ASSIGNMENT_DIGEST = "69a33dc01ce4c3bbf74e5f08c902eb8b18a786eb36f35f2502088d301c041b62"
_EXPECTED_EVALUATION_PREDICTION_DIGEST = "aaee071d8f88f50b9cf8f021a53514efedd0c8ccbca31d10cb75d9f0a4ccf096"
_EXPECTED_PREDICTIONS = {
    "ASK-901": "access_help",
    "ASK-902": "access_help",
    "ASK-903": "billing_review",
    "ASK-904": "billing_review",
    "ASK-905": "credential_request",
    "ASK-906": "credential_request",
}
_EXPECTED_APPLY_MESSAGES = {
    "ASK-901": "登录入口拒绝授权，access portal keeps denying entry.",
    "ASK-902": "无法进入工作台，login access code is rejected.",
    "ASK-903": "发票金额重复，invoice shows a duplicate seat charge.",
    "ASK-904": "账单税额需要复核，billing invoice total looks wrong.",
    "ASK-905": "结业证书无法下载，certificate credential link is absent.",
    "ASK-906": "完成记录已有但凭证未生成，credential certificate is missing.",
}
_OUTPUT_COLUMNS = {"request_ref", "message", "prediction", "prediction_score"}
_ARTIFACT_URI = re.compile(r"artifact://[A-Za-z0-9]+(?:\?[^)\s>]+)?")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_PATH = re.compile(r"(?i)[A-Z]:[\\/]")


@dataclass(frozen=True)
class _TextApiContract:
    model_key: str
    text_role: str
    target_role: str
    group_role: str
    evaluation_facts_key: str
    apply_facts_key: str
    parameter_names: frozenset[str]


_CANDIDATE_API = _TextApiContract(
    model_key="text.classification.multilingual_logistic_regression_tfidf",
    text_role="text",
    target_role="target",
    group_role="group",
    evaluation_facts_key="text_classification_evaluation",
    apply_facts_key="text_classification_apply_facts",
    parameter_names=frozenset(
        {
            "preparation_profile",
            "phrase_mode",
            "max_features",
            "minimum_document_frequency",
            "class_weight",
            "custom_dictionary_dataset_ids",
            "stopword_dataset_ids",
        }
    ),
)
_FROZEN_API: Final[_TextApiContract] = _CANDIDATE_API

BUSINESS_PROMPT = (
    "附件一是双语备注训练表，附件二是待分类原始备注。先画像并用 model.metadata 核对 "
    "text.classification.multilingual_logistic_regression_tfidf 的角色和 7 项参数。将 message "
    "绑定 text、queue 绑定 target、account_batch 绑定可选 group；使用 unigram、max_features=5000、"
    "minimum_document_frequency=1、class_weight=balanced，两个 resource Dataset ID 列表均为空。"
    "训练候选，取得同一 group-safe holdout 上与 dummy baseline 比较的 Evaluate 报告，再用保留的"
    "全量 analyzer 处理附件二。交付公共 predictions Dataset/Artifact 和 Evaluate report Artifact "
    "链接。最终列明候选与 dummy 的 F1、业务组与模板零重叠及全部 7 个参数名；说明这是 raw apply，"
    "且离线证据非因果、自动决策前仍需人工复核。"
)

TEXT_CLASSIFICATION_RUBRIC = JudgeRubric(
    rubric_id="ml.text_grouped_classification_v1.business_outcome.v1",
    score_dimensions=(
        "prediction_delivery",
        "evaluation_grounding",
        "leakage_explanation",
        "decision_limits",
    ),
    allowed_reason_codes=(
        "complete_grounded_outcome",
        "prediction_delivery_incomplete",
        "candidate_baseline_comparison_unsupported",
        "group_template_isolation_unclear",
        "offline_authority_boundary_missing",
    ),
)

pytestmark = pytest.mark.agent_harness_live


class TextGroupedClassificationCase:
    """Measure final public classification outcomes without prescribing a Tool trace."""

    case_id = CASE_ID

    def __init__(
        self,
        train_path: Path = _TRAIN_PATH,
        apply_path: Path = _APPLY_PATH,
    ) -> None:
        self.train_path = train_path
        self.apply_path = apply_path

    def validate_input(self) -> str:
        return _validate_fixture_set(self.train_path, self.apply_path)

    def build_submission(self, *, thread_id: str, fq_model_key: str) -> SubmitUserTurnInput:
        return SubmitUserTurnInput(
            thread_id=thread_id,
            text=BUSINESS_PROMPT,
            source_attachments=[
                SourceAttachmentInput(file_path=str(self.train_path.resolve())),
                SourceAttachmentInput(file_path=str(self.apply_path.resolve())),
            ],
            fq_model_key=fq_model_key,
        )

    def capture_source_state(
        self,
        *,
        snapshot: Any,
        services: BenchmarkCaseServices,
    ) -> tuple[AttachedSourceState, AttachedSourceState]:
        return (
            capture_attached_source_state(
                source_path=self.train_path,
                snapshot=snapshot,
                services=services,
            ),
            capture_attached_source_state(
                source_path=self.apply_path,
                snapshot=snapshot,
                services=services,
            ),
        )

    def assess(self, *, context: BenchmarkCaseContext) -> BenchmarkCaseAssessment:
        dataset, frame = _resolve_prediction_outcome(context)
        prediction_artifact = _resolve_prediction_artifact(context, dataset)
        report_artifact, report = _resolve_evaluation_report(context)
        grounding_gaps = _final_answer_grounding_gaps(
            _terminal_text(context.snapshot),
            report,
        )
        completed = canonical_completion(context.snapshot)
        sources_unchanged = _sources_unchanged(self, context)
        isolated = _state_isolated(context, (prediction_artifact, report_artifact))
        semantic_checks = (
            OutcomeCheck(
                "exact_raw_text_predictions",
                frame is not None,
                "exact_raw_text_predictions_observed" if frame is not None else "exact_raw_text_predictions_missing",
            ),
            OutcomeCheck(
                "public_prediction_artifact",
                prediction_artifact is not None,
                "linked_prediction_artifact_observed"
                if prediction_artifact is not None
                else "linked_prediction_artifact_missing",
            ),
            OutcomeCheck(
                "public_group_safe_evaluation",
                report is not None,
                "candidate_dummy_and_isolation_facts_observed"
                if report is not None
                else "candidate_dummy_or_isolation_facts_missing",
            ),
            OutcomeCheck(
                "grounded_final_answer",
                not grounding_gaps,
                "classification_evidence_and_limits_grounded"
                if not grounding_gaps
                else "classification_explanation_not_grounded:" + ",".join(grounding_gaps),
            ),
        )
        integrity_checks = (
            OutcomeCheck(
                "canonical_completion",
                completed,
                "canonical_completion_observed" if completed else "canonical_completion_missing",
            ),
            OutcomeCheck(
                "sources_unchanged",
                sources_unchanged,
                "sources_unchanged" if sources_unchanged else "source_changed_or_unverifiable",
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
        return BenchmarkCaseAssessment(
            semantic_checks=semantic_checks,
            integrity_checks=integrity_checks,
            judge_input=judge_input,
            judge_required=True,
            terminal_shape=(frame.height, frame.width) if frame is not None else None,
        )


def _validate_fixture_set(train_path: Path, apply_path: Path) -> str:
    expectations = (
        (train_path, _EXPECTED_TRAIN_SIZE, _EXPECTED_TRAIN_SHA256),
        (apply_path, _EXPECTED_APPLY_SIZE, _EXPECTED_APPLY_SHA256),
    )
    observed: list[str] = []
    for path, expected_size, expected_digest in expectations:
        if not path.is_file():
            raise BenchmarkInputError("missing_fixture")
        if path.stat().st_size != expected_size:
            raise BenchmarkInputError("fixture_size_mismatch")
        digest = sha256_file(path)
        if digest != expected_digest:
            raise BenchmarkInputError("fixture_hash_mismatch")
        observed.append(digest)
    combined = sha256(":".join(observed).encode("utf-8")).hexdigest().upper()
    if combined != _EXPECTED_COMBINED_SHA256:
        raise BenchmarkInputError("fixture_set_hash_mismatch")
    return combined


def _resolve_prediction_outcome(
    context: BenchmarkCaseContext,
) -> tuple[Any | None, pl.DataFrame | None]:
    apply_source_ids = _source_ids_for_digest(context, _EXPECTED_APPLY_SHA256)
    datasets = list(context.services.datasets.list_datasets())
    by_id = {str(dataset.id): dataset for dataset in datasets}
    for dataset in datasets:
        if not _is_run_descendant(
            dataset,
            by_id,
            apply_source_ids,
            context.run_dataset_ids,
        ):
            continue
        try:
            frame = load_tabular_frame(Path(dataset.source_path), dataset.source_format)
        except Exception:
            continue
        if _matches_predictions(frame):
            return dataset, frame
    return None, None


def _matches_predictions(frame: pl.DataFrame) -> bool:
    if frame.height != 6 or set(frame.columns) != _OUTPUT_COLUMNS:
        return False
    observed: dict[str, tuple[str, str, float]] = {}
    try:
        for row in frame.to_dicts():
            request_ref = str(row["request_ref"]).strip()
            message = str(row["message"])
            prediction = str(row["prediction"]).strip()
            score = float(row["prediction_score"])
            if request_ref in observed or not math.isfinite(score) or not 0.0 <= score <= 1.0:
                return False
            observed[request_ref] = (message, prediction, score)
    except KeyError, TypeError, ValueError:
        return False
    return set(observed) == set(_EXPECTED_PREDICTIONS) and all(
        observed[request_ref][0] == _EXPECTED_APPLY_MESSAGES[request_ref]
        and observed[request_ref][1] == expected_prediction
        for request_ref, expected_prediction in _EXPECTED_PREDICTIONS.items()
    )


def _resolve_prediction_artifact(context: BenchmarkCaseContext, dataset: Any | None) -> Any | None:
    if dataset is None:
        return None
    for artifact in _linked_artifacts(context):
        path = Path(str(getattr(artifact, "absolute_path", "")))
        metadata = getattr(artifact, "metadata_payload", {})
        if (
            enum_value(getattr(artifact, "kind", None)) == "prediction"
            and bool(getattr(artifact, "ready_to_open", False))
            and bool(getattr(artifact, "exists", False))
            and is_within(path, context.runtime_home)
            and isinstance(metadata, dict)
            and metadata.get("result_dataset_id") == dataset.id
        ):
            return artifact
    return None


def _resolve_evaluation_report(
    context: BenchmarkCaseContext,
) -> tuple[Any | None, dict[str, Any] | None]:
    for artifact in _linked_artifacts(context):
        if enum_value(getattr(artifact, "kind", None)) != "report":
            continue
        payload = _read_json_artifact(artifact, context.runtime_home)
        if payload is not None and _matches_evaluation_report(payload, api=_FROZEN_API):
            return artifact, payload
    return None, None


def _matches_evaluation_report(payload: dict[str, Any], *, api: _TextApiContract) -> bool:
    evaluation = payload.get("evaluation")
    baseline = payload.get("baseline_evaluation")
    comparison = payload.get("comparison")
    split = payload.get("split_facts")
    facts = payload.get(api.evaluation_facts_key)
    if not all(isinstance(value, dict) for value in (evaluation, baseline, comparison, split, facts)):
        return False
    assert isinstance(evaluation, dict)
    assert isinstance(baseline, dict)
    assert isinstance(comparison, dict)
    assert isinstance(split, dict)
    assert isinstance(facts, dict)
    specification = facts.get("specification")
    preparation = facts.get("preparation")
    leakage = facts.get("leakage")
    vectorization = facts.get("vectorization")
    if not all(isinstance(value, dict) for value in (specification, preparation, leakage, vectorization)):
        return False
    assert isinstance(specification, dict)
    assert isinstance(preparation, dict)
    assert isinstance(leakage, dict)
    assert isinstance(vectorization, dict)
    return bool(
        payload.get("model_key") == api.model_key
        and payload.get("evaluation_kind") == "classification"
        and _candidate_metrics_match(evaluation)
        and _baseline_metrics_match(baseline)
        and _comparison_matches(comparison)
        and _split_matches(split)
        and _specification_matches(specification)
        and _preparation_matches(preparation, specification)
        and _leakage_matches(leakage)
        and _vectorization_matches(vectorization)
        and facts.get("prediction_digest") == _EXPECTED_EVALUATION_PREDICTION_DIGEST
        and _is_sha256(_prediction_digest(evaluation))
        and _facts_are_bounded(facts)
        and _report_is_privacy_safe(payload)
    )


def _candidate_metrics_match(evaluation: dict[str, Any]) -> bool:
    metrics = evaluation.get("metrics")
    if not isinstance(metrics, dict):
        return False
    try:
        return bool(
            evaluation.get("primary_metric_name") == "f1_weighted"
            and math.isclose(float(evaluation.get("primary_metric_value")), 1.0, abs_tol=1e-12)
            and all(
                math.isclose(float(metrics.get(name)), 1.0, abs_tol=1e-12)
                for name in ("accuracy", "balanced_accuracy", "f1_macro", "f1_weighted")
            )
        )
    except TypeError, ValueError:
        return False


def _baseline_metrics_match(baseline: dict[str, Any]) -> bool:
    metrics = baseline.get("metrics")
    if not isinstance(metrics, dict):
        return False
    try:
        return bool(
            baseline.get("primary_metric_name") == "f1_weighted"
            and math.isclose(
                float(baseline.get("primary_metric_value")),
                1.0 / 6.0,
                abs_tol=1e-12,
            )
            and math.isclose(float(metrics.get("accuracy")), 1.0 / 3.0, abs_tol=1e-12)
            and math.isclose(float(metrics.get("f1_weighted")), 1.0 / 6.0, abs_tol=1e-12)
        )
    except TypeError, ValueError:
        return False


def _comparison_matches(comparison: dict[str, Any]) -> bool:
    try:
        return bool(
            comparison.get("primary_metric_name") == "f1_weighted"
            and comparison.get("direction") == "max"
            and comparison.get("verdict") == "candidate_better"
            and math.isclose(float(comparison.get("candidate_value")), 1.0, abs_tol=1e-12)
            and math.isclose(float(comparison.get("baseline_value")), 1.0 / 6.0, abs_tol=1e-12)
        )
    except TypeError, ValueError:
        return False


def _split_matches(split: dict[str, Any]) -> bool:
    return bool(
        split.get("policy_key") == "classification.group_hash_holdout.v1"
        and split.get("requested_strategy") == "group_hash_holdout.v1"
        and split.get("realized_strategy") == "group_hash_holdout.v1"
        and split.get("eligible_row_count") == 60
        and split.get("train_row_count") == 48
        and split.get("holdout_row_count") == 12
        and split.get("eligible_group_count") == 10
        and split.get("train_group_count") == 8
        and split.get("holdout_group_count") == 2
        and split.get("group_overlap_count") == 0
        and split.get("random_state") == 42
        and split.get("evaluation_scope") == "holdout"
        and _is_sha256(split.get("source_dataset_snapshot_digest"))
        and _is_sha256(split.get("train_membership_digest"))
        and _is_sha256(split.get("holdout_membership_digest"))
    )


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
        and preparation.get("source_row_count") == 60
        and preparation.get("eligible_row_count") == 60
        and preparation.get("missing_text_row_count") == 0
        and preparation.get("non_empty_text_row_count") == 60
        and preparation.get("empty_after_preparation_row_count") == 0
        and preparation.get("mixed_script_text_row_count") == 60
        and preparation.get("token_count") == 450
        and preparation.get("custom_dictionary_term_count") == 0
        and preparation.get("stopword_term_count") == 49
        and preparation.get("custom_term_match_count") == 0
        and preparation.get("collapsed_exact_duplicate_row_count") == 30
        and preparation.get("collapsed_template_duplicate_row_count") == 30
        and preparation.get("prepared_text_digest") == _EXPECTED_PREPARED_TEXT_DIGEST
    )


def _leakage_matches(leakage: dict[str, Any]) -> bool:
    return bool(
        leakage.get("group_policy_key") == "business_template_connected_union.v1"
        and leakage.get("template_policy_key") == "masked_token_jaccard.v1"
        and math.isclose(float(leakage.get("template_similarity_threshold")), 0.8, abs_tol=1e-12)
        and leakage.get("business_group_supplied") is True
        and leakage.get("eligible_row_count") == 60
        and leakage.get("business_group_count") == 10
        and leakage.get("template_group_count") == 30
        and leakage.get("connected_group_count") == 10
        and leakage.get("near_duplicate_edge_count") == 0
        and leakage.get("train_business_group_overlap_count") == 0
        and leakage.get("train_template_group_overlap_count") == 0
        and leakage.get("train_connected_group_overlap_count") == 0
        and leakage.get("group_assignment_digest") == _EXPECTED_GROUP_ASSIGNMENT_DIGEST
    )


def _vectorization_matches(vectorization: dict[str, Any]) -> bool:
    transformed = vectorization.get("transformed_feature_count")
    return bool(
        vectorization.get("fit_row_count") == 48
        and isinstance(transformed, int)
        and not isinstance(transformed, bool)
        and transformed > 0
        and vectorization.get("inspected_row_count") == 12
        and vectorization.get("empty_after_preparation_row_count") == 0
        and vectorization.get("out_of_vocabulary_row_count") == 0
        and _is_sha256(vectorization.get("vocabulary_digest"))
    )


def _prediction_digest(evaluation: dict[str, Any]) -> str | None:
    details = evaluation.get("details")
    return details.get("prediction_digest") if isinstance(details, dict) else None


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value.lower()) is not None


def _facts_are_bounded(facts: dict[str, Any]) -> bool:
    specification = facts.get("specification")
    preparation = facts.get("preparation")
    leakage = facts.get("leakage")
    vectorization = facts.get("vectorization")
    if not all(isinstance(value, dict) for value in (specification, preparation, leakage, vectorization)):
        return False
    assert isinstance(specification, dict)
    assert isinstance(preparation, dict)
    assert isinstance(leakage, dict)
    assert isinstance(vectorization, dict)
    return bool(
        set(facts) == {"specification", "preparation", "leakage", "vectorization", "prediction_digest"}
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
        and set(leakage)
        == {
            "group_policy_key",
            "template_policy_key",
            "template_similarity_threshold",
            "business_group_supplied",
            "eligible_row_count",
            "business_group_count",
            "template_group_count",
            "connected_group_count",
            "near_duplicate_edge_count",
            "train_business_group_overlap_count",
            "train_template_group_overlap_count",
            "train_connected_group_overlap_count",
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
        and len(json.dumps(facts, ensure_ascii=False, sort_keys=True)) <= 8_192
    )


def _report_is_privacy_safe(payload: dict[str, Any]) -> bool:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    upper = serialized.upper()
    try:
        training_messages = {
            str(value) for value in pl.read_csv(_TRAIN_PATH, columns=["message"]).get_column("message").to_list()
        }
    except Exception:
        return False
    private_values = {
        *training_messages,
        *_EXPECTED_APPLY_MESSAGES.values(),
        *_EXPECTED_PREDICTIONS,
        _TRAIN_PATH.name,
        _APPLY_PATH.name,
    }
    prohibited_keys = (
        '"raw_text":',
        '"raw_texts":',
        '"template_values":',
        '"vocabulary":',
        '"feature_names":',
    )
    return not (
        any(value in serialized for value in private_values)
        or "NOTE-" in upper
        or "ASK-" in upper
        or "CAMPUS-" in upper
        or _WINDOWS_PATH.search(serialized) is not None
        or any(key in serialized for key in prohibited_keys)
    )


def _final_answer_grounding_gaps(
    text: str,
    report: dict[str, Any] | None,
) -> tuple[str, ...]:
    if not text:
        return ("missing_final_answer",)
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).lower())
    raw_apply = any(
        marker in normalized
        for marker in ("原始文本", "原始备注", "原文", "rawtext", "raw-text")
    )
    candidate = any(marker in normalized for marker in ("候选", "分类器", "模型", "candidate"))
    dummy = any(marker in normalized for marker in ("dummy", "多数类", "简单基线"))
    comparison = any(marker in normalized for marker in ("优于", "高于", "提升", "better"))
    metric = "f1" in normalized
    metric_values = _candidate_and_baseline_values_grounded(normalized, report)
    parameter_schema = all(name in normalized for name in _FROZEN_API.parameter_names)
    group = any(marker in normalized for marker in ("业务组", "businessgroup", "group"))
    template = any(marker in normalized for marker in ("模板", "template"))
    zero_overlap = any(marker in normalized for marker in ("零重叠", "无重叠", "0重叠", "zerooverlap"))
    offline = "离线" in normalized or "offline" in normalized
    authority_limit = any(
        marker in normalized for marker in ("不能证明因果", "非因果", "人工复核", "不能自动决策", "线上验证")
    )
    checks = (
        ("evaluation_artifact", report is not None),
        ("raw_text_apply", raw_apply),
        ("candidate_dummy_comparison", candidate and dummy and (comparison or metric_values)),
        ("f1_metric", metric),
        ("seven_parameter_schema", parameter_schema),
        ("group_template_isolation", group and template and zero_overlap),
        ("offline_authority_boundary", offline and authority_limit),
        ("dataset_and_artifact_links", len(_ARTIFACT_URI.findall(text)) >= 2),
    )
    return tuple(name for name, passed in checks if not passed)


def _candidate_and_baseline_values_grounded(
    normalized_text: str,
    report: dict[str, Any] | None,
) -> bool:
    if report is None:
        return False
    evaluation = report.get("evaluation")
    baseline = report.get("baseline_evaluation")
    if not isinstance(evaluation, dict) or not isinstance(baseline, dict):
        return False
    try:
        candidate_value = float(evaluation["primary_metric_value"])
        baseline_value = float(baseline["primary_metric_value"])
    except (KeyError, TypeError, ValueError):
        return False
    observed: list[float] = []
    for raw_value, percent in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(%)?", normalized_text):
        value = float(raw_value)
        observed.append(value / 100.0 if percent else value)
    return any(math.isclose(value, candidate_value, abs_tol=5e-4) for value in observed) and any(
        math.isclose(value, baseline_value, abs_tol=5e-4) for value in observed
    )


def _build_judge_input(report: dict[str, Any]) -> JudgeInput:
    evaluation = report["evaluation"]
    baseline = report["baseline_evaluation"]
    comparison = report["comparison"]
    facts = report[_CANDIDATE_API.evaluation_facts_key]
    leakage = facts["leakage"]
    split = report["split_facts"]
    return JudgeInput(
        rubric=TEXT_CLASSIFICATION_RUBRIC,
        task_intent=BUSINESS_PROMPT,
        facts=(
            "目标要求直接处理双语原始文本，并交付六行确定性分类结果。",
            "候选与多数类 dummy 必须使用同一 group-safe holdout，且业务组、模板与联合组均零重叠。",
            "离线分类证据不能解释为因果效果，也不授予无人值守的自动决策权限。",
            "最终公开说明必须列明模型 metadata 的七项参数 schema，而不依赖 Tool trace。",
        ),
        artifact_evidence=(
            "public_predictions: row_count=6; exact_private_oracle=true; raw_text_apply=true",
            (
                "public_evaluation: metric=f1_weighted; "
                f"candidate={float(evaluation['primary_metric_value']):.6f}; "
                f"dummy={float(baseline['primary_metric_value']):.6f}; "
                f"verdict={comparison['verdict']}"
            ),
            (
                "public_isolation: "
                f"business_overlap={int(leakage['train_business_group_overlap_count'])}; "
                f"template_overlap={int(leakage['train_template_group_overlap_count'])}; "
                f"connected_overlap={int(leakage['train_connected_group_overlap_count'])}; "
                f"holdout_rows={int(split['holdout_row_count'])}"
            ),
            (
                "public_identity: predictions_dataset_linked=true; evaluation_artifact_linked=true; "
                "apply_lineage_verified=true; source_immutability_verified=true"
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


def _source_states(context: BenchmarkCaseContext) -> tuple[AttachedSourceState, ...]:
    state = context.source_state
    if not isinstance(state, tuple):
        return ()
    return tuple(item for item in state if isinstance(item, AttachedSourceState))


def _source_ids_for_digest(context: BenchmarkCaseContext, digest: str) -> set[str]:
    return source_dataset_ids_for_external_digest(
        snapshot=context.snapshot,
        services=context.services,
        digest=digest,
    )


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


def _sources_unchanged(case: TextGroupedClassificationCase, context: BenchmarkCaseContext) -> bool:
    states = _source_states(context)
    if len(states) != 2:
        return False
    try:
        return all(
            attached_source_unchanged(
                source_path=path,
                source_state=state,
                services=context.services,
            )
            for path, state in zip(
                (case.train_path, case.apply_path),
                states,
                strict=True,
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
            artifact is None or is_within(Path(str(getattr(artifact, "absolute_path", ""))), context.runtime_home)
            for artifact in artifacts
        )
        return datasets_confined and artifacts_confined
    except Exception:
        return False


def test_ml_text_grouped_classification(agent_harness_benchmark) -> None:
    """Measure public grouped-classification outcomes without prescribing a Tool trace."""

    agent_harness_benchmark.run(TextGroupedClassificationCase())
