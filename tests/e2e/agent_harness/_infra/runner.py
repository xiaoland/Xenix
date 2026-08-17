"""Sequential, isolated real-LLM benchmark runner for AgentHarnessService."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Iterator
from uuid import uuid4

from xenix.config import AppPaths, ensure_app_dirs, package_root
from xenix.observability import LLMTokenUsage, LLM_USAGE_JOURNAL_FILE_NAME, LocalLLMUsageObservability
from xenix.services.agent.composition import build_headless_agent_services
from xenix.services.embedding_service import EmbeddingSettings, EmbeddingSettingsService
from xenix.services.knowledge_derivation_service import KnowledgeDerivationService
from xenix.services.knowledge_import_service import KnowledgeImportService
from xenix.services.knowledge_index_service import KnowledgeIndexService
from xenix.services.llm import FrozenLLMSettingsSource, LLMService, LLMSettings
from xenix.services.ml.worker_settings import MLWorkerSettingsService
from xenix.services.storage import StorageBootstrapService

from .contracts import (
    AgentHarnessBenchmarkResult,
    BenchmarkCase,
    BenchmarkCaseAssessment,
    BenchmarkCaseContext,
    BenchmarkExecutionMode,
    BenchmarkCasePreparationServices,
    BenchmarkCaseServices,
    BenchmarkIdentity,
    BenchmarkInputError,
    BenchmarkMetrics,
    BenchmarkRunStatus,
    JudgeResult,
    JudgeStatus,
    SemanticVerdict,
    TokenUsage,
)
from .budgets import (
    BenchmarkBudgetController,
    BenchmarkBudgetError,
    BenchmarkBudgetPolicy,
    BenchmarkBudgetSnapshot,
    BenchmarkBudgetStatus,
    IsolatedCallStatus,
    run_isolated_call,
)
from .judge import judge_independence, run_judge


LLM_SETTINGS_PATH_ENV = "XENIX_AGENT_BENCHMARK_LLM_SETTINGS_PATH"
EMBEDDING_SETTINGS_PATH_ENV = "XENIX_AGENT_BENCHMARK_EMBEDDING_SETTINGS_PATH"
JUDGE_LLM_SETTINGS_PATH_ENV = "XENIX_AGENT_BENCHMARK_JUDGE_LLM_SETTINGS_PATH"
DEFAULT_OUTPUT_DIRECTORY = Path("build") / "agent-harness-benchmarks"
DEFAULT_BUDGET_POLICY = BenchmarkBudgetPolicy()


class BenchmarkSettingsError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class BenchmarkRun:
    result: AgentHarnessBenchmarkResult
    persisted: bool


@dataclass(frozen=True)
class _JudgeConfiguration:
    settings: LLMSettings | None = None
    settings_sha256: str | None = None
    model_key: str | None = None
    setup_error: str | None = None

    @property
    def enabled(self) -> bool:
        return self.settings is not None and self.model_key is not None and self.setup_error is None


@dataclass
class _StreamMeasurements:
    snapshot: Any | None = None
    source_state: Any | None = None
    source_state_captured: bool = False
    pending_message_ids: set[str] | None = None
    provider_retry_count: int = 0
    title_event_count: int = 0
    final_snapshot_seen: bool = False

    def __post_init__(self) -> None:
        if self.pending_message_ids is None:
            self.pending_message_ids = set()

    def observe(self, event: Any, *, case: BenchmarkCase, services: BenchmarkCaseServices) -> None:
        pending_message_id = getattr(event, "pending_message_id", None)
        if isinstance(pending_message_id, str) and pending_message_id:
            self.pending_message_ids.add(pending_message_id)
        event_kind = getattr(event, "kind", None)
        if event_kind == "connection":
            self.provider_retry_count += 1
        if event_kind == "title":
            self.title_event_count += 1
        snapshot = getattr(event, "snapshot", None)
        if snapshot is not None:
            self.snapshot = snapshot
            if event_kind == "snapshot" and bool(getattr(event, "is_final", False)):
                self.final_snapshot_seen = True
            if not self.source_state_captured:
                self.source_state = case.capture_source_state(
                    snapshot=snapshot,
                    services=services,
                )
                self.source_state_captured = True


class _BoundedLLMService(LLMService):
    """Real provider gateway with benchmark-only request admission guards."""

    def __init__(
        self,
        settings_source: FrozenLLMSettingsSource,
        budget: BenchmarkBudgetController,
    ) -> None:
        super().__init__(settings_source)
        self._budget = budget

    def complete(
        self,
        *,
        fq_model_key: str | None = None,
        messages: list[Any],
        tools: list[Any],
        retry_callback: Callable[[Any], None] | None = None,
        before_provider_request: Callable[[], None] | None = None,
    ) -> Any:
        self._budget.begin_sampling_round()
        response = super().complete(
            fq_model_key=fq_model_key,
            messages=messages,
            tools=tools,
            retry_callback=retry_callback,
            before_provider_request=self._admission(before_provider_request),
        )
        self._observe_response(response)
        return response

    def stream(
        self,
        *,
        fq_model_key: str | None = None,
        messages: list[Any],
        tools: list[Any],
        before_provider_request: Callable[[], None] | None = None,
    ) -> Iterator[Any]:
        self._budget.begin_sampling_round()
        for event in super().stream(
            fq_model_key=fq_model_key,
            messages=messages,
            tools=tools,
            before_provider_request=self._admission(before_provider_request),
        ):
            response = getattr(event, "response", None)
            if response is not None:
                self._observe_response(response)
            yield event

    def _admission(
        self,
        original: Callable[[], None] | None,
    ) -> Callable[[], None]:
        def admit() -> None:
            if original is not None:
                original()
            self._budget.admit_provider_attempt()

        return admit

    def _observe_response(self, response: Any) -> None:
        usage = LLMTokenUsage.from_payload(getattr(response, "usage_payload", None))
        self._budget.observe_subject_response(
            usage.total_tokens if usage is not None else None
        )


class _HeadlessBenchmarkCell:
    """One isolated production-service composition behind the runner contract."""

    def __init__(
        self,
        *,
        paths: AppPaths,
        settings: LLMSettings,
        embedding_settings: EmbeddingSettings | None,
        budget: BenchmarkBudgetController,
    ) -> None:
        self.paths = paths
        self._closed = False
        self._storage = None
        self._knowledge_import = None
        self._knowledge_derivation = None
        self._knowledge_index = None
        try:
            self._storage = StorageBootstrapService().initialize(paths)
            llm = _BoundedLLMService(FrozenLLMSettingsSource(settings), budget)
            worker_settings = MLWorkerSettingsService(paths)
            embedding_settings_service = EmbeddingSettingsService(paths)
            if embedding_settings is not None:
                embedding_settings_service.save(embedding_settings)
            services = build_headless_agent_services(
                paths=paths,
                session_factory=self._storage.session_factory,
                llm=llm,
                embedding_settings_service=embedding_settings_service,
                ml_worker_settings=worker_settings,
                usage_observability=LocalLLMUsageObservability(
                    paths.logs / LLM_USAGE_JOURNAL_FILE_NAME
                ),
            )
            self._knowledge_index = KnowledgeIndexService(
                session_factory=self._storage.session_factory,
                semantic_service=services.knowledge_semantic,
                embedding_service=services.embedding,
                embedding_settings_source=embedding_settings_service,
                start_worker=False,
            )
            self._knowledge_derivation = KnowledgeDerivationService(
                paths=paths,
                session_factory=self._storage.session_factory,
            )
            self._knowledge_import = KnowledgeImportService(
                paths=paths,
                session_factory=self._storage.session_factory,
                artifact_service=services.artifacts,
                canonical_ready_notifier=self._knowledge_derivation.enqueue_generation,
            )
            self.harness = services.harness
            self.datasets = services.datasets
            self.artifacts = services.artifacts
            self.preparation_services = BenchmarkCasePreparationServices(
                knowledge_import=self._knowledge_import,
                knowledge_derivation=self._knowledge_derivation,
                knowledge_index=self._knowledge_index,
            )
        except Exception:
            self.close()
            raise

    def create_thread(self, *, title: str, fq_model_key: str) -> str:
        snapshot = self.harness.create_thread(
            title=title,
            fq_model_key=fq_model_key,
        )
        return snapshot.thread.id

    def execute_submission(
        self,
        *,
        submission: Any,
        measurements: _StreamMeasurements,
        case: BenchmarkCase,
        services: BenchmarkCaseServices,
    ) -> None:
        for event in self.harness.submit_user_turn_stream(submission):
            measurements.observe(event, case=case, services=services)

    def integrity_checks(self) -> tuple[Any, ...]:
        return ()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._knowledge_import is not None:
            self._knowledge_import.shutdown()
        if self._knowledge_derivation is not None:
            self._knowledge_derivation.shutdown()
        if self._knowledge_index is not None:
            self._knowledge_index.shutdown()
        if self._storage is not None:
            self._storage.engine.dispose()


def resolve_llm_settings_path(explicit_path: Path | None = None) -> Path:
    if explicit_path is not None:
        return explicit_path
    raw = os.environ.get(LLM_SETTINGS_PATH_ENV, "").strip()
    if not raw:
        raise BenchmarkSettingsError("missing_llm_settings")
    return Path(raw)


def resolve_judge_llm_settings_path(explicit_path: Path | None = None) -> Path:
    if explicit_path is not None:
        return explicit_path
    raw = os.environ.get(JUDGE_LLM_SETTINGS_PATH_ENV, "").strip()
    if not raw:
        raise BenchmarkSettingsError("missing_judge_llm_settings")
    return Path(raw)


def resolve_embedding_settings_path(explicit_path: Path | None = None) -> Path | None:
    if explicit_path is not None:
        return explicit_path
    raw = os.environ.get(EMBEDDING_SETTINGS_PATH_ENV, "").strip()
    return Path(raw) if raw else None


def load_settings_snapshot(path: Path) -> tuple[LLMSettings, str]:
    if not path.is_file():
        raise BenchmarkSettingsError("missing_llm_settings")
    try:
        raw = path.read_text(encoding="utf-8")
        settings = LLMSettings.model_validate_json(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise BenchmarkSettingsError("invalid_llm_settings") from None
    return settings, _sha256_file(path)


def load_embedding_settings_snapshot(path: Path) -> tuple[EmbeddingSettings, str]:
    if not path.is_file():
        raise BenchmarkSettingsError("missing_embedding_settings")
    try:
        raw = path.read_text(encoding="utf-8")
        settings = EmbeddingSettings.model_validate_json(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise BenchmarkSettingsError("invalid_embedding_settings") from None
    return settings, _sha256_file(path)


def _load_judge_configuration(
    *,
    judge_settings_path: Path | None,
    judge_model_key: str | None,
) -> _JudgeConfiguration:
    environment_path = os.environ.get(JUDGE_LLM_SETTINGS_PATH_ENV, "").strip()
    requested = judge_settings_path is not None or bool(environment_path) or bool(judge_model_key and judge_model_key.strip())
    if not requested:
        return _JudgeConfiguration()
    try:
        resolved_path = resolve_judge_llm_settings_path(judge_settings_path)
        settings, settings_sha256 = load_settings_snapshot(resolved_path)
    except BenchmarkSettingsError as exc:
        return _JudgeConfiguration(setup_error=f"judge_{exc.code}")
    selected_model = (judge_model_key or settings.default_fq_model_key).strip()
    setup_error = _model_setup_error(settings, selected_model)
    if setup_error is not None:
        return _JudgeConfiguration(
            settings_sha256=settings_sha256,
            model_key=selected_model or None,
            setup_error=f"judge_{setup_error}",
        )
    effective_settings = settings.model_copy(
        deep=True,
        update={"retry_attempts": DEFAULT_BUDGET_POLICY.max_provider_attempts},
    )
    return _JudgeConfiguration(
        settings=effective_settings,
        settings_sha256=settings_sha256,
        model_key=selected_model,
    )


def selected_model_key(
    settings: LLMSettings,
    requested_model: str | None = None,
) -> str:
    requested = requested_model.strip() if isinstance(requested_model, str) else ""
    selected = requested or settings.default_fq_model_key.strip()
    if not selected:
        raise BenchmarkSettingsError("missing_default_model")
    return selected


def dry_run_model(
    *,
    settings_path: Path | None = None,
    requested_model: str | None = None,
) -> str:
    resolved_path = resolve_llm_settings_path(settings_path)
    settings, _settings_sha256 = load_settings_snapshot(resolved_path)
    return selected_model_key(settings, requested_model)


def run_benchmark(
    *,
    settings_path: Path | None,
    embedding_settings_path: Path | None = None,
    case: BenchmarkCase,
    execution_mode: BenchmarkExecutionMode = BenchmarkExecutionMode.HEADLESS,
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY,
    requested_model: str | None = None,
    judge_settings_path: Path | None = None,
    judge_model_key: str | None = None,
    budget_policy: BenchmarkBudgetPolicy = DEFAULT_BUDGET_POLICY,
    harness_variant: str = "baseline",
    invocation_reported_subject_tokens: int = 0,
    invocation_id: str | None = None,
) -> BenchmarkRun:
    identity = _repository_identity()
    preserved_invocation_tokens = (
        invocation_reported_subject_tokens
        if isinstance(invocation_reported_subject_tokens, int)
        and not isinstance(invocation_reported_subject_tokens, bool)
        and invocation_reported_subject_tokens >= 0
        else 0
    )
    try:
        normalized_variant = _normalized_harness_variant(harness_variant)
        normalized_invocation_id = _normalized_invocation_id(invocation_id)
        resolved_settings_path = resolve_llm_settings_path(settings_path)
        settings, settings_sha256 = load_settings_snapshot(resolved_settings_path)
        model_key = selected_model_key(settings, requested_model)
        effective_settings = _effective_subject_settings(settings, budget_policy)
        effective_settings_sha256 = _sha256_text(
            effective_settings.model_dump_json()
        )
        identity = BenchmarkIdentity(
            fixture_sha256=None,
            settings_sha256=settings_sha256,
            repository_commit=identity.repository_commit,
            repository_dirty=identity.repository_dirty,
            effective_settings_sha256=effective_settings_sha256,
            harness_variant=normalized_variant,
            invocation_id=normalized_invocation_id,
            case_definition_sha256=_case_definition_sha256(case),
            runtime_sha256=_runtime_sha256(),
        )
    except BenchmarkSettingsError as exc:
        fallback_variant = (
            harness_variant.strip()
            if isinstance(harness_variant, str) and harness_variant.strip()
            else "unresolved"
        )[:96]
        return _persist_result(
            output_directory,
            _invalid_result(
                case_id=case.case_id,
                provider_model="unresolved",
                execution_mode=execution_mode,
                identity=replace(identity, harness_variant=fallback_variant),
                failure_kind=exc.code,
                budget_policy=budget_policy,
                invocation_reported_subject_tokens=preserved_invocation_tokens,
            ),
        )

    resolved_embedding_settings_path = resolve_embedding_settings_path(
        embedding_settings_path
    )
    embedding_settings: EmbeddingSettings | None = None
    embedding_settings_sha256: str | None = None
    if resolved_embedding_settings_path is not None:
        try:
            embedding_settings, embedding_settings_sha256 = (
                load_embedding_settings_snapshot(resolved_embedding_settings_path)
            )
        except BenchmarkSettingsError as exc:
            invalid_identity = BenchmarkIdentity(
                settings_sha256=settings_sha256,
                repository_commit=identity.repository_commit,
                repository_dirty=identity.repository_dirty,
                effective_settings_sha256=effective_settings_sha256,
                harness_variant=normalized_variant,
                invocation_id=normalized_invocation_id,
                case_definition_sha256=_case_definition_sha256(case),
                runtime_sha256=_runtime_sha256(),
            )
            return _persist_result(
                output_directory,
                _invalid_result(
                    case_id=case.case_id,
                    provider_model=model_key,
                    execution_mode=execution_mode,
                    identity=invalid_identity,
                    failure_kind=exc.code,
                    budget_policy=budget_policy,
                    invocation_reported_subject_tokens=preserved_invocation_tokens,
                ),
            )
    judge_configuration = _load_judge_configuration(
        judge_settings_path=judge_settings_path,
        judge_model_key=judge_model_key,
    )
    try:
        fixture_sha256 = case.validate_input()
    except BenchmarkInputError as exc:
        invalid_identity = BenchmarkIdentity(
            fixture_sha256=None,
            settings_sha256=settings_sha256,
            embedding_settings_sha256=embedding_settings_sha256,
            judge_settings_sha256=judge_configuration.settings_sha256,
            repository_commit=identity.repository_commit,
            repository_dirty=identity.repository_dirty,
            effective_settings_sha256=effective_settings_sha256,
            harness_variant=normalized_variant,
            invocation_id=normalized_invocation_id,
            case_definition_sha256=_case_definition_sha256(case),
            runtime_sha256=_runtime_sha256(),
        )
        return _persist_result(
            output_directory,
            _invalid_result(
                case_id=case.case_id,
                provider_model=model_key,
                execution_mode=execution_mode,
                identity=invalid_identity,
                failure_kind=exc.code,
                budget_policy=budget_policy,
                invocation_reported_subject_tokens=preserved_invocation_tokens,
            ),
        )

    cell_identity = BenchmarkIdentity(
        fixture_sha256=fixture_sha256,
        settings_sha256=settings_sha256,
        embedding_settings_sha256=embedding_settings_sha256,
        judge_settings_sha256=judge_configuration.settings_sha256,
        repository_commit=identity.repository_commit,
        repository_dirty=identity.repository_dirty,
        effective_settings_sha256=effective_settings_sha256,
        harness_variant=normalized_variant,
        invocation_id=normalized_invocation_id,
        case_definition_sha256=_case_definition_sha256(case),
        runtime_sha256=_runtime_sha256(),
    )
    run_id = uuid4().hex
    if (
        isinstance(invocation_reported_subject_tokens, bool)
        or not isinstance(invocation_reported_subject_tokens, int)
        or invocation_reported_subject_tokens < 0
    ):
        return _persist_result(
            output_directory,
            _invalid_result(
                case_id=case.case_id,
                provider_model=model_key,
                execution_mode=execution_mode,
                identity=cell_identity,
                failure_kind="invalid_invocation_token_state",
                budget_policy=budget_policy,
                run_id=run_id,
            ),
        )
    if (
        invocation_reported_subject_tokens
        >= budget_policy.max_reported_invocation_subject_tokens
    ):
        return _persist_result(
            output_directory,
            AgentHarnessBenchmarkResult(
                case_id=case.case_id,
                run_id=run_id,
                provider_model=model_key,
                execution_mode=execution_mode,
                run_status=BenchmarkRunStatus.BUDGET_EXCEEDED,
                subject_metrics=BenchmarkMetrics(),
                budget=BenchmarkBudgetSnapshot(
                    status=BenchmarkBudgetStatus.EXCEEDED,
                    policy=budget_policy,
                    invocation_reported_subject_tokens=(
                        invocation_reported_subject_tokens
                    ),
                    exhaustion_reason="invocation_token_limit_reached",
                ),
                identity=cell_identity,
                failure_kind="invocation_token_limit_reached",
            ),
        )
    with tempfile.TemporaryDirectory(
        prefix="xenix-agent-benchmark-parent-",
        ignore_cleanup_errors=True,
    ) as temporary_parent:
        outcome = run_isolated_call(
            _run_model_cell,
            {
                "run_id": run_id,
                "case": case,
                "execution_mode": execution_mode,
                "settings": effective_settings,
                "settings_path": resolved_settings_path,
                "settings_sha256": settings_sha256,
                "embedding_settings": embedding_settings,
                "embedding_settings_path": resolved_embedding_settings_path,
                "embedding_settings_sha256": embedding_settings_sha256,
                "model_key": model_key,
                "identity": cell_identity,
                "judge_configuration": judge_configuration,
                "budget_policy": budget_policy,
                "temporary_parent": Path(temporary_parent),
            },
            timeout_seconds=budget_policy.max_wall_seconds,
        )
    if outcome.status is IsolatedCallStatus.COMPLETED and isinstance(
        outcome.value,
        AgentHarnessBenchmarkResult,
    ):
        result = outcome.value
    elif outcome.status is IsolatedCallStatus.TIMED_OUT:
        result = AgentHarnessBenchmarkResult(
            case_id=case.case_id,
            run_id=run_id,
            provider_model=model_key,
            execution_mode=execution_mode,
            run_status=BenchmarkRunStatus.BUDGET_EXCEEDED,
            subject_metrics=BenchmarkMetrics(),
            budget=BenchmarkBudgetSnapshot(
                status=BenchmarkBudgetStatus.EXCEEDED,
                policy=budget_policy,
                exhaustion_reason="process_wall_time_exceeded",
            ),
            identity=cell_identity,
            failure_kind="process_wall_time_exceeded",
        )
    else:
        result = AgentHarnessBenchmarkResult(
            case_id=case.case_id,
            run_id=run_id,
            provider_model=model_key,
            execution_mode=execution_mode,
            run_status=BenchmarkRunStatus.RUNTIME_ERROR,
            subject_metrics=BenchmarkMetrics(),
            budget=BenchmarkBudgetSnapshot(
                status=BenchmarkBudgetStatus.NOT_EVALUATED,
                policy=budget_policy,
            ),
            identity=cell_identity,
            failure_kind=outcome.failure_kind or "child_process_failed",
        )
    invocation_total = (
        invocation_reported_subject_tokens
        + result.budget.reported_subject_tokens
    )
    result_budget = replace(
        result.budget,
        invocation_reported_subject_tokens=invocation_total,
    )
    if (
        result.run_status is BenchmarkRunStatus.COMPLETED
        and invocation_total
        > budget_policy.max_reported_invocation_subject_tokens
    ):
        result_budget = replace(
            result_budget,
            status=BenchmarkBudgetStatus.EXCEEDED,
            exhaustion_reason="invocation_token_limit_exceeded",
        )
        result = replace(
            result,
            run_status=BenchmarkRunStatus.BUDGET_EXCEEDED,
            semantic_verdict=SemanticVerdict.NOT_EVALUATED,
            budget=result_budget,
            failure_kind="invocation_token_limit_exceeded",
        )
    else:
        result = replace(result, budget=result_budget)
    return _persist_result(output_directory, result)


def _run_model_cell(
    *,
    run_id: str,
    case: BenchmarkCase,
    execution_mode: BenchmarkExecutionMode,
    settings: LLMSettings,
    settings_path: Path,
    settings_sha256: str,
    embedding_settings: EmbeddingSettings | None,
    embedding_settings_path: Path | None,
    embedding_settings_sha256: str | None,
    model_key: str,
    identity: BenchmarkIdentity,
    judge_configuration: _JudgeConfiguration,
    budget_policy: BenchmarkBudgetPolicy,
    temporary_parent: Path,
) -> AgentHarnessBenchmarkResult:
    setup_error = _model_setup_error(settings, model_key)
    if setup_error is not None:
        return _invalid_result(
            case_id=case.case_id,
            provider_model=model_key,
            execution_mode=execution_mode,
            identity=identity,
            failure_kind=setup_error,
            run_id=run_id,
            budget_policy=budget_policy,
        )

    budget = BenchmarkBudgetController(budget_policy)
    measurements = _StreamMeasurements()
    subject_metrics = BenchmarkMetrics()
    run_status = BenchmarkRunStatus.COMPLETED
    failure_kind: str | None = None
    assessment: BenchmarkCaseAssessment | None = None
    judge_result = JudgeResult()
    with tempfile.TemporaryDirectory(
        prefix="cell-",
        dir=temporary_parent,
        ignore_cleanup_errors=True,
    ) as temporary_root:
        paths = _benchmark_paths(Path(temporary_root) / "runtime")
        cell: Any | None = None
        case_services: BenchmarkCaseServices | None = None
        thread_id: str | None = None
        turn_seconds = 0.0
        try:
            cell = _open_benchmark_cell(
                execution_mode=execution_mode,
                paths=paths,
                settings=settings,
                embedding_settings=embedding_settings,
                budget=budget,
            )
            case_services = BenchmarkCaseServices(
                datasets=cell.datasets,
                artifacts=cell.artifacts,
            )
            before_dataset_ids = {
                dataset.id for dataset in cell.datasets.list_datasets()
            }
            title = _synthetic_title(case.case_id, model_key, run_id)
            thread_id = cell.create_thread(title=title, fq_model_key=model_key)
            _prepare_case(
                case=case,
                services=cell.preparation_services,
            )
            started_at = time.perf_counter()
            try:
                cell.execute_submission(
                    submission=case.build_submission(
                        thread_id=thread_id,
                        fq_model_key=model_key,
                    ),
                    measurements=measurements,
                    case=case,
                    services=case_services,
                )
            except BenchmarkBudgetError as exc:
                run_status = BenchmarkRunStatus.BUDGET_EXCEEDED
                failure_kind = exc.code
            except Exception as exc:
                run_status = BenchmarkRunStatus.RUNTIME_ERROR
                failure_kind = _exception_kind(exc)
            finally:
                turn_seconds = time.perf_counter() - started_at

            if measurements.title_event_count and run_status is BenchmarkRunStatus.COMPLETED:
                run_status = BenchmarkRunStatus.MEASUREMENT_ERROR
                failure_kind = "unexpected_title_event"

            if measurements.snapshot is None and thread_id is not None:
                try:
                    measurements.snapshot = cell.harness.get_thread_snapshot(thread_id)
                except Exception:
                    pass
            run_dataset_ids = frozenset(
                dataset.id for dataset in cell.datasets.list_datasets()
            ) - before_dataset_ids
            try:
                assessment_started_at = time.perf_counter()
                assessment = case.assess(
                    context=BenchmarkCaseContext(
                        snapshot=measurements.snapshot,
                        source_state=measurements.source_state,
                        run_dataset_ids=run_dataset_ids,
                        runtime_home=paths.home,
                        settings_unchanged=(
                            _sha256_file(settings_path) == settings_sha256
                            and (
                                embedding_settings_path is None
                                or (
                                    embedding_settings_sha256 is not None
                                    and _sha256_file(embedding_settings_path)
                                    == embedding_settings_sha256
                                )
                            )
                        ),
                        services=case_services,
                    )
                )
                assessment_seconds = time.perf_counter() - assessment_started_at
                subject_metrics = _collect_metrics(
                    harness=cell.harness,
                    dataset_service=cell.datasets,
                    snapshot=measurements.snapshot,
                    turn_seconds=turn_seconds,
                    assessment_seconds=assessment_seconds,
                    pending_message_ids=measurements.pending_message_ids,
                    provider_retry_count=measurements.provider_retry_count,
                    terminal_shape=assessment.terminal_shape,
                    budget=budget,
                )
            except Exception as exc:
                if run_status is BenchmarkRunStatus.COMPLETED:
                    run_status = BenchmarkRunStatus.MEASUREMENT_ERROR
                    failure_kind = _exception_kind(exc)
                try:
                    subject_metrics = _collect_metrics(
                        harness=cell.harness,
                        dataset_service=cell.datasets,
                        snapshot=measurements.snapshot,
                        turn_seconds=turn_seconds,
                        assessment_seconds=None,
                        pending_message_ids=measurements.pending_message_ids,
                        provider_retry_count=measurements.provider_retry_count,
                        terminal_shape=None,
                        budget=budget,
                    )
                except Exception:
                    subject_metrics = BenchmarkMetrics(
                        turn_seconds=turn_seconds,
                        sampling_round_count=budget.snapshot().sampling_rounds_admitted,
                        provider_retry_count=measurements.provider_retry_count,
                    )
        except Exception as exc:
            run_status = BenchmarkRunStatus.RUNTIME_ERROR
            failure_kind = _exception_kind(exc)
        finally:
            if cell is not None:
                case_services = None
                try:
                    cell.close()
                except Exception as exc:
                    if run_status is BenchmarkRunStatus.COMPLETED:
                        run_status = BenchmarkRunStatus.RUNTIME_ERROR
                        failure_kind = _exception_kind(exc)
                if assessment is not None:
                    assessment = replace(
                        assessment,
                        integrity_checks=(
                            *assessment.integrity_checks,
                            *cell.integrity_checks(),
                        ),
                    )
        budget_snapshot = budget.snapshot()
        if run_status is BenchmarkRunStatus.COMPLETED:
            if budget_snapshot.status is BenchmarkBudgetStatus.EXCEEDED:
                run_status = BenchmarkRunStatus.BUDGET_EXCEEDED
                failure_kind = budget_snapshot.exhaustion_reason
            elif budget_snapshot.status is BenchmarkBudgetStatus.UNVERIFIABLE:
                run_status = BenchmarkRunStatus.MEASUREMENT_ERROR
                failure_kind = budget_snapshot.exhaustion_reason
            elif not _usage_projection_matches(subject_metrics, budget_snapshot):
                run_status = BenchmarkRunStatus.MEASUREMENT_ERROR
                failure_kind = "subject_usage_projection_mismatch"
        try:
            judge_result = _evaluate_judge(
                assessment=assessment,
                run_status=run_status,
                configuration=judge_configuration,
                subject_model_key=model_key,
            )
        except Exception:
            judge_result = JudgeResult(
                required=bool(assessment and assessment.judge_required),
                status=JudgeStatus.PROVIDER_ERROR,
                provider_model=judge_configuration.model_key,
                independence=judge_independence(
                    judge_model_key=judge_configuration.model_key,
                    subject_model_key=model_key,
                ),
                summary="judge_dispatch_error",
            )

    budget_snapshot = budget.snapshot()
    return AgentHarnessBenchmarkResult(
        case_id=case.case_id,
        run_id=run_id,
        provider_model=model_key,
        execution_mode=execution_mode,
        run_status=run_status,
        subject_metrics=subject_metrics,
        budget=budget_snapshot,
        semantic_verdict=_semantic_verdict(assessment=assessment, run_status=run_status),
        semantic_checks=assessment.semantic_checks if assessment is not None else (),
        integrity_checks=assessment.integrity_checks if assessment is not None else (),
        judge=judge_result,
        identity=identity,
        failure_kind=failure_kind,
    )


def _open_benchmark_cell(
    *,
    execution_mode: BenchmarkExecutionMode,
    paths: AppPaths,
    settings: LLMSettings,
    embedding_settings: EmbeddingSettings | None,
    budget: BenchmarkBudgetController,
) -> Any:
    if execution_mode is BenchmarkExecutionMode.HEADLESS:
        return _HeadlessBenchmarkCell(
            paths=paths,
            settings=settings,
            embedding_settings=embedding_settings,
            budget=budget,
        )
    if execution_mode is BenchmarkExecutionMode.HEADED:
        from .headed import HeadedBenchmarkCell

        return HeadedBenchmarkCell(
            paths=paths,
            settings=settings,
            embedding_settings=embedding_settings,
            bounded_llm=_BoundedLLMService(
                FrozenLLMSettingsSource(settings),
                budget,
            ),
        )
    raise BenchmarkInputError("unsupported_execution_mode")


def _prepare_case(
    *,
    case: BenchmarkCase,
    services: BenchmarkCasePreparationServices,
) -> None:
    prepare = getattr(case, "prepare", None)
    if prepare is None:
        return
    prepare(services=services)


def _collect_metrics(
    *,
    harness: Any,
    dataset_service: Any,
    snapshot: Any | None,
    turn_seconds: float,
    assessment_seconds: float | None,
    pending_message_ids: set[str],
    provider_retry_count: int,
    terminal_shape: tuple[int, int] | None,
    budget: BenchmarkBudgetController,
) -> BenchmarkMetrics:
    messages = list(getattr(snapshot, "messages", [])) if snapshot is not None else []
    message_counts: dict[str, int] = {}
    tool_call_counts: dict[str, int] = {}
    tool_result_counts: dict[str, int] = {}
    for message in messages:
        kind = _enum_value(getattr(message, "kind", None))
        message_counts[kind] = message_counts.get(kind, 0) + 1
        if kind == "tool_call":
            name = str(getattr(message, "tool_id", "") or "unknown")
            tool_call_counts[name] = tool_call_counts.get(name, 0) + 1
        if kind == "tool_result":
            status = _enum_value(getattr(message, "result_status", None)) or "unknown"
            tool_result_counts[status] = tool_result_counts.get(status, 0) + 1
    usage_count, token_usage = _usage_metrics(harness, snapshot)
    return BenchmarkMetrics(
        turn_seconds=turn_seconds,
        assessment_seconds=assessment_seconds,
        sampling_round_count=budget.snapshot().sampling_rounds_admitted,
        usage_reported_primary_response_count=usage_count,
        token_usage=token_usage,
        message_counts=message_counts,
        tool_call_counts_by_name=tool_call_counts,
        tool_result_counts_by_status=tool_result_counts,
        provider_retry_count=provider_retry_count,
        derived_dataset_count=len(dataset_service.list_generated_datasets()),
        terminal_shape=terminal_shape,
    )


def _usage_metrics(harness: Any, snapshot: Any | None) -> tuple[int | None, TokenUsage | None]:
    if snapshot is None:
        return None, None
    total_request_count = 0
    aggregate: TokenUsage | None = None
    for event in harness.project_chatbot_events(snapshot):
        if _enum_value(getattr(event, "kind", None)) != "usage":
            continue
        payload = getattr(event, "usage_payload", None)
        usage = LLMTokenUsage.from_payload(payload)
        if usage is None:
            continue
        request_count = payload.get("request_count") if isinstance(payload, dict) else None
        if not isinstance(request_count, int) or isinstance(request_count, bool) or request_count < 1:
            continue
        total_request_count += request_count
        current = TokenUsage(
            input_tokens=usage.input_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
        )
        aggregate = current if aggregate is None else TokenUsage(
            input_tokens=aggregate.input_tokens + current.input_tokens,
            cached_input_tokens=aggregate.cached_input_tokens + current.cached_input_tokens,
            output_tokens=aggregate.output_tokens + current.output_tokens,
            total_tokens=aggregate.total_tokens + current.total_tokens,
        )
    if aggregate is None:
        return None, None
    return total_request_count, aggregate


def _evaluate_judge(
    *,
    assessment: BenchmarkCaseAssessment | None,
    run_status: BenchmarkRunStatus,
    configuration: _JudgeConfiguration,
    subject_model_key: str,
) -> JudgeResult:
    if assessment is None:
        return JudgeResult(status=JudgeStatus.BLOCKED, summary="subject_assessment_unavailable")
    if not assessment.judge_required:
        return JudgeResult()
    rubric_id, rubric_sha256 = _judge_rubric_identity(assessment)
    if run_status is not BenchmarkRunStatus.COMPLETED:
        return _blocked_judge_result(
            configuration=configuration,
            subject_model_key=subject_model_key,
            summary="subject_run_not_completed",
            rubric_id=rubric_id,
            rubric_sha256=rubric_sha256,
        )
    if not assessment.integrity_passed:
        return _blocked_judge_result(
            configuration=configuration,
            subject_model_key=subject_model_key,
            summary="benchmark_integrity_invalid",
            rubric_id=rubric_id,
            rubric_sha256=rubric_sha256,
        )
    if not assessment.semantic_checks_passed:
        return _blocked_judge_result(
            configuration=configuration,
            subject_model_key=subject_model_key,
            summary="semantic_prerequisite_failed",
            rubric_id=rubric_id,
            rubric_sha256=rubric_sha256,
        )
    if assessment.judge_input is None:
        return _blocked_judge_result(
            configuration=configuration,
            subject_model_key=subject_model_key,
            summary="insufficient_semantic_evidence",
            verdict=SemanticVerdict.INCONCLUSIVE,
            rubric_id=rubric_id,
            rubric_sha256=rubric_sha256,
        )
    if configuration.setup_error is not None:
        return JudgeResult(
            required=True,
            rubric_id=rubric_id,
            rubric_sha256=rubric_sha256,
            status=JudgeStatus.INVALID_SETUP,
            provider_model=configuration.model_key,
            independence=judge_independence(
                judge_model_key=configuration.model_key,
                subject_model_key=subject_model_key,
            ),
            summary=configuration.setup_error,
        )
    if not configuration.enabled:
        return JudgeResult(
            required=True,
            rubric_id=rubric_id,
            rubric_sha256=rubric_sha256,
            status=JudgeStatus.NOT_CONFIGURED,
            provider_model=configuration.model_key,
            independence=judge_independence(
                judge_model_key=configuration.model_key,
                subject_model_key=subject_model_key,
            ),
            summary="judge_not_configured",
        )
    judge_llm = LLMService(FrozenLLMSettingsSource(configuration.settings))
    return replace(
        run_judge(
            llm=judge_llm,
            judge_input=assessment.judge_input,
            judge_model_key=configuration.model_key,
            subject_model_key=subject_model_key,
        ),
        required=True,
        rubric_id=rubric_id,
        rubric_sha256=rubric_sha256,
    )


def _blocked_judge_result(
    *,
    configuration: _JudgeConfiguration,
    subject_model_key: str,
    summary: str,
    verdict: SemanticVerdict = SemanticVerdict.NOT_EVALUATED,
    rubric_id: str | None = None,
    rubric_sha256: str | None = None,
) -> JudgeResult:
    return JudgeResult(
        required=True,
        rubric_id=rubric_id,
        rubric_sha256=rubric_sha256,
        status=JudgeStatus.BLOCKED,
        verdict=verdict,
        provider_model=configuration.model_key,
        independence=judge_independence(
            judge_model_key=configuration.model_key,
            subject_model_key=subject_model_key,
        ),
        summary=summary,
    )


def _judge_rubric_identity(
    assessment: BenchmarkCaseAssessment,
) -> tuple[str | None, str | None]:
    judge_input = assessment.judge_input
    if judge_input is None:
        return None, None
    rubric = judge_input.rubric
    payload = json.dumps(
        {
            "rubric_id": rubric.rubric_id,
            "score_dimensions": list(rubric.score_dimensions),
            "allowed_reason_codes": list(rubric.allowed_reason_codes),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return rubric.rubric_id, _sha256_text(payload)


def _semantic_verdict(
    *,
    assessment: BenchmarkCaseAssessment | None,
    run_status: BenchmarkRunStatus,
) -> SemanticVerdict:
    if run_status is not BenchmarkRunStatus.COMPLETED or assessment is None:
        return SemanticVerdict.NOT_EVALUATED
    if not assessment.integrity_passed:
        return SemanticVerdict.NOT_EVALUATED
    if not assessment.semantic_checks:
        return SemanticVerdict.NOT_EVALUATED
    if not assessment.semantic_checks_passed:
        return SemanticVerdict.FAIL
    return SemanticVerdict.PASS


def _persist_result(
    output_directory: Path,
    result: AgentHarnessBenchmarkResult,
) -> BenchmarkRun:
    try:
        _write_result(output_directory, result)
    except OSError:
        return BenchmarkRun(result=result, persisted=False)
    return BenchmarkRun(result=result, persisted=True)


def _write_result(output_directory: Path, result: AgentHarnessBenchmarkResult) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    file_name = "-".join(
        (
            _safe_file_component(result.case_id),
            _safe_file_component(result.provider_model),
            result.run_id,
        )
    ) + ".json"
    destination = output_directory / file_name
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result.to_payload(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(destination)


def _invalid_result(
    *,
    case_id: str,
    provider_model: str,
    execution_mode: BenchmarkExecutionMode,
    identity: BenchmarkIdentity,
    failure_kind: str,
    budget_policy: BenchmarkBudgetPolicy,
    run_id: str | None = None,
    invocation_reported_subject_tokens: int = 0,
) -> AgentHarnessBenchmarkResult:
    return AgentHarnessBenchmarkResult(
        case_id=case_id,
        run_id=run_id or uuid4().hex,
        provider_model=provider_model,
        execution_mode=execution_mode,
        run_status=BenchmarkRunStatus.INVALID_SETUP,
        subject_metrics=BenchmarkMetrics(),
        budget=BenchmarkBudgetSnapshot(
            status=BenchmarkBudgetStatus.NOT_EVALUATED,
            policy=budget_policy,
            invocation_reported_subject_tokens=invocation_reported_subject_tokens,
        ),
        identity=identity,
        failure_kind=failure_kind,
    )


def _model_setup_error(settings: LLMSettings, model_key: str) -> str | None:
    try:
        provider_key, requested_model = model_key.split("/", 1)
    except ValueError:
        return "invalid_model"
    for provider in settings.providers:
        if provider.key != provider_key:
            continue
        if requested_model not in provider.models:
            return "invalid_model"
        if not provider.api_key.strip() and not provider.dialect_config.get("secret_source"):
            return "missing_credentials"
        return None
    return "invalid_model"


def _effective_subject_settings(
    settings: LLMSettings,
    policy: BenchmarkBudgetPolicy,
) -> LLMSettings:
    return settings.model_copy(
        deep=True,
        update={
            "retry_attempts": policy.max_provider_attempts,
            "thread_title_fq_model_key": "",
            "turn_completion_guard_fq_model_key": "",
        },
    )


def _normalized_harness_variant(value: object) -> str:
    variant = value.strip() if isinstance(value, str) else ""
    if (
        not variant
        or len(variant) > 96
        or any(not (character.isalnum() or character in {"-", "_", "."}) for character in variant)
    ):
        raise BenchmarkSettingsError("invalid_harness_variant")
    return variant


def _normalized_invocation_id(value: object) -> str:
    invocation_id = value.strip() if isinstance(value, str) else ""
    if not invocation_id:
        return uuid4().hex
    if (
        len(invocation_id) > 96
        or any(
            not (character.isalnum() or character in {"-", "_", "."})
            for character in invocation_id
        )
    ):
        raise BenchmarkSettingsError("invalid_invocation_id")
    return invocation_id


def _case_definition_sha256(case: BenchmarkCase) -> str | None:
    try:
        source = inspect.getsourcefile(type(case))
        path = Path(source) if source is not None else None
        return _sha256_file(path) if path is not None and path.is_file() else None
    except (OSError, TypeError):
        return None


def _project_root() -> Path:
    """Resolve the repository root by locating ``pyproject.toml``."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("project_root_not_found")


def _runtime_sha256() -> str:
    project_root = _project_root()
    lock_path = project_root / "pdm.lock"
    lock_sha = _sha256_file(lock_path) if lock_path.is_file() else "unavailable"
    infrastructure_root = Path(__file__).resolve().parent
    benchmark_runtime_files = (
        "budgets.py",
        "case_support.py",
        "contracts.py",
        "headed.py",
        "judge.py",
        "pytest_plugin.py",
        "runner.py",
    )
    components = [sys.version, sys.platform, platform.machine(), lock_sha]
    components.extend(
        f"{name}:{_sha256_file(infrastructure_root / name)}"
        for name in benchmark_runtime_files
    )
    return _sha256_text("|".join(components))


def _usage_projection_matches(
    metrics: BenchmarkMetrics,
    budget: BenchmarkBudgetSnapshot,
) -> bool:
    usage = metrics.token_usage
    if usage is None:
        return False
    return usage.total_tokens == budget.reported_subject_tokens


def _benchmark_paths(home: Path) -> AppPaths:
    return ensure_app_dirs(
        AppPaths(
            home=home,
            config=home / "config",
            logs=home / "logs",
            cache=home / "cache",
            state=home / "state",
            temp=home / "temp",
            artifacts=home / "artifacts",
            resources=package_root() / "resources",
        )
    )


def _synthetic_title(case_id: str, model_key: str, run_id: str) -> str:
    tested_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"benchmark {case_id} {model_key} {tested_at} {run_id[:8]}"[:180]


def _repository_identity() -> BenchmarkIdentity:
    project_root = _project_root()
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return BenchmarkIdentity()
    return BenchmarkIdentity(
        repository_commit=commit.stdout.strip() if commit.returncode == 0 else None,
        repository_dirty=bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
    )


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest().upper()


def _safe_file_component(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in {"-", "_", "."} else "-" for character in value)
    return safe.strip(".-")[:96] or "unknown"


def _exception_kind(exc: BaseException) -> str:
    for attribute in ("code", "error_code"):
        code = getattr(exc, attribute, None)
        if isinstance(code, str) and code.strip():
            return code.strip()[:80]
    name = exc.__class__.__name__
    return name[:80] if name else "runtime_failure"


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")
