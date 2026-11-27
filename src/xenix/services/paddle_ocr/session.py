from __future__ import annotations

import json
import os
import queue
import struct
import subprocess
import threading
import time
from contextlib import AbstractContextManager
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from ...exceptions import ValidationError, report_exception
from .contracts import (
    MAX_PROTOCOL_MESSAGE_BYTES,
    NATIVE_OCR_PROTOCOL_VERSION,
    PROCESS_TERMINATE_GRACE_SECONDS,
    PROTOCOL_POLL_INTERVAL_SECONDS,
    PaddleOcrRuntime,
    PaddleOcrRuntimeDescriptor,
    PaddleOcrState,
    bounded_json_object,
)

if TYPE_CHECKING:
    from .deployment import PaddleOcrDeploymentService


class PaddleOcrSession(AbstractContextManager["PaddleOcrSession"]):
    """One bounded stdio session owning one native model initialization."""

    def __init__(
        self,
        runtime: PaddleOcrRuntime,
        *,
        allowed_root: Path,
        log_path: Path,
    ) -> None:
        self._runtime = runtime
        self._allowed_root = allowed_root.resolve()
        self._log_path = log_path
        self._process: subprocess.Popen[bytes] | None = None
        self._stderr = None
        self._request_lock = threading.Lock()

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def runtime_descriptor(self) -> PaddleOcrRuntimeDescriptor:
        return self._runtime.descriptor

    def __enter__(self) -> PaddleOcrSession:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._stderr = self._log_path.open("ab", buffering=0)
        try:
            self._process = subprocess.Popen(
                [str(self._runtime.executable_path), "--stdio"],
                cwd=self._runtime.generation_path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._stderr,
                creationflags=_no_console_creationflags(),
            )
            version = self.request("version", {}, timeout=10)
            if (
                not isinstance(version, dict)
                or version.get("protocol_version") != NATIVE_OCR_PROTOCOL_VERSION
                or version.get("runtime_id") != self._runtime.runtime_id
            ):
                raise ValidationError(
                    "Local OCR worker is incompatible.",
                    error_code="knowledge_ocr_worker_incompatible",
                )
            initialized = self.request(
                "initialize",
                {
                    "model_pack_id": self._runtime.model_pack_id,
                    "detection_model_path": str(self._runtime.detection_model_path),
                    "recognition_model_path": str(self._runtime.recognition_model_path),
                },
                timeout=120,
            )
            if not isinstance(initialized, dict) or initialized.get("initialized") is not True:
                raise ValidationError(
                    "Local OCR models could not be initialized.",
                    error_code="knowledge_ocr_initialize_failed",
                )
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc_type is None and self._process is not None and self._process.poll() is None:
            try:
                self.request("shutdown", {}, timeout=5)
            except Exception as exc:
                report_exception(exc)
        self.close()
        return False

    def recognize(
        self,
        image_path: Path,
        *,
        output_path: Path | None = None,
        timeout: int = 300,
    ) -> dict[str, object]:
        image = image_path.resolve()
        try:
            image.relative_to(self._allowed_root)
        except ValueError as exc:
            raise ValidationError(
                "Local OCR input is outside the import staging area.",
                error_code="knowledge_ocr_input_outside_staging",
            ) from exc
        result = self.request(
            "recognize",
            {"image_path": str(image)},
            timeout=timeout,
        )
        payload = _normalized_ocr_result(result)
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
        return payload

    def request(
        self,
        operation: str,
        arguments: dict[str, object],
        *,
        timeout: int,
    ) -> object:
        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise ValidationError(
                "Local OCR worker is not running.",
                error_code="knowledge_ocr_worker_unavailable",
            )
        request_id = uuid4().hex
        message = {
            "protocol_version": NATIVE_OCR_PROTOCOL_VERSION,
            "request_id": request_id,
            "operation": operation,
            "arguments": arguments,
        }
        with self._request_lock:
            _write_frame(process.stdin, message)
            response = _read_frame_with_poll(
                process,
                timeout=timeout,
            )
        if (
            not isinstance(response, dict)
            or response.get("protocol_version") != NATIVE_OCR_PROTOCOL_VERSION
            or response.get("request_id") != request_id
            or type(response.get("ok")) is not bool
        ):
            raise ValidationError(
                "Local OCR worker returned an invalid response.",
                error_code="knowledge_ocr_response_invalid",
            )
        if response["ok"] is not True:
            reason_code = response.get("reason_code")
            if not isinstance(reason_code, str) or not reason_code.startswith("knowledge_ocr_"):
                reason_code = "knowledge_ocr_worker_failed"
            raise ValidationError(
                "Local OCR operation failed.",
                error_code=reason_code,
                retryable=True,
            )
        if response.keys() != {"protocol_version", "request_id", "ok", "result"}:
            raise ValidationError(
                "Local OCR worker returned an invalid response.",
                error_code="knowledge_ocr_response_invalid",
            )
        return response["result"]

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is not None:
            _stop_worker_process(process)
        if self._stderr is not None:
            try:
                self._stderr.close()
            except OSError:
                pass
            self._stderr = None


class PaddleOcrService:
    def __init__(self, deployment: PaddleOcrDeploymentService) -> None:
        self._deployment = deployment

    def is_ready(self) -> bool:
        return self._deployment.status_snapshot().state is PaddleOcrState.READY

    def runtime_descriptor(self) -> PaddleOcrRuntimeDescriptor:
        return self._deployment.open_runtime().descriptor

    def open_session(
        self,
        *,
        allowed_root: Path,
        log_path: Path,
    ) -> PaddleOcrSession:
        return PaddleOcrSession(
            self._deployment.open_runtime(),
            allowed_root=allowed_root,
            log_path=log_path,
        )

    def recognize(
        self,
        image_path: Path,
        *,
        output_path: Path,
        timeout: int = 300,
    ) -> dict[str, object]:
        with self.open_session(
            allowed_root=image_path.resolve().parent,
            log_path=output_path.with_suffix(".ocr.log"),
        ) as session:
            payload = session.recognize(
                image_path,
                output_path=output_path,
                timeout=timeout,
            )
        return payload


def _normalized_ocr_result(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or value.keys() != {"regions"}:
        raise ValidationError(
            "Local OCR returned an invalid result.",
            error_code="knowledge_ocr_result_invalid",
        )
    regions = value.get("regions")
    if not isinstance(regions, list) or len(regions) > 20_000:
        raise ValidationError(
            "Local OCR returned an invalid result.",
            error_code="knowledge_ocr_result_invalid",
        )
    normalized: list[dict[str, object]] = []
    for region in regions:
        if not isinstance(region, dict) or region.keys() != {"text", "confidence", "polygon"}:
            raise ValidationError(
                "Local OCR returned an invalid result.",
                error_code="knowledge_ocr_result_invalid",
            )
        text = region.get("text")
        confidence = region.get("confidence")
        polygon = region.get("polygon")
        if (
            not isinstance(text, str)
            or len(text) > 32_000
            or not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= float(confidence) <= 1
            or not isinstance(polygon, list)
            or len(polygon) != 4
            or any(
                not isinstance(point, list)
                or len(point) != 2
                or any(not isinstance(coordinate, (int, float)) or isinstance(coordinate, bool) for coordinate in point)
                for point in polygon
            )
        ):
            raise ValidationError(
                "Local OCR returned an invalid result.",
                error_code="knowledge_ocr_result_invalid",
            )
        normalized.append(
            {
                "text": text,
                "confidence": float(confidence),
                "polygon": [[float(value) for value in point] for point in polygon],
            }
        )
    return {"protocol": NATIVE_OCR_PROTOCOL_VERSION, "pages": [{"regions": normalized}]}


def _write_frame(stream, payload: dict[str, object]) -> None:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if not data or len(data) > MAX_PROTOCOL_MESSAGE_BYTES:
        raise ValidationError(
            "Local OCR request is outside the supported bound.",
            error_code="knowledge_ocr_request_too_large",
        )
    stream.write(struct.pack(">I", len(data)))
    stream.write(data)
    stream.flush()


def _read_frame_with_poll(
    process: subprocess.Popen[bytes],
    *,
    timeout: int,
) -> object:
    assert process.stdout is not None
    result_queue: queue.Queue[tuple[object | None, BaseException | None]] = queue.Queue(maxsize=1)

    def read() -> None:
        try:
            result_queue.put((_read_frame(process.stdout), None))
        except BaseException as exc:
            result_queue.put((None, exc))

    threading.Thread(target=read, name="xenix-ocr-response", daemon=True).start()
    deadline = time.monotonic() + max(1, timeout)
    while True:
        if process.poll() is not None and result_queue.empty():
            raise ValidationError(
                "Local OCR worker exited unexpectedly.",
                error_code="knowledge_ocr_worker_crashed",
                retryable=True,
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValidationError(
                "Local OCR operation timed out.",
                error_code="knowledge_ocr_timeout",
                retryable=True,
            )
        try:
            value, error = result_queue.get(timeout=min(PROTOCOL_POLL_INTERVAL_SECONDS, remaining))
        except queue.Empty:
            continue
        if error is not None:
            raise ValidationError(
                "Local OCR worker returned an unreadable response.",
                error_code="knowledge_ocr_response_invalid",
            ) from error
        return value


def _read_frame(stream) -> object:
    header = _read_exact(stream, 4)
    length = struct.unpack(">I", header)[0]
    if length < 2 or length > MAX_PROTOCOL_MESSAGE_BYTES:
        raise ValueError("Native OCR response length is invalid.")
    return bounded_json_object(_read_exact(stream, length).decode("utf-8"), max_bytes=length)


def _read_exact(stream, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError("Native OCR worker closed its response stream.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _stop_worker_process(process: subprocess.Popen[bytes]) -> None:
    try:
        if process.stdin is not None:
            process.stdin.close()
    except OSError:
        pass
    if process.poll() is None:
        try:
            process.terminate()
        except OSError:
            pass
    try:
        process.wait(timeout=PROCESS_TERMINATE_GRACE_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=PROCESS_TERMINATE_GRACE_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            pass
    for stream in (process.stdin, process.stdout):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


def _no_console_creationflags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
