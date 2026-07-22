from __future__ import annotations

import json
import os
import queue
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from multiprocessing import get_context
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from ..config import AppPaths
from ..exceptions import ValidationError
from .knowledge_canonical import CanonicalIdentity, Canonicalizer
from .knowledge_content_store import KnowledgeContentStore
from .knowledge_pipeline import FileProbe, FormatNormalizer, ParseExecutor, ParserRouter
from .paddle_ocr_service import PaddleOcrDeploymentService, PaddleOcrService
from .storage.layout import knowledge_import_result_path, knowledge_import_task_root

_RESULT_SCHEMA_VERSION = 1
_MAX_RESULT_BYTES = 256 * 1024
_TASK_ID = re.compile(r"[0-9a-f]{32}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_EVENT_TOKEN = re.compile(r"[a-z0-9_.-]{1,80}\Z")
_SUCCESS_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "worker_pid",
        "canonical_generation_id",
        "media_type",
        "envelope_sha256",
        "content_ir_sha256",
        "relative_path",
        "pipeline",
        "warnings",
        "error_code",
        "retryable",
    }
)


@dataclass(frozen=True)
class KnowledgeImportWorkerRequest:
    paths: AppPaths
    import_id: str
    source_path: str
    expected_source_sha256: str
    expected_source_format: str
    expected_media_type: str | None
    identity: CanonicalIdentity
    password: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class KnowledgeImportWorkerEvent:
    phase: str
    event_code: str
    level: str = "info"


@dataclass(frozen=True)
class KnowledgeImportWorkerResult:
    status: str
    worker_pid: int
    canonical_generation_id: str | None = None
    media_type: str | None = None
    envelope_sha256: str | None = None
    content_ir_sha256: str | None = None
    relative_path: str | None = None
    pipeline: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    error_code: str | None = None
    retryable: bool = False


class KnowledgeImportWorkerRunner(Protocol):
    def run(
        self,
        request: KnowledgeImportWorkerRequest,
        *,
        is_cancelled: Callable[[], bool],
        on_event: Callable[[KnowledgeImportWorkerEvent], None],
    ) -> KnowledgeImportWorkerResult: ...


class LocalKnowledgeImportWorkerRunner:
    """Run one import attempt in a spawn-safe child process."""

    def __init__(
        self,
        *,
        poll_interval: float = 0.05,
        cancel_grace: float = 1.0,
        entrypoint: Callable[..., None] | None = None,
    ) -> None:
        self._poll_interval = max(0.01, poll_interval)
        self._cancel_grace = max(0.1, cancel_grace)
        self._entrypoint = entrypoint or knowledge_import_worker_entry

    def run(
        self,
        request: KnowledgeImportWorkerRequest,
        *,
        is_cancelled: Callable[[], bool],
        on_event: Callable[[KnowledgeImportWorkerEvent], None],
    ) -> KnowledgeImportWorkerResult:
        _validate_request(request)
        result_path = knowledge_import_result_path(request.paths, request.import_id)
        task_root = knowledge_import_task_root(request.paths, request.import_id)
        task_root.mkdir(parents=True, exist_ok=True)
        result_path.unlink(missing_ok=True)
        context = get_context("spawn")
        cancel_event = context.Event()
        event_queue = context.Queue()
        process = context.Process(
            target=self._entrypoint,
            args=(request, cancel_event, event_queue),
            name=f"xenix-knowledge-import-{request.import_id[:8]}",
        )
        cancellation_started: float | None = None
        process.start()
        try:
            while process.is_alive():
                _drain_events(event_queue, on_event)
                if is_cancelled():
                    cancel_event.set()
                    if cancellation_started is None:
                        cancellation_started = time.monotonic()
                    elif time.monotonic() - cancellation_started >= self._cancel_grace:
                        process.terminate()
                process.join(self._poll_interval)
            _drain_events(event_queue, on_event)
            if cancellation_started is not None or is_cancelled():
                raise KnowledgeImportWorkerCancelled
            if process.exitcode != 0:
                raise KnowledgeImportWorkerCrashed
            return read_worker_result(result_path)
        finally:
            if process.is_alive():
                process.terminate()
                process.join(self._cancel_grace)
            if process.is_alive():
                process.kill()
                process.join()
            event_queue.close()
            event_queue.join_thread()


class InlineKnowledgeImportWorkerRunner:
    """Deterministic test seam with the same result and event contract."""

    def __init__(
        self,
        paths: AppPaths,
        *,
        normalizer: FormatNormalizer | None = None,
        ocr_service: object | None = None,
        store: KnowledgeContentStore | None = None,
    ) -> None:
        self._paths = paths
        self._normalizer = normalizer or FormatNormalizer()
        self._parser = ParseExecutor(ocr_service)  # type: ignore[arg-type]
        self._store = store or KnowledgeContentStore(paths)

    def run(
        self,
        request: KnowledgeImportWorkerRequest,
        *,
        is_cancelled: Callable[[], bool],
        on_event: Callable[[KnowledgeImportWorkerEvent], None],
    ) -> KnowledgeImportWorkerResult:
        _validate_request(request)
        if request.paths != self._paths:
            raise ValueError("Inline Knowledge worker paths do not match the request.")
        result_path = knowledge_import_result_path(request.paths, request.import_id)
        knowledge_import_task_root(request.paths, request.import_id).mkdir(
            parents=True, exist_ok=True
        )
        result_path.unlink(missing_ok=True)
        _run_worker_operation(
            request,
            is_cancelled=is_cancelled,
            on_event=on_event,
            normalizer=self._normalizer,
            parser=self._parser,
            store=self._store,
        )
        if is_cancelled():
            raise KnowledgeImportWorkerCancelled
        return read_worker_result(result_path)


class KnowledgeImportWorkerCancelled(Exception):
    pass


class KnowledgeImportWorkerCrashed(Exception):
    pass


def knowledge_import_worker_entry(request, cancel_event, event_queue) -> None:
    """Top-level entrypoint required by Windows spawn and frozen executables."""

    def is_cancelled() -> bool:
        return bool(cancel_event.is_set())

    def on_event(event: KnowledgeImportWorkerEvent) -> None:
        try:
            event_queue.put_nowait(event)
        except Exception:
            pass

    _run_worker_operation(request, is_cancelled=is_cancelled, on_event=on_event)


def _run_worker_operation(
    request: KnowledgeImportWorkerRequest,
    *,
    is_cancelled: Callable[[], bool],
    on_event: Callable[[KnowledgeImportWorkerEvent], None],
    normalizer: FormatNormalizer | None = None,
    parser: ParseExecutor | None = None,
    store: KnowledgeContentStore | None = None,
) -> None:
    result_path = knowledge_import_result_path(request.paths, request.import_id)
    try:
        _validate_request(request)
        actual_store = store or KnowledgeContentStore(request.paths)
        actual_normalizer = normalizer or FormatNormalizer()
        actual_parser = parser or ParseExecutor(
            PaddleOcrService(PaddleOcrDeploymentService(request.paths))
        )
        router = ParserRouter()
        canonicalizer = Canonicalizer()
        _emit(on_event, "probing", "worker_started")
        _raise_if_cancelled(is_cancelled)
        source = actual_store.verify_source_snapshot(
            Path(request.source_path),
            expected_sha256=request.expected_source_sha256,
        )
        probe = FileProbe().probe(source.path)
        if (
            probe.source_format != request.expected_source_format
            or probe.media_type != request.expected_media_type
        ):
            raise ValidationError(
                "Knowledge source identity changed before parsing.",
                error_code="knowledge_source_integrity_failed",
            )
        with TemporaryDirectory(prefix="xenix-knowledge-import-") as temp:
            work_dir = Path(temp)
            check_cancelled = lambda: _raise_if_cancelled(is_cancelled)
            _emit(on_event, "normalizing", "normalization_started")
            normalized = actual_normalizer.normalize(
                probe,
                work_dir=work_dir,
                password=request.password,
                check_cancelled=check_cancelled,
            )
            _emit(on_event, "routing", "routing_started")
            plan = router.route(normalized, ocr_ready=actual_parser.ocr_ready)
            _emit(on_event, "parsing", "parsing_started")
            parsed = actual_parser.parse(
                normalized,
                plan,
                probe=probe,
                work_dir=work_dir,
                check_cancelled=check_cancelled,
            )
            _raise_if_cancelled(is_cancelled)
            material = canonicalizer.freeze(
                parsed.document,
                identity=request.identity,
                pipeline=parsed.pipeline,
                warnings=parsed.warnings,
                projections=parsed.projections,
            )
            _emit(on_event, "publishing_canonical", "canonical_write_started")
            stored = actual_store.write_canonical_bundle(
                envelope=material.envelope,
                docling_document=material.docling_document,
                assets=material.assets,
            )
        _raise_if_cancelled(is_cancelled)
        result = KnowledgeImportWorkerResult(
            status="succeeded",
            worker_pid=os.getpid(),
            canonical_generation_id=request.identity.canonical_generation_id,
            media_type=probe.media_type,
            envelope_sha256=stored.envelope_sha256,
            content_ir_sha256=stored.content_ir_sha256,
            relative_path=stored.relative_path,
            pipeline=dict(parsed.pipeline),
            warnings=tuple(str(item) for item in parsed.warnings),
        )
        write_worker_result(result_path, result)
        _emit(on_event, "completed", "worker_succeeded")
    except _WorkerCancelled:
        write_worker_result(
            result_path,
            KnowledgeImportWorkerResult(
                status="cancelled",
                worker_pid=os.getpid(),
                error_code="knowledge_import_cancelled",
                retryable=True,
            ),
        )
        _emit(on_event, "cancelled", "worker_cancelled", level="warning")
    except Exception as exc:
        error_code = getattr(exc, "error_code", None)
        if not isinstance(error_code, str) or not error_code.startswith("knowledge_"):
            error_code = "knowledge_import_failed"
        retryable = bool(getattr(exc, "retryable", False))
        write_worker_result(
            result_path,
            KnowledgeImportWorkerResult(
                status="failed",
                worker_pid=os.getpid(),
                error_code=error_code,
                retryable=retryable,
            ),
        )
        _emit(on_event, "failed", "worker_failed", level="error")


def write_worker_result(path: Path, result: KnowledgeImportWorkerResult) -> None:
    payload = asdict(result)
    payload["schema_version"] = _RESULT_SCHEMA_VERSION
    payload["warnings"] = list(result.warnings)
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if not encoded or len(encoded) > _MAX_RESULT_BYTES:
        raise ValidationError("Knowledge import worker result is too large.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.part")
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_worker_result(path: Path) -> KnowledgeImportWorkerResult:
    try:
        size = path.stat().st_size
        if size < 1 or size > _MAX_RESULT_BYTES:
            raise ValueError("result size")
        payload = json.loads(path.read_bytes())
        if not isinstance(payload, dict) or set(payload) != _SUCCESS_KEYS:
            raise ValueError("result shape")
        if payload.get("schema_version") != _RESULT_SCHEMA_VERSION:
            raise ValueError("result version")
        status = payload.get("status")
        worker_pid = payload.get("worker_pid")
        if status not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("result status")
        if type(worker_pid) is not int or worker_pid < 1:
            raise ValueError("worker pid")
        warnings = payload.get("warnings")
        pipeline = payload.get("pipeline")
        if not isinstance(warnings, list) or not all(
            isinstance(item, str) and len(item) <= 200 for item in warnings
        ):
            raise ValueError("result warnings")
        if not isinstance(pipeline, dict):
            raise ValueError("result pipeline")
        result = KnowledgeImportWorkerResult(
            status=status,
            worker_pid=worker_pid,
            canonical_generation_id=_optional_string(payload, "canonical_generation_id"),
            media_type=_optional_string(payload, "media_type"),
            envelope_sha256=_optional_string(payload, "envelope_sha256"),
            content_ir_sha256=_optional_string(payload, "content_ir_sha256"),
            relative_path=_optional_string(payload, "relative_path"),
            pipeline=pipeline,
            warnings=tuple(warnings),
            error_code=_optional_string(payload, "error_code"),
            retryable=payload.get("retryable") is True,
        )
        _validate_result(result)
        return result
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise KnowledgeImportWorkerCrashed from exc


def _validate_request(request: KnowledgeImportWorkerRequest) -> None:
    if _TASK_ID.fullmatch(request.import_id) is None:
        raise ValueError("Knowledge import worker task identity is invalid.")
    if request.identity.import_id != request.import_id:
        raise ValueError("Knowledge import worker identity is inconsistent.")
    if _SHA256.fullmatch(request.expected_source_sha256) is None:
        raise ValueError("Knowledge import worker source identity is invalid.")
    if request.identity.source_sha256 != request.expected_source_sha256:
        raise ValueError("Knowledge import worker source identity is inconsistent.")


def _validate_result(result: KnowledgeImportWorkerResult) -> None:
    if result.status == "succeeded":
        if (
            not result.canonical_generation_id
            or _TASK_ID.fullmatch(result.canonical_generation_id) is None
            or not result.relative_path
            or not result.envelope_sha256
            or _SHA256.fullmatch(result.envelope_sha256) is None
            or not result.content_ir_sha256
            or _SHA256.fullmatch(result.content_ir_sha256) is None
            or result.error_code is not None
        ):
            raise ValueError("Knowledge import worker success result is invalid.")
    elif (
        not result.error_code
        or _EVENT_TOKEN.fullmatch(result.error_code) is None
        or any(
            value is not None
            for value in (
                result.canonical_generation_id,
                result.envelope_sha256,
                result.content_ir_sha256,
                result.relative_path,
            )
        )
    ):
        raise ValueError("Knowledge import worker failure result is invalid.")


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"result {key}")
    return value


def _drain_events(event_queue, callback: Callable[[KnowledgeImportWorkerEvent], None]) -> None:
    while True:
        try:
            event = event_queue.get_nowait()
        except queue.Empty:
            return
        if isinstance(event, KnowledgeImportWorkerEvent):
            callback(event)


def _emit(
    callback: Callable[[KnowledgeImportWorkerEvent], None],
    phase: str,
    event_code: str,
    *,
    level: str = "info",
) -> None:
    callback(KnowledgeImportWorkerEvent(phase=phase, event_code=event_code, level=level))


def _raise_if_cancelled(check: Callable[[], bool]) -> None:
    if check():
        raise _WorkerCancelled


class _WorkerCancelled(Exception):
    pass


__all__ = [
    "InlineKnowledgeImportWorkerRunner",
    "KnowledgeImportWorkerCancelled",
    "KnowledgeImportWorkerCrashed",
    "KnowledgeImportWorkerEvent",
    "KnowledgeImportWorkerRequest",
    "KnowledgeImportWorkerResult",
    "KnowledgeImportWorkerRunner",
    "LocalKnowledgeImportWorkerRunner",
    "knowledge_import_worker_entry",
    "read_worker_result",
]
