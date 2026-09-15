"""Clean-room paid-live Agent case for grouped bilingual text classification."""

from __future__ import annotations

from hashlib import sha256
import math
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


CASE_ID: Final = "ml.text_grouped_classification_v1"
_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "ml_capabilities"
_TRAIN_PATH = _FIXTURE_ROOT / "learning_module_text_training.csv"
_APPLY_PATH = _FIXTURE_ROOT / "learning_module_text_apply.csv"
_EXPECTED_TRAIN_SIZE = 5_983
_EXPECTED_TRAIN_SHA256 = "3EA66D8A70B07934B0EC3CB07DBC62DEA0DF9336A0ABA1EE700EDF1C6E0DE278"
_EXPECTED_APPLY_SIZE = 447
_EXPECTED_APPLY_SHA256 = "D3DFC9466392ED5045FDE2459A9036AB3A9D1165E310F55E21E7FEAFDABA9DC3"
_EXPECTED_COMBINED_SHA256 = "C1B734A25BDBD39D31809165B469F82461622D47EFB5E7FAE4AFC882AB2D98EA"
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


BUSINESS_PROMPT = (
    "第一份附件是已经分配处理队列的中英文备注，第二份是待分配的新备注。"
    "请据此预测新备注应进入哪个队列，交付预测表和评估报告。account_batch 表示同批业务记录，"
    "同批记录可能很相似，请避免把这种重复当作模型效果。说明效果是否优于简单猜测，以及人工复核建议。"
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

    def build_submission(self, *, thread_id: int, fq_model_key: str) -> SubmitUserTurnInput:
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
        frame = _resolve_prediction_outcome(context)
        report_artifact, report = _resolve_evaluation_report(context)
        completed = canonical_completion(context.snapshot)
        sources_unchanged = _sources_unchanged(self, context)
        semantic_checks = (
            OutcomeCheck(
                "exact_raw_text_predictions",
                frame is not None,
                "exact_raw_text_predictions_observed" if frame is not None else "exact_raw_text_predictions_missing",
            ),
            OutcomeCheck(
                "public_prediction_artifact",
                frame is not None,
                "linked_prediction_artifact_observed"
                if frame is not None
                else "linked_prediction_artifact_missing",
            ),
            OutcomeCheck(
                "public_group_safe_evaluation",
                report is not None,
                "candidate_dummy_and_isolation_facts_observed"
                if report is not None
                else "candidate_dummy_or_isolation_facts_missing",
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
        )
        deterministic_passed = all(check.passed for check in semantic_checks)
        integrity_passed = all(check.passed for check in integrity_checks)
        judge_input = (
            _build_judge_input(report, _terminal_text(context.snapshot)) if deterministic_passed and integrity_passed and report is not None else None
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


def _resolve_prediction_outcome(context: BenchmarkCaseContext) -> pl.DataFrame | None:
    return next((frame for frame in linked_tables(context).values() if _matches_predictions(frame)), None)


def _matches_predictions(frame: pl.DataFrame) -> bool:
    if frame.height != 6 or not _OUTPUT_COLUMNS.issubset(frame.columns):
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


def _resolve_evaluation_report(
    context: BenchmarkCaseContext,
) -> tuple[Any | None, dict[str, Any] | None]:
    for uri, payload in linked_json_reports(context).items():
        if payload is not None and _matches_evaluation_report(payload):
            return uri, payload
    return None, None


def _matches_evaluation_report(payload: dict[str, Any]) -> bool:
    evaluation = payload.get("evaluation")
    baseline = payload.get("baseline_evaluation")
    comparison = payload.get("comparison")
    split = payload.get("split_facts")
    facts = payload.get("text_classification_evaluation")
    if not all(isinstance(value, dict) for value in (evaluation, baseline, comparison, split, facts)):
        return False
    assert isinstance(evaluation, dict)
    assert isinstance(baseline, dict)
    assert isinstance(comparison, dict)
    assert isinstance(split, dict)
    assert isinstance(facts, dict)
    leakage = facts.get("leakage")
    if not isinstance(leakage, dict):
        return False
    assert isinstance(leakage, dict)
    return bool(
        payload.get("evaluation_kind") == "classification"
        and _candidate_metrics_match(evaluation)
        and _baseline_metrics_match(baseline)
        and _comparison_matches(comparison)
        and _split_matches(split)
        and _leakage_matches(leakage)
    )


def _candidate_metrics_match(evaluation: dict[str, Any]) -> bool:
    try:
        return evaluation.get("primary_metric_name") == "f1_weighted" and 0.0 <= float(evaluation.get("primary_metric_value")) <= 1.0
    except (TypeError, ValueError):
        return False


def _baseline_metrics_match(baseline: dict[str, Any]) -> bool:
    try:
        return baseline.get("primary_metric_name") == "f1_weighted" and 0 <= float(baseline.get("primary_metric_value")) <= 1.0
    except (TypeError, ValueError):
        return False


def _comparison_matches(comparison: dict[str, Any]) -> bool:
    try:
        return bool(
            comparison.get("primary_metric_name") == "f1_weighted"
            and comparison.get("direction") == "max"
            and float(comparison.get("candidate_value")) > float(comparison.get("baseline_value"))
        )
    except (TypeError, ValueError):
        return False


def _split_matches(split: dict[str, Any]) -> bool:
    try:
        return bool(
            0 < int(split.get("train_row_count")) < int(split.get("eligible_row_count"))
            and 0 < int(split.get("holdout_row_count")) < int(split.get("eligible_row_count"))
            and split.get("group_overlap_count") == 0
            and split.get("evaluation_scope") == "holdout"
        )
    except (TypeError, ValueError):
        return False


def _leakage_matches(leakage: dict[str, Any]) -> bool:
    return bool(
        leakage.get("business_group_supplied") is True
        and leakage.get("train_business_group_overlap_count") == 0
        and leakage.get("train_template_group_overlap_count") == 0
        and leakage.get("train_connected_group_overlap_count") == 0
    )


def _build_judge_input(report: dict[str, Any], final_text: str) -> JudgeInput:
    evaluation = report["evaluation"]
    baseline = report["baseline_evaluation"]
    comparison = report["comparison"]
    facts = report["text_classification_evaluation"]
    leakage = facts["leakage"]
    split = report["split_facts"]
    return JudgeInput(
        rubric=TEXT_CLASSIFICATION_RUBRIC,
        task_intent=BUSINESS_PROMPT,
        facts=(
            "目标要求直接处理双语原始文本，并交付六行确定性分类结果。",
            "候选与多数类 dummy 必须使用同一 group-safe holdout，且业务组、模板与联合组均零重叠。",
            "离线分类证据不能解释为因果效果，也不授予无人值守的自动决策权限。",
        ),
        artifact_evidence=(
            f"final_answer: {final_text}",
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
                "source_immutability_verified=true"
            ),
        ),
    )


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


def _sources_unchanged(case: TextGroupedClassificationCase, context: BenchmarkCaseContext) -> bool:
    states = _source_states(context)
    if len(states) != 2:
        return False
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


def test_ml_text_grouped_classification(agent_harness_benchmark) -> None:
    """Measure public grouped-classification outcomes without prescribing a Tool trace."""

    agent_harness_benchmark.run(TextGroupedClassificationCase())
