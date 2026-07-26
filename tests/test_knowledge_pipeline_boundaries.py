from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pikepdf
import pytest
from docling_core.types.doc import DoclingDocument
from PIL import Image
from pydantic import ValidationError as PydanticValidationError

import xenix.services.knowledge_pipeline as pipeline_module
from xenix.exceptions import ValidationError
from xenix.services.knowledge_formats import (
    KNOWLEDGE_FORMAT_CATALOG,
    KNOWLEDGE_FORMAT_REGISTRY,
    SUPPORTED_KNOWLEDGE_SUFFIXES,
    KnowledgeFormatCapability,
    KnowledgeFormatCatalog,
    knowledge_file_dialog_filter,
)
from xenix.services.knowledge_pipeline import (
    MAX_OOXML_PACKAGE_ENTRIES,
    FileProbe,
    FileProbeResult,
    FormatNormalizer,
    NormalizedSource,
    ParseExecutor,
    ParsePlan,
    ParsePlanUnit,
    ParserRouter,
)
from xenix.services.knowledge_pdf import (
    PdfPageEvidence,
    PdfPageTextState,
    classify_pdf_page_text,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def test_format_catalog_drives_derived_views_and_router_closure() -> None:
    expected_suffixes = frozenset(
        suffix
        for capability in KNOWLEDGE_FORMAT_CATALOG.capabilities
        for suffix in capability.suffixes
    )

    assert KNOWLEDGE_FORMAT_CATALOG.version == 2
    assert SUPPORTED_KNOWLEDGE_SUFFIXES == expected_suffixes
    assert knowledge_file_dialog_filter("知识文档") == (
        "知识文档 (*.txt *.doc *.docx *.ppt *.pptx *.pdf *.jpg *.jpeg *.png)"
    )
    pptx_capability = KNOWLEDGE_FORMAT_REGISTRY.capability_for_suffix(".PPTX")
    assert pptx_capability is not None
    assert pptx_capability.source_format == "pptx"
    assert KNOWLEDGE_FORMAT_REGISTRY.route_provider_ids == (
        "text",
        "docx",
        "pptx",
        "pdf",
        "image",
    )
    assert set(KNOWLEDGE_FORMAT_REGISTRY.route_provider_ids) == set(
        ParserRouter().registered_provider_ids
    )


@pytest.mark.parametrize(
    "catalog_payload",
    [
        {"version": 0, "capabilities": (KNOWLEDGE_FORMAT_CATALOG.capabilities[0],)},
        {"version": 1, "capabilities": ()},
        {
            "version": 1,
            "capabilities": (
                KNOWLEDGE_FORMAT_CATALOG.capabilities[0],
                KnowledgeFormatCapability.model_validate(
                    {
                        "source_format": "txt",
                        "display_name": "TEXT",
                        "suffixes": (".text",),
                        "media_type": "text/plain",
                        "probe_provider_id": "text",
                        "normalizer_provider_id": "text",
                        "parser_format": "txt",
                        "route_provider_id": "text",
                        "parser_provider_id": "text",
                    }
                ),
            ),
        },
        {
            "version": 1,
            "capabilities": (
                KNOWLEDGE_FORMAT_CATALOG.capabilities[0],
                KnowledgeFormatCapability.model_validate(
                    {
                        "source_format": "text",
                        "display_name": "TEXT",
                        "suffixes": (".txt",),
                        "media_type": "text/plain",
                        "probe_provider_id": "text",
                        "normalizer_provider_id": "text",
                        "parser_format": "txt",
                        "route_provider_id": "text",
                        "parser_provider_id": "text",
                    }
                ),
            ),
        },
    ],
    ids=("version", "empty", "duplicate-format", "duplicate-suffix"),
)
def test_format_catalog_rejects_cross_capability_invariant_violations(
    catalog_payload: dict[str, object],
) -> None:
    with pytest.raises(PydanticValidationError):
        KnowledgeFormatCatalog.model_validate(catalog_payload)


@pytest.mark.parametrize(
    ("providers", "required_ids", "message"),
    [
        ((SimpleNamespace(provider_id=1),), ("1",), "normalized strings"),
        (
            (
                SimpleNamespace(provider_id="text"),
                SimpleNamespace(provider_id="text"),
            ),
            ("text",),
            "must be unique",
        ),
        ((SimpleNamespace(provider_id="text"),), ("pdf",), "providers are missing"),
        (
            (
                SimpleNamespace(provider_id="text"),
                SimpleNamespace(provider_id="pdf"),
            ),
            ("text",),
            "no format capability",
        ),
    ],
    ids=("non-string", "duplicate", "missing", "unused"),
)
def test_provider_maps_fail_closed_on_invalid_provider_sets(
    providers: tuple[SimpleNamespace, ...],
    required_ids: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        pipeline_module._provider_map(
            providers,
            required_ids=required_ids,
            kind="test",
        )


def test_pptx_uses_complete_presentation_capability(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "rules.pptx"
    _write_minimal_pptx(source)
    probe = FileProbe().probe(source)
    normalized = FormatNormalizer().normalize(probe, work_dir=tmp_path)
    plan = ParserRouter().route(normalized, ocr_ready=False)
    monkeypatch.setattr(
        pipeline_module,
        "_docling_convert",
        lambda *_args, **_kwargs: DoclingDocument(name="presentation"),
    )

    result = ParseExecutor().parse(
        normalized,
        plan,
        probe=probe,
        work_dir=tmp_path,
    )

    assert probe.source_format == "pptx"
    assert probe.facts["probe_provider_id"] == "ooxml-presentation"
    assert normalized.parser_format == "pptx"
    assert normalized.descriptor["backend"] == "ooxml-identity"
    assert plan.units[0].route_id == "docling-pptx"
    assert result.pipeline["parser"]["options"]["parser_format"] == "pptx"


def test_pptx_rejects_a_word_ooxml_package(tmp_path: Path) -> None:
    source = tmp_path / "wrong-package.pptx"
    _write_minimal_docx(source)

    with pytest.raises(ValidationError) as raised:
        FileProbe().probe(source)

    assert raised.value.error_code == "knowledge_pptx_package_invalid"


def test_pptx_uses_the_shared_ooxml_package_safety_boundary(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.pptx"
    with ZipFile(source, "w", ZIP_STORED) as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("ppt/presentation.xml", "<presentation/>")
        package.writestr("../outside.xml", "<unsafe/>")

    with pytest.raises(ValidationError) as raised:
        FileProbe().probe(source)

    assert raised.value.error_code == "knowledge_pptx_path_unsafe"


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        (
            dict(
                extracted_characters=7,
                alphanumeric_characters=7,
                suspicious_characters=0,
                image_coverage=0.0,
                unembedded_nonstandard_fonts=0,
            ),
            PdfPageTextState.ABSENT,
        ),
        (
            dict(
                extracted_characters=30,
                alphanumeric_characters=24,
                suspicious_characters=1,
                image_coverage=0.0,
                unembedded_nonstandard_fonts=0,
            ),
            PdfPageTextState.SUSPECT,
        ),
        (
            dict(
                extracted_characters=30,
                alphanumeric_characters=24,
                suspicious_characters=0,
                image_coverage=0.0,
                unembedded_nonstandard_fonts=0,
            ),
            PdfPageTextState.CREDIBLE,
        ),
    ],
)
def test_pdf_page_text_classification_is_explicit_and_tri_state(
    facts: dict[str, object],
    expected: PdfPageTextState,
) -> None:
    state, reasons = classify_pdf_page_text(**facts)

    assert state is expected
    assert reasons


def test_pdf_router_keeps_page_evidence_and_uses_hybrid_for_suspect_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-fixture")
    evidence = (
        PdfPageEvidence(1, PdfPageTextState.CREDIBLE, ("native_text_credible",), 30, 25, 0, 0.0, 0, 1, 0, 0),
        PdfPageEvidence(2, PdfPageTextState.SUSPECT, ("suspicious_unicode",), 30, 20, 1, 0.0, 0, 1, 0, 0),
        PdfPageEvidence(3, PdfPageTextState.ABSENT, ("useful_text_absent",), 0, 0, 0, 1.0, 1, 0, 0, 0),
    )
    monkeypatch.setattr(pipeline_module, "probe_pdf_pages", lambda _path: evidence)

    plan = ParserRouter().route(
        NormalizedSource(source, "pdf", "pdf", {"operation": "identity"}),
        ocr_ready=True,
    )

    assert [unit.route_id for unit in plan.units] == [
        "docling-pdf-native",
        "paddleocr-hybrid-page",
        "paddleocr-page",
    ]
    assert plan.policy_version == 2
    assert plan.units[1].evidence["text_state"] == "suspect"


@pytest.mark.parametrize(
    ("payload", "expected_encoding"),
    [
        (b"\xef\xbb\xbf" + "库存\r\nRule\r尾行".encode(), "utf-8"),
        (b"\xff\xfe" + "库存\r\nRule\r尾行".encode("utf-16-le"), "utf-16-le"),
        (b"\xfe\xff" + "库存\r\nRule\r尾行".encode("utf-16-be"), "utf-16-be"),
    ],
)
def test_txt_bom_decode_is_strict_normalized_and_hashed(
    tmp_path: Path,
    payload: bytes,
    expected_encoding: str,
) -> None:
    source = tmp_path / "confidential-name.txt"
    source.write_bytes(payload)

    probe = FileProbe().probe(source)
    normalized = FormatNormalizer().normalize(probe, work_dir=tmp_path)

    assert normalized.path.read_text(encoding="utf-8") == "库存\nRule\n尾行"
    assert normalized.descriptor["encoding"] == expected_encoding
    assert normalized.descriptor["newline"] == {"input": "mixed", "output": "lf"}
    assert normalized.descriptor["normalization"] == {
        "bom_removed": True,
        "newlines_normalized": True,
        "unicode_normalization": "preserved",
    }
    assert normalized.descriptor["input_sha256"] == hashlib.sha256(payload).hexdigest()
    assert normalized.descriptor["output_sha256"] == hashlib.sha256(
        "库存\nRule\n尾行".encode()
    ).hexdigest()
    assert str(source.resolve()) not in json.dumps(normalized.descriptor)


def test_txt_accepts_only_a_confident_allowlisted_fallback(tmp_path: Path) -> None:
    text = "门店库存规则要求每周检查安全库存和补货周期。" * 20
    source = tmp_path / "rules.txt"
    source.write_bytes(text.encode("gb18030"))

    probe = FileProbe().probe(source)
    normalized = FormatNormalizer().normalize(probe, work_dir=tmp_path)

    assert normalized.descriptor["encoding"] == "gb18030"
    assert normalized.path.read_text(encoding="utf-8") == text


@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        (b"Caf\xe9", "knowledge_text_encoding_unknown"),
        (b"plain\x00binary", "knowledge_text_controls_invalid"),
        (b"plain\x01control", "knowledge_text_controls_invalid"),
    ],
)
def test_txt_rejects_uncertain_binary_and_control_inputs(
    tmp_path: Path,
    payload: bytes,
    error_code: str,
) -> None:
    source = tmp_path / "unsafe.txt"
    source.write_bytes(payload)

    with pytest.raises(ValidationError) as raised:
        FileProbe().probe(source)

    assert raised.value.error_code == error_code


def test_txt_long_line_has_a_stable_rejection_category(tmp_path: Path) -> None:
    source = tmp_path / "long.txt"
    source.write_text("x" * (pipeline_module.MAX_TEXT_LINE_CHARS + 1), encoding="utf-8")
    probe = FileProbe().probe(source)

    with pytest.raises(ValidationError) as raised:
        FormatNormalizer().normalize(probe, work_dir=tmp_path)

    assert raised.value.error_code == "knowledge_text_line_too_long"


@pytest.mark.parametrize(
    "failure_factory",
    [
        lambda: ValidationError("provider detail C:/private/model"),
        lambda: OSError("private worker path"),
        lambda: TimeoutError("private timeout detail"),
        lambda: subprocess.SubprocessError("private subprocess detail"),
    ],
)
def test_expected_image_ocr_failures_degrade_to_a_safe_projection_warning(
    tmp_path: Path,
    failure_factory: Callable[[], BaseException],
) -> None:
    class FailingOcr:
        def is_ready(self) -> bool:
            return True

        def recognize(self, *_args: Any, **_kwargs: Any) -> dict[str, object]:
            raise failure_factory()

    probe, normalized, plan = _image_parse_inputs(tmp_path, ocr_ready=True)
    result = ParseExecutor(FailingOcr()).parse(
        normalized,
        plan,
        probe=probe,
        work_dir=tmp_path,
    )

    assert len(result.document.pictures) == 1
    assert result.warnings == ["ocr_projection_unavailable"]
    assert result.projections == [{"kind": "ocr_text", "status": "unavailable"}]
    assert result.pipeline["ocr"]["status"] == "unavailable"
    assert result.pipeline["ocr"]["unavailable_count"] == 1
    persisted = json.dumps(result.pipeline, sort_keys=True)
    assert "private" not in persisted
    assert "C:/" not in persisted


def test_unknown_image_ocr_failure_remains_fail_closed(tmp_path: Path) -> None:
    class BrokenOcr:
        def recognize(self, *_args: Any, **_kwargs: Any) -> dict[str, object]:
            raise RuntimeError("programming defect")

    probe, normalized, plan = _image_parse_inputs(tmp_path, ocr_ready=True)

    with pytest.raises(RuntimeError, match="programming defect"):
        ParseExecutor(BrokenOcr()).parse(
            normalized,
            plan,
            probe=probe,
            work_dir=tmp_path,
        )


def test_ocr_cancellation_preserves_identity_even_when_it_is_an_oserror(
    tmp_path: Path,
) -> None:
    class CancelledOSError(OSError):
        pass

    class CooperativeOcr:
        def recognize(
            self,
            _image_path: Path,
            *,
            output_path: Path,
            check_cancelled=None,
        ) -> dict[str, object]:
            assert output_path.name == "image-ocr.json"
            assert check_cancelled is not None
            check_cancelled()
            return {}

    cancelled = CancelledOSError("cancel import")
    checks = 0

    def check_cancelled() -> None:
        nonlocal checks
        checks += 1
        if checks == 2:
            raise cancelled

    probe, normalized, plan = _image_parse_inputs(tmp_path, ocr_ready=True)
    with pytest.raises(CancelledOSError) as raised:
        ParseExecutor(CooperativeOcr()).parse(
            normalized,
            plan,
            probe=probe,
            work_dir=tmp_path,
            check_cancelled=check_cancelled,
        )

    assert raised.value is cancelled


def test_executor_obeys_ocr_unavailable_plan_if_service_readiness_changes(
    tmp_path: Path,
) -> None:
    class NewlyReadyOcr:
        readiness_calls = 0
        recognize_calls = 0

        def is_ready(self) -> bool:
            self.readiness_calls += 1
            return True

        def recognize(self, *_args: Any, **_kwargs: Any) -> dict[str, object]:
            self.recognize_calls += 1
            return {}

    ocr = NewlyReadyOcr()
    probe, normalized, plan = _image_parse_inputs(tmp_path, ocr_ready=False)
    result = ParseExecutor(ocr).parse(
        normalized,
        plan,
        probe=probe,
        work_dir=tmp_path,
    )

    assert ocr.readiness_calls == 0
    assert ocr.recognize_calls == 0
    assert result.pipeline["ocr"]["ready"] is False
    assert result.pipeline["ocr"]["status"] == "unavailable"


def test_pdf_ocr_failure_is_page_scoped_and_keeps_partial_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "two-pages.pdf"
    with pikepdf.Pdf.new() as pdf:
        pdf.add_blank_page(page_size=(100, 100))
        pdf.add_blank_page(page_size=(100, 100))
        pdf.save(source)

    class PartialOcr:
        calls = 0

        def recognize(self, *_args: Any, **_kwargs: Any) -> dict[str, object]:
            self.calls += 1
            if self.calls == 2:
                raise OSError("private worker detail")
            return {}

    monkeypatch.setattr(
        pipeline_module,
        "_docling_convert",
        lambda *_args, **_kwargs: DoclingDocument(name="bounded-pdf"),
    )
    normalized = NormalizedSource(source, "pdf", "pdf", {"operation": "identity"})
    plan = ParsePlan(
        "pdf",
        "pdf",
        (
            ParsePlanUnit("page", "paddleocr-page", "native_text_insufficient", 1),
            ParsePlanUnit("page", "paddleocr-page", "native_text_insufficient", 2),
        ),
        "docling-document-plus-page-projections",
        ocr_ready=True,
    )
    probe = FileProbeResult(
        source,
        "pdf",
        "application/pdf",
        source.stat().st_size,
        False,
        {"page_count": 2},
    )

    result = ParseExecutor(PartialOcr()).parse(
        normalized,
        plan,
        probe=probe,
        work_dir=tmp_path,
    )

    assert result.warnings == ["ocr_projection_unavailable"]
    assert result.projections == [
        {"kind": "ocr_text", "status": "ready", "pages": [1], "items": 0},
        {"kind": "ocr_text", "status": "unavailable", "pages": [2]},
    ]
    assert result.pipeline["ocr"]["status"] == "partial"
    assert result.pipeline["ocr"]["attempted_count"] == 2
    assert result.pipeline["ocr"]["succeeded_count"] == 1
    assert result.pipeline["ocr"]["unavailable_count"] == 1


def test_pipeline_descriptors_have_safe_packages_options_status_and_hashes(
    tmp_path: Path,
) -> None:
    class SuccessfulOcr:
        def runtime_descriptor(self) -> dict[str, object]:
            return {
                "generation_id": "runtime-generation-1",
                "runtime_id": "paddle-inference-win-x64",
                "model_pack_id": "pp-ocr-model-pack",
                "engine": "paddle-inference",
                "engine_version": "3.3.0",
                "protocol_version": 2,
                "manifest_sha256": "a" * 64,
            }

        def recognize(self, *_args: Any, **_kwargs: Any) -> dict[str, object]:
            return {"rec_texts": [], "rec_polys": []}

    probe, normalized, plan = _image_parse_inputs(tmp_path, ocr_ready=True)
    result = ParseExecutor(SuccessfulOcr()).parse(
        normalized,
        plan,
        probe=probe,
        work_dir=tmp_path,
    )

    for descriptor in (
        result.pipeline["normalizer"],
        result.pipeline["parser"],
        result.pipeline["ocr"],
    ):
        assert descriptor["package"]["name"]
        assert descriptor["backend"]
        assert isinstance(descriptor["options"], dict)
        assert descriptor["status"] == "succeeded"
        assert _SHA256.fullmatch(descriptor["input_sha256"])
        assert _SHA256.fullmatch(descriptor["output_sha256"])
    assert result.pipeline["normalizer"]["output_sha256"] == result.pipeline["parser"][
        "input_sha256"
    ]
    assert result.pipeline["parser"]["input_sha256"] == result.pipeline["ocr"][
        "input_sha256"
    ]
    assert result.pipeline["ocr"]["runtime"] == {
        "generation_id": "runtime-generation-1",
        "runtime_id": "paddle-inference-win-x64",
        "model_pack_id": "pp-ocr-model-pack",
        "engine": "paddle-inference",
        "engine_version": "3.3.0",
        "protocol_version": 2,
        "manifest_sha256": "a" * 64,
    }
    serialized = json.dumps(result.pipeline, sort_keys=True)
    assert str(probe.source_path.resolve()) not in serialized
    assert str(tmp_path.resolve()) not in serialized
    assert "password" not in serialized.casefold()


@pytest.mark.parametrize(
    ("extra_name", "extra_payload", "error_code"),
    [
        ("../outside.xml", b"unsafe", "knowledge_docx_path_unsafe"),
        (
            "word/media/bomb.bin",
            b"0" * (2 * 1024 * 1024),
            "knowledge_docx_compression_ratio",
        ),
    ],
    ids=("path-traversal", "compression-ratio"),
)
def test_docx_rejects_unsafe_paths_and_high_compression_before_parsing(
    tmp_path: Path,
    extra_name: str,
    extra_payload: bytes,
    error_code: str,
) -> None:
    source = tmp_path / "unsafe.docx"
    _write_minimal_docx(source, extra=(extra_name, extra_payload), compression=ZIP_DEFLATED)

    with pytest.raises(ValidationError) as raised:
        FileProbe().probe(source)

    assert raised.value.error_code == error_code


def test_docx_rejects_actual_entry_count_above_the_exported_limit(tmp_path: Path) -> None:
    source = tmp_path / "many.docx"
    with ZipFile(source, "w", ZIP_STORED) as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<document/>")
        for index in range(MAX_OOXML_PACKAGE_ENTRIES - 1):
            package.writestr(f"word/items/{index}.xml", "")

    with pytest.raises(ValidationError) as raised:
        FileProbe().probe(source)

    assert raised.value.error_code == "knowledge_docx_entry_limit"


@pytest.mark.parametrize(
    ("limit_name", "limit_value", "error_code"),
    [
        ("MAX_OOXML_ENTRY_BYTES", 15, "knowledge_docx_entry_too_large"),
        ("MAX_OOXML_EXPANDED_BYTES", 45, "knowledge_docx_expansion_limit"),
    ],
)
def test_docx_enforces_per_entry_and_total_expansion_limits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    limit_name: str,
    limit_value: int,
    error_code: str,
) -> None:
    monkeypatch.setattr(pipeline_module, limit_name, limit_value)
    source = tmp_path / "expanded.docx"
    with ZipFile(source, "w", ZIP_STORED) as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<document/>")
        package.writestr("word/data/one.bin", b"1" * 20)
        package.writestr("word/data/two.bin", b"2" * 20)

    with pytest.raises(ValidationError) as raised:
        FileProbe().probe(source)

    assert raised.value.error_code == error_code


def _image_parse_inputs(
    tmp_path: Path,
    *,
    ocr_ready: bool,
) -> tuple[FileProbeResult, NormalizedSource, ParsePlan]:
    source = tmp_path / "private-password-like-name.png"
    Image.new("RGB", (8, 8), "white").save(source)
    probe = FileProbe().probe(source)
    normalized = FormatNormalizer().normalize(probe, work_dir=tmp_path)
    plan = ParserRouter().route(normalized, ocr_ready=ocr_ready)
    return probe, normalized, plan


def _write_minimal_docx(
    path: Path,
    *,
    extra: tuple[str, bytes] | None = None,
    compression: int = ZIP_STORED,
) -> None:
    with ZipFile(path, "w", compression) as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<document/>")
        if extra is not None:
            package.writestr(*extra)


def _write_minimal_pptx(path: Path) -> None:
    with ZipFile(path, "w", ZIP_STORED) as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("ppt/presentation.xml", "<presentation/>")
