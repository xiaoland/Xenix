"""Sequential, isolated real-LLM benchmark runner for AgentHarnessService."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Iterable
from uuid import uuid4

from xenix.config import AppPaths, ensure_app_dirs, package_root
from xenix.observability import LLMTokenUsage, LLM_USAGE_JOURNAL_FILE_NAME, LocalLLMUsageObservability
from xenix.services.agent.composition import build_headless_agent_services
from xenix.services.llm import FrozenLLMSettingsSource, LLMService, LLMSettings
from xenix.services.ml.worker_settings import MLWorkerSettingsService
from xenix.services.storage import StorageBootstrapService

from .contracts import (
    AgentHarnessBenchmarkResult,
    BenchmarkCase,
    BenchmarkCaseAssessment,
    BenchmarkCaseContext,
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
from .judge import judge_independence, run_judge


LLM_SETTINGS_PATH_ENV = "XENIX_AGENT_BENCHMARK_LLM_SETTINGS_PATH"
JUDGE_LLM_SETTINGS_PATH_ENV = "XENIX_AGENT_BENCHMARK_JUDGE_LLM_SETTINGS_PATH"
DEFAULT_OUTPUT_DIRECTORY = Path("build") / "agent-harness-benchmarks"


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
            if not self.source_state_captured:
                self.source_state = case.capture_source_state(
                    snapshot=snapshot,
                    services=services,
                )
                self.source_state_captured = True


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


def load_settings_snapshot(path: Path) -> tuple[LLMSettings, str]:
    if not path.is_file():
        raise BenchmarkSettingsError("missing_llm_settings")
    try:
        raw = path.read_text(encoding="utf-8")
        settings = LLMSettings.model_validate_json(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise BenchmarkSettingsError("invalid_llm_settings") from None
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
    return _JudgeConfiguration(
        settings=settings,
        settings_sha256=settings_sha256,
        model_key=selected_model,
    )


def configured_model_keys(settings: LLMSettings) -> tuple[str, ...]:
    return tuple(
        f"{provider.key}/{model_key}"
        for provider in settings.providers
        for model_key in provider.models
    )


def filtered_model_keys(
    settings: LLMSettings,
    requested_models: Iterable[str] | None = None,
) -> tuple[str, ...]:
    configured = configured_model_keys(settings)
    requested = tuple(
        dict.fromkeys(
            model.strip()
            for model in (requested_models or ())
            if isinstance(model, str) and model.strip()
        )
    )
    if not requested:
        return configured
    return requested


def dry_run_models(
    *,
    settings_path: Path | None = None,
    requested_models: Iterable[str] | None = None,
) -> tuple[str, ...]:
    resolved_path = resolve_llm_settings_path(settings_path)
    settings, _settings_sha256 = load_settings_snapshot(resolved_path)
    return filtered_model_keys(settings, requested_models)


def run_benchmark(
    *,
    settings_path: Path | None,
    case: BenchmarkCase,
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY,
    requested_models: Iterable[str] | None = None,
    judge_settings_path: Path | None = None,
    judge_model_key: str | None = None,
) -> tuple[BenchmarkRun, ...]:
    identity = _repository_identity()
    try:
        resolved_settings_path = resolve_llm_settings_path(settings_path)
        settings, settings_sha256 = load_settings_snapshot(resolved_settings_path)
        identity = BenchmarkIdentity(
            fixture_sha256=None,
            settings_sha256=settings_sha256,
            repository_commit=identity.repository_commit,
            repository_dirty=identity.repository_dirty,
        )
    except BenchmarkSettingsError as exc:
        return _persist_all(
            output_directory,
            (
                _invalid_result(
                    case_id=case.case_id,
                    provider_model="unresolved",
                    identity=identity,
                    failure_kind=exc.code,
                ),
            ),
        )

    model_keys = filtered_model_keys(settings, requested_models)
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
            judge_settings_sha256=judge_configuration.settings_sha256,
            repository_commit=identity.repository_commit,
            repository_dirty=identity.repository_dirty,
        )
        return _persist_all(
            output_directory,
            tuple(
                _invalid_result(
                    case_id=case.case_id,
                    provider_model=model_key,
                    identity=invalid_identity,
                    failure_kind=exc.code,
                )
                for model_key in model_keys
            ),
        )

    cell_identity = BenchmarkIdentity(
        fixture_sha256=fixture_sha256,
        settings_sha256=settings_sha256,
        judge_settings_sha256=judge_configuration.settings_sha256,
        repository_commit=identity.repository_commit,
        repository_dirty=identity.repository_dirty,
    )
    return _persist_all(
        output_directory,
        tuple(
            _run_model_cell(
                case=case,
                settings=settings,
                settings_path=resolved_settings_path,
                settings_sha256=settings_sha256,
                model_key=model_key,
                identity=cell_identity,
                judge_configuration=judge_configuration,
            )
            for model_key in model_keys
        ),
    )


def _run_model_cell(
    *,
    case: BenchmarkCase,
    settings: LLMSettings,
    settings_path: Path,
    settings_sha256: str,
    model_key: str,
    identity: BenchmarkIdentity,
    judge_configuration: _JudgeConfiguration,
) -> AgentHarnessBenchmarkResult:
    run_id = uuid4().hex
    setup_error = _model_setup_error(settings, model_key)
    if setup_error is not None:
        return _invalid_result(
            case_id=case.case_id,
            provider_model=model_key,
            identity=identity,
            failure_kind=setup_error,
            run_id=run_id,
        )

    measurements = _StreamMeasurements()
    subject_metrics = BenchmarkMetrics()
    run_status = BenchmarkRunStatus.COMPLETED
    failure_kind: str | None = None
    assessment = None
    judge_result = JudgeResult()
    with tempfile.TemporaryDirectory(prefix="xenix-agent-benchmark-") as temporary_root:
        root = Path(temporary_root)
        paths = _benchmark_paths(root / "runtime")
        storage = None
        services = None
        thread_id: str | None = None
        try:
            storage = StorageBootstrapService().initialize(paths)
            llm = LLMService(FrozenLLMSettingsSource(settings))
            worker_settings = MLWorkerSettingsService(paths)
            services = build_headless_agent_services(
                paths=paths,
                session_factory=storage.session_factory,
                llm=llm,
                ml_worker_settings=worker_settings,
                usage_observability=LocalLLMUsageObservability(
                    paths.logs / LLM_USAGE_JOURNAL_FILE_NAME
                ),
            )
            case_services = BenchmarkCaseServices(
                datasets=services.datasets,
                artifacts=services.artifacts,
            )
            before_dataset_ids = {dataset.id for dataset in services.datasets.list_datasets()}
            title = _synthetic_title(case.case_id, model_key, run_id)
            thread = services.harness.create_thread(title=title, fq_model_key=model_key)
            thread_id = thread.thread.id
            started_at = time.perf_counter()
            try:
                for event in services.harness.submit_user_turn_stream(
                    case.build_submission(thread_id=thread_id, fq_model_key=model_key)
                ):
                    measurements.observe(
                        event,
                        case=case,
                        services=case_services,
                    )
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
                    measurements.snapshot = services.harness.get_thread_snapshot(thread_id)
                except Exception:
                    pass
            run_dataset_ids = frozenset(
                dataset.id for dataset in services.datasets.list_datasets()
            ) - before_dataset_ids
            try:
                assessment_started_at = time.perf_counter()
                assessment = case.assess(
                    context=BenchmarkCaseContext(
                        snapshot=measurements.snapshot,
                        source_state=measurements.source_state,
                        run_dataset_ids=run_dataset_ids,
                        runtime_home=paths.home,
                        settings_unchanged=_sha256_file(settings_path) == settings_sha256,
                        services=case_services,
                    )
                )
                assessment_seconds = time.perf_counter() - assessment_started_at
                subject_metrics = _collect_metrics(
                    harness=services.harness,
                    dataset_service=services.datasets,
                    snapshot=measurements.snapshot,
                    turn_seconds=turn_seconds,
                    assessment_seconds=assessment_seconds,
                    pending_message_ids=measurements.pending_message_ids,
                    provider_retry_count=measurements.provider_retry_count,
                    terminal_shape=assessment.terminal_shape,
                )
            except Exception as exc:
                if run_status is BenchmarkRunStatus.COMPLETED:
                    run_status = BenchmarkRunStatus.MEASUREMENT_ERROR
                    failure_kind = _exception_kind(exc)
                try:
                    subject_metrics = _collect_metrics(
                        harness=services.harness,
                        dataset_service=services.datasets,
                        snapshot=measurements.snapshot,
                        turn_seconds=turn_seconds,
                        assessment_seconds=None,
                        pending_message_ids=measurements.pending_message_ids,
                        provider_retry_count=measurements.provider_retry_count,
                        terminal_shape=None,
                    )
                except Exception:
                    subject_metrics = BenchmarkMetrics(
                        turn_seconds=turn_seconds,
                        sampling_round_count=len(measurements.pending_message_ids),
                        provider_retry_count=measurements.provider_retry_count,
                    )
            try:
                judge_result = _evaluate_judge(
                    assessment=assessment,
                    run_status=run_status,
                    configuration=judge_configuration,
                    subject_model_key=model_key,
                )
            except Exception:
                judge_result = JudgeResult(
                    status=JudgeStatus.PROVIDER_ERROR,
                    provider_model=judge_configuration.model_key,
                    independence=judge_independence(
                        judge_model_key=judge_configuration.model_key,
                        subject_model_key=model_key,
                    ),
                    summary="judge_dispatch_error",
                )
        except Exception as exc:
            run_status = BenchmarkRunStatus.RUNTIME_ERROR
            failure_kind = _exception_kind(exc)
        finally:
            if storage is not None:
                storage.engine.dispose()

    return AgentHarnessBenchmarkResult(
        case_id=case.case_id,
        run_id=run_id,
        provider_model=model_key,
        run_status=run_status,
        subject_metrics=subject_metrics,
        semantic_verdict=_semantic_verdict(assessment=assessment, run_status=run_status, judge_result=judge_result),
        semantic_checks=assessment.semantic_checks if assessment is not None else (),
        integrity_checks=assessment.integrity_checks if assessment is not None else (),
        judge=judge_result,
        identity=identity,
        failure_kind=failure_kind,
    )


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
        sampling_round_count=len(pending_message_ids),
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
    if run_status is not BenchmarkRunStatus.COMPLETED:
        return _blocked_judge_result(
            configuration=configuration,
            subject_model_key=subject_model_key,
            summary="subject_run_not_completed",
        )
    if not assessment.integrity_passed:
        return _blocked_judge_result(
            configuration=configuration,
            subject_model_key=subject_model_key,
            summary="benchmark_integrity_invalid",
        )
    if not assessment.semantic_checks_passed:
        return _blocked_judge_result(
            configuration=configuration,
            subject_model_key=subject_model_key,
            summary="semantic_prerequisite_failed",
        )
    if assessment.judge_input is None:
        return _blocked_judge_result(
            configuration=configuration,
            subject_model_key=subject_model_key,
            summary="insufficient_semantic_evidence",
            verdict=SemanticVerdict.INCONCLUSIVE,
        )
    if configuration.setup_error is not None:
        return JudgeResult(
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
            status=JudgeStatus.NOT_CONFIGURED,
            provider_model=configuration.model_key,
            independence=judge_independence(
                judge_model_key=configuration.model_key,
                subject_model_key=subject_model_key,
            ),
            summary="judge_not_configured",
        )
    judge_llm = LLMService(FrozenLLMSettingsSource(configuration.settings))
    return run_judge(
        llm=judge_llm,
        judge_input=assessment.judge_input,
        judge_model_key=configuration.model_key,
        subject_model_key=subject_model_key,
    )


def _blocked_judge_result(
    *,
    configuration: _JudgeConfiguration,
    subject_model_key: str,
    summary: str,
    verdict: SemanticVerdict = SemanticVerdict.NOT_EVALUATED,
) -> JudgeResult:
    return JudgeResult(
        status=JudgeStatus.BLOCKED,
        verdict=verdict,
        provider_model=configuration.model_key,
        independence=judge_independence(
            judge_model_key=configuration.model_key,
            subject_model_key=subject_model_key,
        ),
        summary=summary,
    )


def _semantic_verdict(
    *,
    assessment: BenchmarkCaseAssessment | None,
    run_status: BenchmarkRunStatus,
    judge_result: JudgeResult,
) -> SemanticVerdict:
    if run_status is not BenchmarkRunStatus.COMPLETED or assessment is None:
        return SemanticVerdict.NOT_EVALUATED
    if not assessment.integrity_passed:
        return SemanticVerdict.NOT_EVALUATED
    if not assessment.semantic_checks:
        return SemanticVerdict.NOT_EVALUATED
    if not assessment.semantic_checks_passed:
        return SemanticVerdict.FAIL
    if assessment.judge_required:
        return judge_result.verdict
    return SemanticVerdict.PASS


def _persist_all(output_directory: Path, results: Iterable[AgentHarnessBenchmarkResult]) -> tuple[BenchmarkRun, ...]:
    runs: list[BenchmarkRun] = []
    for result in results:
        try:
            _write_result(output_directory, result)
        except OSError:
            runs.append(BenchmarkRun(result=result, persisted=False))
        else:
            runs.append(BenchmarkRun(result=result, persisted=True))
    return tuple(runs)


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
    identity: BenchmarkIdentity,
    failure_kind: str,
    run_id: str | None = None,
) -> AgentHarnessBenchmarkResult:
    return AgentHarnessBenchmarkResult(
        case_id=case_id,
        run_id=run_id or uuid4().hex,
        provider_model=provider_model,
        run_status=BenchmarkRunStatus.INVALID_SETUP,
        subject_metrics=BenchmarkMetrics(),
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
    project_root = Path(__file__).resolve().parents[3]
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
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


def _safe_file_component(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in {"-", "_", "."} else "-" for character in value)
    return safe.strip(".-")[:96] or "unknown"


def _exception_kind(exc: BaseException) -> str:
    name = exc.__class__.__name__
    return name[:80] if name else "runtime_failure"


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")
