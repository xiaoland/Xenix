"""Clean-room paid-live Agent case for trustworthy cluster selection."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import unicodedata
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
    enum_value,
    is_within,
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
_EXPECTED_PROFILE_MEDIANS = {
    _LOYAL_ACCOUNTS: (24.5, 1.4, 40.5),
    _GROWING_ACCOUNTS: (12.5, 5.25, 77.5),
    _AT_RISK_ACCOUNTS: (3.5, 11.75, 123.5),
}
_ARTIFACT_URI = re.compile(r"artifact://[A-Za-z0-9]+(?:\?[^)\s>]+)?")
_LONG_ID = re.compile(r"\b[A-Fa-f0-9]{24,64}\b")
_WINDOWS_PATH = re.compile(r"(?<!\w)[A-Za-z]:[\\/][^\s]+")

BUSINESS_PROMPT = (
    "请先画像，只用 monthly_orders、return_rate_pct 和 service_minutes 比较 KMeans 的 2、3、4 "
    "群方案；account_id 只保留作业务标识，不能作为特征。请先读取 clustering.kmeans 的参数 "
    "schema，再为三个候选填写有界的浅层参数，不要自行改随机种子或底层优化器。请根据同口径"
    "质量、稳定性、空基线和群组规模证据选择方案，生成保留原始四列并新增 cluster_id 的公共 "
    "Dataset，并给出可打开的画像/评估 Artifact。最终用原始尺度解释各群、选择依据、内部指标"
    "局限和下一步业务验证建议。"
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
        "identifier_or_row_disclosure",
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
        dataset, frame = _resolve_assignment_outcome(context, self.source_path)
        report_artifact, report_facts = _resolve_cluster_report(context, frame)
        final_text = _terminal_text(context.snapshot)
        grounding_gaps = _final_answer_grounding_gaps(final_text)
        grounded_answer = not grounding_gaps
        completed = canonical_completion(context.snapshot)
        source_unchanged = _source_unchanged(self.source_path, context)
        isolated = _state_isolated(context, report_artifact)

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
            OutcomeCheck(
                "grounded_final_answer",
                grounded_answer,
                (
                    "selection_profiles_and_limits_grounded"
                    if grounded_answer
                    else "selection_explanation_not_grounded:" + ",".join(grounding_gaps)
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
            _build_judge_input(report_facts, final_text)
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


def _resolve_assignment_outcome(
    context: BenchmarkCaseContext,
    source_path: Path,
) -> tuple[Any | None, pl.DataFrame | None]:
    expected_source = load_tabular_frame(source_path, DatasetSourceFormat.CSV)
    datasets = list(context.services.datasets.list_datasets())
    by_id = {str(dataset.id): dataset for dataset in datasets}
    source_ids = _source_ids(context)
    for dataset in datasets:
        if not _is_run_descendant(dataset, by_id, source_ids, context.run_dataset_ids):
            continue
        try:
            frame = load_tabular_frame(Path(dataset.source_path), dataset.source_format)
        except Exception:
            continue
        if _matches_assignment(frame, expected_source):
            return dataset, frame
    return None, None


def _matches_assignment(frame: pl.DataFrame, expected_source: pl.DataFrame) -> bool:
    required = {*expected_source.columns, "cluster_id"}
    if frame.height != 18 or set(frame.columns) != required:
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
    for artifact in _linked_artifacts(context):
        if enum_value(getattr(artifact, "kind", None)) != "report":
            continue
        payload = _read_json_artifact(artifact, context.runtime_home)
        facts = _cluster_facts(payload)
        if facts is not None and _matches_cluster_report(facts, frame):
            return artifact, facts
    return None, None


def _cluster_facts(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload.get("quality"), dict):
        return payload
    nested = payload.get("clustering_evaluation")
    return nested if isinstance(nested, dict) else None


def _matches_cluster_report(facts: dict[str, Any], frame: pl.DataFrame) -> bool:
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
        and stability.get("run_count") == 5
        and _finite_at_least(stability.get("mean_adjusted_rand_index"), 0.9)
        and baseline.get("run_count") == 16
        and _finite_at_least(baseline.get("candidate_margin"), 0.1)
        and sorted(item.get("row_count") for item in sizes if isinstance(item, dict)) == [6, 6, 6]
        and bool(limitations)
    ):
        return False

    memberships: dict[int, frozenset[str]] = {}
    try:
        for cluster_id in frame.get_column("cluster_id").unique().to_list():
            accounts = frame.filter(pl.col("cluster_id") == cluster_id).get_column("account_id")
            memberships[int(cluster_id)] = frozenset(str(value) for value in accounts.to_list())
    except TypeError, ValueError:
        return False
    expected_by_cluster = {
        cluster_id: _EXPECTED_PROFILE_MEDIANS[membership]
        for cluster_id, membership in memberships.items()
        if membership in _EXPECTED_PROFILE_MEDIANS
    }
    if len(expected_by_cluster) != 3:
        return False
    observed_profiles: dict[int, dict[str, float]] = {}
    for raw_profile in profiles:
        if not isinstance(raw_profile, dict) or not isinstance(raw_profile.get("numeric"), list):
            continue
        try:
            cluster_id = int(raw_profile["cluster_id"])
            observed_profiles[cluster_id] = {
                str(item["feature"]): float(item["median"])
                for item in raw_profile["numeric"]
                if isinstance(item, dict) and item.get("feature") in _FEATURE_COLUMNS and item.get("median") is not None
            }
        except KeyError, TypeError, ValueError:
            return False
    for cluster_id, expected_values in expected_by_cluster.items():
        observed = observed_profiles.get(cluster_id, {})
        if any(
            not math.isclose(observed.get(feature, math.nan), expected, abs_tol=1e-6)
            for feature, expected in zip(_FEATURE_COLUMNS, expected_values, strict=True)
        ):
            return False
    return True


def _finite_at_least(value: Any, minimum: float) -> bool:
    try:
        number = float(value)
    except TypeError, ValueError:
        return False
    return math.isfinite(number) and number >= minimum


def _final_answer_grounding_gaps(text: str) -> tuple[str, ...]:
    if not text:
        return ("missing_final_answer",)
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).lower())
    checks = (
        ("candidate_scope", all(str(value) in normalized for value in (2, 3, 4))),
        (
            "selected_cluster_count",
            bool(
                re.search(
                    r"(?:选择|选定|保留|最终|推荐).{0,16}(?:k=?3|3(?:群|组|类|个cluster)|三(?:群|组|类))",
                    normalized,
                )
                or re.search(
                    r"(?:k=?3|3(?:群|组|类|个cluster)|三(?:群|组|类)).{0,16}(?:选择|选定|保留|最终|推荐)",
                    normalized,
                )
            ),
        ),
        ("quality_metric", "silhouette" in normalized or "轮廓" in normalized),
        ("stability", "稳定" in normalized or "stability" in normalized),
        (
            "original_scale_profiles",
            all(marker in normalized for marker in ("monthly_orders", "return_rate", "service_minutes"))
            or all(marker in normalized for marker in ("订单", "退货", "服务")),
        ),
        (
            "limitations",
            any(marker in normalized for marker in ("局限", "限制", "不能证明", "不代表", "非因果")),
        ),
        ("artifact_link", bool(_ARTIFACT_URI.search(text))),
    )
    return tuple(name for name, passed in checks if not passed)


def _build_judge_input(report: dict[str, Any], final_text: str) -> JudgeInput:
    quality = report["quality"]
    stability = report["stability"]
    baseline = report["null_baseline"]
    evidence = (
        "public_assignment: row_count=18; cluster_sizes=6/6/6; source_features_unchanged=true",
        (
            "public_report: cluster_count=3; "
            f"silhouette={float(quality['silhouette']):.6f}; "
            f"stability_mean_ari={float(stability['mean_adjusted_rand_index']):.6f}; "
            f"null_margin={float(baseline['candidate_margin']):.6f}"
        ),
        "public_profiles: median(monthly_orders, return_rate_pct, service_minutes)="
        "(24.5,1.4,40.5)|(12.5,5.25,77.5)|(3.5,11.75,123.5)",
        f"final_answer: {_safe_final_text(final_text)}",
    )
    return JudgeInput(
        rubric=CLUSTER_SELECTION_RUBRIC,
        task_intent=BUSINESS_PROMPT,
        facts=(
            "候选范围是 KMeans k=2/3/4，确定性公共结果选择 k=3。",
            "三个群各 6 个账户；画像只使用原尺度聚合，不把 account_id 当特征。",
            "轮廓、稳定性和空基线都是内部证据，不能证明外部有效性或因果解释。",
        ),
        artifact_evidence=evidence,
    )


def _safe_final_text(text: str) -> str:
    value = _ARTIFACT_URI.sub("[public artifact link]", text)
    value = _LONG_ID.sub("[stable id]", value)
    value = _WINDOWS_PATH.sub("[local path]", value)
    lines = [
        "[row-like content omitted]" if len([part for part in line.split(",") if part.strip()]) >= 4 else line
        for line in value.splitlines()
    ]
    return " ".join(" ".join(lines).split())[:480]


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


def _source_ids(context: BenchmarkCaseContext) -> set[str]:
    state = context.source_state
    return set(state.source_dataset_ids) if isinstance(state, AttachedSourceState) else set()


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


def _source_unchanged(source_path: Path, context: BenchmarkCaseContext) -> bool:
    state = context.source_state
    if not isinstance(state, AttachedSourceState) or not state.source_dataset_ids:
        return False
    try:
        return attached_source_unchanged(
            source_path=source_path,
            source_state=state,
            services=context.services,
        )
    except Exception:
        return False


def _state_isolated(context: BenchmarkCaseContext, artifact: Any | None) -> bool:
    if not context.settings_unchanged:
        return False
    try:
        datasets_confined = all(
            is_within(Path(str(dataset.source_path)), context.runtime_home)
            for dataset in context.services.datasets.list_datasets()
        )
        artifact_confined = artifact is None or is_within(
            Path(str(getattr(artifact, "absolute_path", ""))),
            context.runtime_home,
        )
        return datasets_confined and artifact_confined
    except Exception:
        return False


def test_ml_cluster_selection(agent_harness_benchmark) -> None:
    """Measure the selected public outcome without prescribing a Tool trace."""

    agent_harness_benchmark.run(ClusterSelectionCase())
