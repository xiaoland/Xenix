"""Clean-room paid-live Agent case for trustworthy cluster selection."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Final

import polars as pl
import pytest

from xenix.services.agent import SourceAttachmentInput, SubmitUserTurnInput
from xenix.services.storage.models import DatasetSourceFormat
from xenix.services.tabular import load_tabular_frame

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


CASE_ID: Final = "ml.cluster_selection_v1"
_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "ml_capabilities" / "cluster_selection_accounts.csv"
_EXPECTED_SIZE = 388
_EXPECTED_SHA256 = "BC692350CF2C0FB23905EEC264A48F6D361A09030DECBB5C1BAC2B6627B1D2EA"
_FEATURE_COLUMNS = ("monthly_orders", "return_rate_pct", "service_minutes")
_LOYAL_ACCOUNTS = frozenset({"ACC-001", "ACC-002", "ACC-003", "ACC-004", "ACC-005", "ACC-006"})
_GROWING_ACCOUNTS = frozenset({"ACC-007", "ACC-008", "ACC-009", "ACC-010", "ACC-011", "ACC-012"})
_AT_RISK_ACCOUNTS = frozenset({"ACC-013", "ACC-014", "ACC-015", "ACC-016", "ACC-017", "ACC-018"})
_EXPECTED_PARTITION = (_LOYAL_ACCOUNTS, _GROWING_ACCOUNTS, _AT_RISK_ACCOUNTS)

BUSINESS_PROMPT = (
    "我们想按下单、退货和服务需求给这些客户分群，方便制定不同的运营方案。"
    "请比较分成 2 到 4 群的效果，推荐合适的方案，并说明各群特点、选择依据和使用局限。"
    "account_id 是客户编号。请交付保留原始记录和群组标签的数据集，以及可打开的评估报告。"
)

CLUSTER_SELECTION_RUBRIC = JudgeRubric(
    rubric_id="ml.cluster_selection.business_explanation.v1",
    score_dimensions=(
        "business_intent_alignment",
        "public_evidence_grounding",
        "segment_interpretability",
        "limitations_and_next_validation",
    ),
    allowed_reason_codes=(
        "missing_public_outcome",
        "ungrounded_model_selection",
        "segment_profile_not_actionable",
        "internal_metric_overclaim",
        "clear_grounded_explanation",
    ),
)

pytestmark = pytest.mark.agent_harness_live


class ClusterSelectionCase:
    """Measure public assignments, report facts, and business interpretation."""

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
        frame = _resolve_assignment_outcome(context, self.source_path)
        report_artifact, report_facts = _resolve_cluster_report(context, frame)
        final_text = _terminal_text(context.snapshot)
        completed = canonical_completion(context.snapshot)
        source_unchanged = _source_unchanged(self.source_path, context)

        semantic_checks = (
            OutcomeCheck(
                "exact_selected_assignment_dataset",
                frame is not None,
                "permutation_invariant_k3_assignment_observed"
                if frame is not None
                else "qualified_k3_assignment_missing",
            ),
            OutcomeCheck(
                "public_trustworthiness_report",
                report_facts is not None,
                "linked_recomputable_cluster_report_observed"
                if report_facts is not None
                else "linked_recomputable_cluster_report_missing",
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
        deterministic_passed = all(check.passed for check in semantic_checks)
        integrity_passed = all(check.passed for check in integrity_checks)
        judge_input = (
            _build_judge_input(report_facts, final_text, frame, _comparison_evidence(context, frame))
            if deterministic_passed and integrity_passed and report_facts is not None
            else None
        )
        return BenchmarkCaseAssessment(
            semantic_checks=semantic_checks,
            integrity_checks=integrity_checks,
            judge_input=judge_input,
            judge_required=True,
            terminal_shape=(frame.height, frame.width) if frame is not None else None,
        )


def _resolve_assignment_outcome(context: BenchmarkCaseContext, source_path: Path) -> pl.DataFrame | None:
    expected_source = load_tabular_frame(source_path, DatasetSourceFormat.CSV)
    return next((frame for frame in linked_tables(context).values() if _matches_assignment(frame, expected_source)), None)


def _matches_assignment(frame: pl.DataFrame, expected_source: pl.DataFrame) -> bool:
    required = {*expected_source.columns, "cluster_id"}
    if frame.height != 18 or not required.issubset(frame.columns):
        return False
    try:
        source_projection = frame.select(expected_source.columns).sort("account_id")
        if not source_projection.equals(expected_source.sort("account_id")):
            return False
        memberships: dict[str, set[str]] = {}
        for row in frame.select("account_id", "cluster_id").to_dicts():
            account_id = str(row["account_id"]).strip()
            cluster_id = str(row["cluster_id"]).strip()
            if not account_id or not cluster_id:
                return False
            memberships.setdefault(cluster_id, set()).add(account_id)
    except KeyError, TypeError, ValueError:
        return False
    observed = {frozenset(accounts) for accounts in memberships.values()}
    return observed == set(_EXPECTED_PARTITION)


def _resolve_cluster_report(
    context: BenchmarkCaseContext,
    frame: pl.DataFrame | None,
) -> tuple[Any | None, dict[str, Any] | None]:
    if frame is None:
        return None, None
    for uri, payload in linked_json_reports(context).items():
        facts = _cluster_facts(payload)
        if facts is not None and _matches_cluster_report(facts):
            return uri, facts
    return None, None


def _cluster_facts(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload.get("quality"), dict):
        return payload
    nested = payload.get("clustering_evaluation")
    return nested if isinstance(nested, dict) else None


def _matches_cluster_report(facts: dict[str, Any]) -> bool:
    quality = facts.get("quality")
    stability = facts.get("stability")
    baseline = facts.get("null_baseline")
    sizes = facts.get("sizes")
    profiles = facts.get("profiles")
    limitations = facts.get("limitations")
    if not all(
        isinstance(value, expected_type)
        for value, expected_type in (
            (quality, dict),
            (stability, dict),
            (baseline, dict),
            (sizes, list),
            (profiles, list),
            (limitations, list),
        )
    ):
        return False
    assert isinstance(quality, dict)
    assert isinstance(stability, dict)
    assert isinstance(baseline, dict)
    assert isinstance(sizes, list)
    assert isinstance(profiles, list)
    assert isinstance(limitations, list)
    if not (
        quality.get("cluster_count") == 3
        and quality.get("evaluated_row_count") == 18
        and quality.get("noise_row_count") == 0
        and _finite_at_least(quality.get("silhouette"), 0.75)
        and int(stability.get("run_count", 0)) > 1
        and _finite_at_least(stability.get("mean_adjusted_rand_index"), 0.9)
        and int(baseline.get("run_count", 0)) > 0
        and _finite_at_least(baseline.get("candidate_margin"), 0.1)
        and sorted(item.get("row_count") for item in sizes if isinstance(item, dict)) == [6, 6, 6]
        and bool(limitations)
    ):
        return False

    # Report profiles describe the model input coordinate system, which may
    # contain standardized or transformed features. Business interpretation is
    # checked against the original columns in the delivered assignment table.
    return True


def _finite_at_least(value: Any, minimum: float) -> bool:
    try:
        number = float(value)
    except TypeError, ValueError:
        return False
    return math.isfinite(number) and number >= minimum


def _comparison_evidence(context: BenchmarkCaseContext, assignments: pl.DataFrame) -> tuple[str, ...]:
    """Include delivered comparison tables, rather than only the selected report."""
    accounts = set(assignments.get_column("account_id").to_list())
    evidence = []
    for uri, table in linked_tables(context).items():
        if any(accounts.intersection(table.get_column(column).cast(pl.String).to_list()) for column in table.columns):
            continue
        evidence.append(json.dumps({"uri": uri, "public_comparison_table": table.to_dicts()}, ensure_ascii=False, default=str))
    return tuple(evidence)


def _build_judge_input(
    report: dict[str, Any], final_text: str, frame: pl.DataFrame, comparisons: tuple[str, ...],
) -> JudgeInput:
    quality = report["quality"]
    stability = report["stability"]
    baseline = report["null_baseline"]
    profiles = frame.group_by("cluster_id").agg(
        pl.len().alias("rows"),
        *[expression for column in _FEATURE_COLUMNS for expression in (
            pl.col(column).mean().alias(f"{column}_mean"),
            pl.col(column).median().alias(f"{column}_median"),
            pl.col(column).min().alias(f"{column}_min"),
            pl.col(column).max().alias(f"{column}_max"),
        )],
    )
    evidence = (
        "public_assignment: row_count=18; cluster_sizes=6/6/6; source_features_unchanged=true",
        (
            "public_report: cluster_count=3; "
            f"silhouette={float(quality['silhouette']):.6f}; "
            f"stability_mean_ari={float(stability['mean_adjusted_rand_index']):.6f}; "
            f"null_margin={float(baseline['candidate_margin']):.6f}"
        ),
        "public_original_scale_profiles: " + json.dumps(profiles.to_dicts(), ensure_ascii=False),
        "public_model_input_profiles: " + json.dumps(report["profiles"], ensure_ascii=False),
        *comparisons,
        f"final_answer: {final_text}",
    )
    return JudgeInput(
        rubric=CLUSTER_SELECTION_RUBRIC,
        task_intent=BUSINESS_PROMPT,
        facts=(
            "业务要求比较 2 至 4 个群组；当前交付的三个群组符合私有成员划分真值。",
            "三个群各 6 个账户；业务画像按交付表的原始列重算，模型报告可以使用标准化后的特征尺度。不要把不同尺度或均值/中位数混为一谈。",
            "轮廓、稳定性和空基线都是内部证据，不能证明外部有效性或因果解释。",
        ),
        artifact_evidence=evidence,
    )


def _terminal_text(snapshot: Any | None) -> str:
    messages = list(getattr(snapshot, "messages", [])) if snapshot is not None else []
    if not messages:
        return ""
    return str(getattr(messages[-1], "text", "") or "")


def _source_unchanged(source_path: Path, context: BenchmarkCaseContext) -> bool:
    state = context.source_state
    if not isinstance(state, AttachedSourceState) or not state.source_dataset_ids:
        return False
    return attached_source_unchanged(
        source_path=source_path,
        source_state=state,
        services=context.services,
    )


def test_ml_cluster_selection(agent_harness_benchmark) -> None:
    """Measure the selected public outcome without prescribing a Tool trace."""

    agent_harness_benchmark.run(ClusterSelectionCase())
