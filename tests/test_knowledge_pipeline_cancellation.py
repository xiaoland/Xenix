from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from xenix.exceptions import ValidationError
from xenix.services.knowledge_pipeline import (
    FileProbeResult,
    FormatNormalizer,
    NormalizedSource,
    ParseExecutor,
    ParsePlan,
    ParsePlanUnit,
    _recognize_with_cancellation,
)


class _Cancelled(Exception):
    pass


class _FakeProcess:
    def __init__(self, *, ignore_terminate: bool = False) -> None:
        self.returncode: int | None = None
        self.ignore_terminate = ignore_terminate
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        if not self.ignore_terminate:
            self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is None:
            raise subprocess.TimeoutExpired("bounded-worker", timeout)
        return self.returncode


def test_text_normalization_preserves_callback_exception_during_chunked_io(tmp_path: Path) -> None:
    source = tmp_path / "large.txt"
    source.write_bytes(b"a" * (2 * 1024 * 1024))
    probe = FileProbeResult(source, "txt", "text/plain", source.stat().st_size, False, {})
    cancelled = _Cancelled("cancel import")
    checks = 0

    def check_cancelled() -> None:
        nonlocal checks
        checks += 1
        if checks >= 5:
            raise cancelled

    with pytest.raises(_Cancelled) as raised:
        FormatNormalizer().normalize(
            probe,
            work_dir=tmp_path,
            check_cancelled=check_cancelled,
        )

    assert raised.value is cancelled
    assert not (tmp_path / "normalized.txt").exists()


def test_libreoffice_cancellation_terminates_process_and_preserves_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source-input.doc"
    source.write_bytes(b"legacy office bytes")
    executable = tmp_path / "soffice.exe"
    executable.touch()
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    probe = FileProbeResult(source, "doc", "application/msword", source.stat().st_size, False, {})
    process = _FakeProcess()
    started = False

    def popen(*_args: Any, **_kwargs: Any) -> _FakeProcess:
        nonlocal started
        started = True
        return process

    cancelled = _Cancelled("cancel import")

    def check_cancelled() -> None:
        if started:
            raise cancelled

    monkeypatch.setattr(subprocess, "Popen", popen)

    with pytest.raises(_Cancelled) as raised:
        FormatNormalizer(executable).normalize(
            probe,
            work_dir=work_dir,
            check_cancelled=check_cancelled,
        )

    assert raised.value is cancelled
    assert process.terminated is True
    assert process.killed is False


def test_docling_failure_preserves_a_content_free_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.docx"
    source.touch()
    private_content = "private customer presentation content"

    def fail_conversion(*_args: Any, **_kwargs: Any) -> None:
        raise MemoryError(private_content)

    monkeypatch.setattr(
        "xenix.services.knowledge_docling.convert_document",
        fail_conversion,
    )
    normalized = NormalizedSource(source, "docx", "docx", {"operation": "identity"})
    plan = ParsePlan(
        "docx",
        "docx",
        (ParsePlanUnit("document", "docling-docx", "validated_ooxml"),),
        "document",
    )
    probe = FileProbeResult(source, "docx", None, 1, False, {})

    with pytest.raises(ValidationError) as raised:
        ParseExecutor().parse(
            normalized,
            plan,
            probe=probe,
            work_dir=tmp_path,
        )

    error = raised.value
    assert getattr(error, "error_code", None) == "knowledge_docling_conversion_failed"
    assert getattr(error, "retryable", None) is True
    assert getattr(error, "error_details", None) == {
        "diagnostic_code": "docling_memory_error"
    }
    assert private_content not in str(error)


def test_ocr_keyword_detection_does_not_retry_an_internal_type_error(tmp_path: Path) -> None:
    calls = 0

    class OcrWithCancellation:
        def recognize(
            self,
            image_path: Path,
            *,
            output_path: Path,
            check_cancelled=None,
        ) -> dict[str, object]:
            nonlocal calls
            calls += 1
            assert check_cancelled is not None
            raise TypeError("provider implementation failed")

    with pytest.raises(TypeError, match="provider implementation failed"):
        _recognize_with_cancellation(
            OcrWithCancellation(),
            tmp_path / "page.png",
            output_path=tmp_path / "page.json",
            check_cancelled=lambda: None,
        )

    assert calls == 1


def test_ocr_without_new_keyword_remains_compatible(tmp_path: Path) -> None:
    class LegacyOcr:
        def recognize(self, image_path: Path, *, output_path: Path) -> dict[str, int]:
            return {"protocol": 1}

    checks = 0

    def check_cancelled() -> None:
        nonlocal checks
        checks += 1

    payload = _recognize_with_cancellation(
        LegacyOcr(),
        tmp_path / "page.png",
        output_path=tmp_path / "page.json",
        check_cancelled=check_cancelled,
    )

    assert payload == {"protocol": 1}
    assert checks == 2
