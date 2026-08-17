"""Clean-room paid-live Agent case for personalized recommendation ranking."""

from __future__ import annotations

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


CASE_ID: Final = "ml.recommendation_ranking_v1"
_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "ml_capabilities"
_RATINGS_PATH = _FIXTURE_ROOT / "learning_module_explicit_ratings.csv"
_TARGETS_PATH = _FIXTURE_ROOT / "learning_module_target_users.csv"
_EXPECTED_RATINGS_SIZE = 1_883
_EXPECTED_RATINGS_SHA256 = "4C5B6CA95C797A02C0D492C63119B9EBBF1EE95EB5626E883979F192AAAA28D3"
_EXPECTED_TARGETS_SIZE = 35
_EXPECTED_TARGETS_SHA256 = "D848D5099F38A35EB7F6415BD757930AF4A3BCD93CF34C6DEABEFDF8F74028B1"
_EXPECTED_COMBINED_SHA256 = "65E48CA44FEEBDDD209BA1AFC702A0D2CB5CEA669B5946780F469BB48B860C53"
_KNOWN_USER = "LEARNER-101"
_COLD_USER = "LEARNER-COLD"
_KNOWN_SEEN_ITEMS = frozenset(
    {
        "MODULE-ALPHA",
        "MODULE-BETA",
        "MODULE-ETA",
        "MODULE-THETA",
    }
)
_EXPECTED_RANKINGS = {
    _KNOWN_USER: (
        (1, "MODULE-DELTA", 5.0, "personalized_collaborative"),
        (2, "MODULE-GAMMA", 5.0, "personalized_collaborative"),
    ),
    _COLD_USER: (
        (1, "MODULE-THETA", 1.0, "popularity_cold_start"),
        (2, "MODULE-ETA", 0.875, "popularity_cold_start"),
    ),
}
_OUTPUT_COLUMNS = {
    "source_file",
    "input_row_number",
    "user_id",
    "rank",
    "recommended_item",
    "score",
    "strategy",
}
_ARTIFACT_URI = re.compile(r"artifact://[A-Za-z0-9]+(?:\?[^)\s>]+)?")

BUSINESS_PROMPT = (
    "两份附件分别是企业学习模块的显式评分历史和本次目标学习者。请先画像评分尺度，"
    "再查看 recommendation.collaborative_top_k 的角色与参数 schema。使用 viewer_id、"
    "module_id、rating、rated_at 绑定用户、项目、评分和时间；以 4 分为正向门槛，"
    "top_k=2，用户最少 3 次、模块最少 2 名学习者评分。请完成同一真值上的个性化候选"
    "与 popularity baseline 评价，保留完整历史训练的 analyzer，并对目标学习者附件"
    "生成推荐。交付公共推荐 Dataset、推荐结果 Artifact 和评价 Artifact 的可打开链接；"
    "最终说明候选相对热门基线的离线证据、已评分模块排除、冷启动策略，以及离线结果"
    "不能证明线上因果提升的限制。"
)

RECOMMENDATION_RANKING_RUBRIC = JudgeRubric(
    rubric_id="ml.recommendation_ranking_v1.business_outcome.v1",
    score_dimensions=(
        "recommendation_delivery",
        "evaluation_grounding",
        "cold_start_explanation",
        "decision_limits",
    ),
    allowed_reason_codes=(
        "complete_grounded_outcome",
        "recommendation_delivery_incomplete",
        "evaluation_comparison_unsupported",
        "cold_start_strategy_unclear",
        "offline_online_boundary_missing",
    ),
)

pytestmark = pytest.mark.agent_harness_live


class RecommendationRankingCase:
    """Measure public ranking outcomes without prescribing a Tool trace."""

    case_id = CASE_ID

    def __init__(
        self,
        ratings_path: Path = _RATINGS_PATH,
        targets_path: Path = _TARGETS_PATH,
    ) -> None:
        self.ratings_path = ratings_path
        self.targets_path = targets_path

    def validate_input(self) -> str:
        paths = (
            (
                self.ratings_path,
                _EXPECTED_RATINGS_SIZE,
                _EXPECTED_RATINGS_SHA256,
            ),
            (
                self.targets_path,
                _EXPECTED_TARGETS_SIZE,
                _EXPECTED_TARGETS_SHA256,
            ),
        )
        observed: list[str] = []
        for path, expected_size, expected_digest in paths:
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

    def build_submission(self, *, thread_id: str, fq_model_key: str) -> SubmitUserTurnInput:
        return SubmitUserTurnInput(
            thread_id=thread_id,
            text=BUSINESS_PROMPT,
            source_attachments=[
                SourceAttachmentInput(file_path=str(self.ratings_path.resolve())),
                SourceAttachmentInput(file_path=str(self.targets_path.resolve())),
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
                source_path=self.ratings_path,
                snapshot=snapshot,
                services=services,
            ),
            capture_attached_source_state(
                source_path=self.targets_path,
                snapshot=snapshot,
                services=services,
            ),
        )

    def assess(self, *, context: BenchmarkCaseContext) -> BenchmarkCaseAssessment:
        dataset, frame = _resolve_recommendation_outcome(context)
        apply_artifact = _resolve_apply_artifact(context, dataset)
        report_artifact, report = _resolve_evaluation_report(context)
        outcome_diagnostic = _recommendation_outcome_diagnostic(context)
        failed_tools = _failed_tool_names(context.snapshot)
        failed_tool_summary = ",".join(failed_tools) if failed_tools else "none"
        linked_artifact_count = len(_linked_artifacts(context))
        final_link_count = len(_ARTIFACT_URI.findall(_terminal_text(context.snapshot)))
        grounding_gaps = _final_answer_grounding_gaps(
            _terminal_text(context.snapshot),
            report,
        )
        grounded_answer = not grounding_gaps
        completed = canonical_completion(context.snapshot)
        source_unchanged = _sources_unchanged(self, context)
        isolated = _state_isolated(context, (apply_artifact, report_artifact))

        semantic_checks = (
            OutcomeCheck(
                "exact_private_top_k",
                frame is not None,
                "known_and_cold_rankings_observed"
                if frame is not None
                else (
                    f"qualified_rankings_missing:{outcome_diagnostic};"
                    f"failed_tools={failed_tool_summary}"
                ),
            ),
            OutcomeCheck(
                "public_recommendation_artifact",
                apply_artifact is not None,
                "linked_recommendation_artifact_observed"
                if apply_artifact is not None
                else (
                    "linked_recommendation_artifact_missing:"
                    f"final_links={final_link_count};linked_artifacts={linked_artifact_count}"
                ),
            ),
            OutcomeCheck(
                "public_ranking_evaluation",
                report is not None,
                "linked_candidate_baseline_evaluation_observed"
                if report is not None
                else (
                    "linked_candidate_baseline_evaluation_missing:"
                    f"final_links={final_link_count};linked_artifacts={linked_artifact_count}"
                ),
            ),
            OutcomeCheck(
                "grounded_final_answer",
                grounded_answer,
                "comparison_cold_start_and_limits_grounded"
                if grounded_answer
                else "recommendation_explanation_not_grounded:" + ",".join(grounding_gaps),
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
                "sources_unchanged" if source_unchanged else "source_changed_or_unverifiable",
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
            _build_judge_input(report, grounded_answer)
            if deterministic_passed and integrity_passed and report is not None
            else None
        )
        return BenchmarkCaseAssessment(
            semantic_checks=semantic_checks,
            integrity_checks=integrity_checks,
            judge_input=judge_input,
            judge_required=True,
            terminal_shape=(frame.height, frame.width) if frame is not None else None,
        )


def _resolve_recommendation_outcome(
    context: BenchmarkCaseContext,
) -> tuple[Any | None, pl.DataFrame | None]:
    target_source_ids = _source_ids_for_digest(context, _EXPECTED_TARGETS_SHA256)
    datasets = list(context.services.datasets.list_datasets())
    by_id = {str(dataset.id): dataset for dataset in datasets}
    for dataset in datasets:
        if not _is_run_descendant(
            dataset,
            by_id,
            target_source_ids,
            context.run_dataset_ids,
        ):
            continue
        try:
            frame = load_tabular_frame(Path(dataset.source_path), dataset.source_format)
        except Exception:
            continue
        if _matches_recommendations(frame):
            return dataset, frame
    return None, None


def _recommendation_outcome_diagnostic(context: BenchmarkCaseContext) -> str:
    target_source_ids = _source_ids_for_digest(context, _EXPECTED_TARGETS_SHA256)
    if not target_source_ids:
        return "target_source_identity_missing"
    datasets = list(context.services.datasets.list_datasets())
    by_id = {str(dataset.id): dataset for dataset in datasets}
    descendant_count = 0
    readable_count = 0
    expected_column_count = 0
    expected_row_count = 0
    for dataset in datasets:
        if not _is_run_descendant(
            dataset,
            by_id,
            target_source_ids,
            context.run_dataset_ids,
        ):
            continue
        descendant_count += 1
        try:
            frame = load_tabular_frame(Path(dataset.source_path), dataset.source_format)
        except Exception:
            continue
        readable_count += 1
        if set(frame.columns) != _OUTPUT_COLUMNS:
            continue
        expected_column_count += 1
        if frame.height != 4:
            continue
        expected_row_count += 1
        if _matches_recommendations(frame):
            return "qualified_rankings_observed"
    if descendant_count == 0:
        return "target_descendant_missing"
    if readable_count == 0:
        return "target_descendant_unreadable"
    if expected_column_count == 0:
        return "recommendation_columns_mismatch"
    if expected_row_count == 0:
        return "recommendation_row_count_mismatch"
    return "recommendation_values_mismatch"


def _failed_tool_names(snapshot: Any | None) -> tuple[str, ...]:
    messages = list(getattr(snapshot, "messages", [])) if snapshot is not None else []
    call_names = {
        str(getattr(message, "id", "")): str(getattr(message, "tool_id", "") or "unknown")
        for message in messages
        if enum_value(getattr(message, "kind", None)) == "tool_call"
    }
    names = {
        call_names.get(str(getattr(message, "tool_call_message_id", "")), "unknown")
        for message in messages
        if enum_value(getattr(message, "kind", None)) == "tool_result"
        and enum_value(getattr(message, "result_status", None)) == "failed"
    }
    return tuple(sorted(names))


def _matches_recommendations(frame: pl.DataFrame) -> bool:
    if frame.height != 4 or set(frame.columns) != _OUTPUT_COLUMNS:
        return False
    observed: dict[str, list[tuple[int, str, float, str]]] = {}
    try:
        for row in frame.to_dicts():
            user = str(row["user_id"]).strip()
            rank = int(row["rank"])
            item = str(row["recommended_item"]).strip()
            score = float(row["score"])
            strategy = str(row["strategy"]).strip()
            if not user or not item or not math.isfinite(score):
                return False
            observed.setdefault(user, []).append((rank, item, score, strategy))
    except KeyError, TypeError, ValueError:
        return False
    if set(observed) != set(_EXPECTED_RANKINGS):
        return False
    for user, expected in _EXPECTED_RANKINGS.items():
        rows = sorted(observed[user])
        if len(rows) != 2 or [row[0] for row in rows] != [1, 2]:
            return False
        for actual, wanted in zip(rows, expected, strict=True):
            if not (
                actual[0] == wanted[0]
                and actual[1] == wanted[1]
                and math.isclose(actual[2], wanted[2], rel_tol=1e-9, abs_tol=1e-9)
                and actual[3] == wanted[3]
            ):
                return False
    known_items = {item for _rank, item, _score, _strategy in observed[_KNOWN_USER]}
    return not bool(known_items & _KNOWN_SEEN_ITEMS)


def _resolve_apply_artifact(context: BenchmarkCaseContext, dataset: Any | None) -> Any | None:
    if dataset is None:
        return None
    for artifact in _linked_artifacts(context):
        metadata = getattr(artifact, "metadata_payload", {})
        path = Path(str(getattr(artifact, "absolute_path", "")))
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
        if payload is not None and _matches_evaluation_report(payload):
            return artifact, payload
    return None, None


def _matches_evaluation_report(payload: dict[str, Any]) -> bool:
    evaluation = payload.get("evaluation")
    baseline = payload.get("baseline_evaluation")
    comparison = payload.get("comparison")
    facts = payload.get("recommendation_evaluation")
    if not (
        payload.get("model_key") == "recommendation.collaborative_top_k"
        and isinstance(evaluation, dict)
        and isinstance(baseline, dict)
        and isinstance(comparison, dict)
        and isinstance(facts, dict)
        and _report_is_privacy_safe(payload)
    ):
        return False
    candidate_facts = facts.get("candidate")
    baseline_facts = facts.get("baseline")
    split = facts.get("split")
    preparation = facts.get("preparation")
    cold_start = facts.get("cold_start")
    limitations = facts.get("limitations")
    if not all(
        isinstance(value, expected_type)
        for value, expected_type in (
            (candidate_facts, dict),
            (baseline_facts, dict),
            (split, dict),
            (preparation, dict),
            (cold_start, dict),
            (limitations, list),
        )
    ):
        return False
    assert isinstance(candidate_facts, dict)
    assert isinstance(baseline_facts, dict)
    assert isinstance(split, dict)
    assert isinstance(preparation, dict)
    assert isinstance(cold_start, dict)
    assert isinstance(limitations, list)
    candidate_metrics = evaluation.get("metrics")
    baseline_metrics = baseline.get("metrics")
    if not (
        evaluation.get("primary_metric_name") == "ndcg_at_k"
        and baseline.get("primary_metric_name") == "ndcg_at_k"
        and isinstance(candidate_metrics, dict)
        and isinstance(baseline_metrics, dict)
        and _ranking_metrics_match(candidate_metrics, candidate=True)
        and _ranking_metrics_match(baseline_metrics, candidate=False)
    ):
        return False
    if not (
        comparison.get("primary_metric_name") == "ndcg_at_k"
        and comparison.get("direction") == "max"
        and comparison.get("verdict") == "candidate_better"
        and math.isclose(float(comparison.get("candidate_value")), 0.9, abs_tol=1e-9)
        and math.isclose(
            float(comparison.get("baseline_value")),
            0.26309297535714576,
            abs_tol=1e-9,
        )
    ):
        return False
    if not (
        facts.get("protocol") == "recommendation_ranking.v1"
        and split.get("policy_key") == "latest_positive_per_user.v1"
        and re.fullmatch(
            r"[0-9a-f]{64}",
            str(split.get("source_dataset_snapshot_digest") or ""),
        )
        is not None
        and split.get("eligible_user_count") == 10
        and split.get("train_interaction_count") == 39
        and split.get("holdout_interaction_count") == 10
        and split.get("user_overlap_count") == 10
        and preparation.get("source_row_count") == 49
        and preparation.get("admitted_interaction_count") == 49
        and preparation.get("user_count") == 10
        and preparation.get("item_count") == 8
        and preparation.get("candidate_item_count") == 8
        and preparation.get("positive_rating_threshold") == 4.0
        and preparation.get("time_column_present") is True
    ):
        return False
    return bool(
        candidate_facts.get("seen_item_violation_count") == 0
        and baseline_facts.get("seen_item_violation_count") == 0
        and cold_start.get("policy_key") == "global_popularity_unseen.v1"
        and cold_start.get("known_user_strategy") == "item_neighborhood_explicit_rating.v1"
        and cold_start.get("cold_user_strategy") == "global_popularity_unseen.v1"
        and cold_start.get("cold_user_supported") is True
        and cold_start.get("cold_item_supported") is False
        and bool(limitations)
    )


def _ranking_metrics_match(metrics: dict[str, Any], *, candidate: bool) -> bool:
    expected = (
        {
            "ndcg_at_k": 0.9,
            "recall_at_k": 0.9,
            "hit_rate_at_k": 0.9,
            "mrr_at_k": 0.9,
        }
        if candidate
        else {
            "ndcg_at_k": 0.26309297535714576,
            "recall_at_k": 0.3,
            "hit_rate_at_k": 0.3,
            "mrr_at_k": 0.25,
        }
    )
    try:
        return expected.keys() <= metrics.keys() and all(
            math.isclose(float(metrics[name]), value, abs_tol=1e-9) for name, value in expected.items()
        )
    except TypeError, ValueError:
        return False


def _report_is_privacy_safe(payload: dict[str, Any]) -> bool:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).upper()
    private_values = {
        *_EXPECTED_RANKINGS,
        *(
            item
            for recommendations in _EXPECTED_RANKINGS.values()
            for _rank, item, _score, _strategy in recommendations
        ),
        *_KNOWN_SEEN_ITEMS,
        _RATINGS_PATH.name.upper(),
        _TARGETS_PATH.name.upper(),
    }
    return not (
        any(value.upper() in serialized for value in private_values)
        or "LEARNER-" in serialized
        or "MODULE-" in serialized
        or re.search(r"[A-Z]:[\\/]", serialized) is not None
    )


def _final_answer_grounding_gaps(
    text: str,
    report: dict[str, Any] | None,
) -> tuple[str, ...]:
    if not text:
        return ("missing_final_answer",)
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).lower())
    collaborative = any(marker in normalized for marker in ("协同", "collaborative", "个性化候选"))
    popularity = any(marker in normalized for marker in ("热门", "popularity", "流行度"))
    comparison = any(marker in normalized for marker in ("优于", "高于", "改善", "提升", "better", "outperform"))
    ranking_metrics = "ndcg" in normalized and any(
        marker in normalized for marker in ("recall", "hitrate", "hit_rate", "mrr", "召回", "命中")
    )
    seen_exclusion = any(marker in normalized for marker in ("已评分", "已见", "seen")) and any(
        marker in normalized for marker in ("排除", "剔除", "过滤", "不再推荐")
    )
    cold_start = "冷启动" in normalized and popularity
    offline_boundary = "离线" in normalized and any(
        marker in normalized for marker in ("不能证明", "不代表", "不等于", "非因果", "线上", "a/b")
    )
    links = len(_ARTIFACT_URI.findall(text)) >= 2
    checks = (
        ("evaluation_artifact", report is not None),
        ("collaborative_candidate", collaborative),
        ("popularity_baseline", popularity),
        ("candidate_baseline_comparison", comparison),
        ("ranking_metrics", ranking_metrics),
        ("seen_exclusion", seen_exclusion),
        ("cold_start", cold_start),
        ("offline_online_boundary", offline_boundary),
        ("dataset_and_artifact_links", links),
    )
    return tuple(name for name, passed in checks if not passed)


def _build_judge_input(report: dict[str, Any], grounded_answer: bool) -> JudgeInput:
    evaluation = report["evaluation"]
    baseline = report["baseline_evaluation"]
    comparison = report["comparison"]
    facts = report["recommendation_evaluation"]
    return JudgeInput(
        rubric=RECOMMENDATION_RANKING_RUBRIC,
        task_intent=BUSINESS_PROMPT,
        facts=(
            "目标结果要求已知用户个性化 Top-2、已见项目零违规及冷用户确定性热门回退。",
            "候选与热门基线必须使用同一私有 holdout 真值，并报告排序指标和限制。",
            "离线排序指标不得解释为线上因果提升，冷项目在 v1 中不受支持。",
        ),
        artifact_evidence=(
            (
                "public_recommendation: target_count=2; top_k=2; "
                "personalized=true; cold_start=true; seen_item_violations=0"
            ),
            (
                "public_evaluation: metric=ndcg_at_k; "
                f"candidate={float(evaluation['primary_metric_value']):.6f}; "
                f"baseline={float(baseline['primary_metric_value']):.6f}; "
                f"verdict={comparison['verdict']}"
            ),
            (
                "public_protocol: "
                f"eligible_users={int(facts['split']['eligible_user_count'])}; "
                f"policy={facts['split']['policy_key']}; shared_truth=true"
            ),
            (
                "public_identity: recommendation_dataset_linked=true; "
                "evaluation_artifact_linked=true; lineage_verified=true; "
                f"final_answer_grounded={str(grounded_answer).lower()}"
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


def _sources_unchanged(case: RecommendationRankingCase, context: BenchmarkCaseContext) -> bool:
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
            and bool(
                source_dataset_ids_for_external_digest(
                    snapshot=context.snapshot,
                    services=context.services,
                    digest=state.external_sha256,
                )
            )
            for path, state in zip(
                (case.ratings_path, case.targets_path),
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


def test_ml_recommendation_ranking(agent_harness_benchmark) -> None:
    """Measure public personalized ranking without prescribing a Tool trace."""

    agent_harness_benchmark.run(RecommendationRankingCase())
