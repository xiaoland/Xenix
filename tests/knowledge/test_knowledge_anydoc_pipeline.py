from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

from xenix.exceptions import ValidationError
from xenix.services.knowledge_formats import KNOWLEDGE_FORMAT_REGISTRY
from xenix.services.knowledge_pipeline import (
    MAX_TEXT_LINE_CHARS,
    FileProbe,
    NormalizedSource,
    ParserRouter,
    _anydoc_convert,
    _bounded_markdown_lines,
    _markdown_to_docling_document,
)


@pytest.mark.parametrize(
    ("source_format", "probe_provider"),
    [
        ("doc", "cfb-word"),
        ("docx", "ooxml-word"),
        ("ppt", "cfb-presentation"),
        ("pptx", "ooxml-presentation"),
        ("rtf", "rtf"),
        ("epub", "mimetype-zip"),
        ("odt", "mimetype-zip"),
        ("odp", "mimetype-zip"),
    ],
)
def test_document_formats_use_the_shared_anydoc_pipeline(
    source_format: str,
    probe_provider: str,
) -> None:
    capability = KNOWLEDGE_FORMAT_REGISTRY.capability_for_format(source_format)

    assert capability is not None
    assert capability.probe_provider_id == probe_provider
    assert capability.normalizer_provider_id == "document"
    assert capability.route_provider_id == "anydoc"
    assert capability.parser_provider_id == "anydoc"


@pytest.mark.parametrize("source_format", ["doc", "docx", "ppt", "pptx", "rtf", "epub", "odt", "odp"])
def test_anydoc_route_is_format_parameterized(
    tmp_path: Path,
    source_format: str,
) -> None:
    source = tmp_path / f"source.{source_format}"
    plan = ParserRouter().route(
        NormalizedSource(source, source_format, source_format, {}),
        ocr_ready=False,
    )

    assert plan.source_format == source_format
    assert plan.units[0].route_id == f"anydoc-{source_format}"


def test_rtf_probe_accepts_real_header(tmp_path: Path) -> None:
    source = tmp_path / "source.rtf"
    source.write_bytes(b"{\\rtf1\\ansi Safe local document}")

    probe = FileProbe().probe(source)

    assert probe.source_format == "rtf"
    assert probe.facts["container"] == "rtf"


@pytest.mark.parametrize(
    ("suffix", "mimetype"),
    [
        (".epub", "application/epub+zip"),
        (".odt", "application/vnd.oasis.opendocument.text"),
        (".odp", "application/vnd.oasis.opendocument.presentation"),
    ],
)
def test_mimetype_zip_probe_validates_package_identity(
    tmp_path: Path,
    suffix: str,
    mimetype: str,
) -> None:
    source = tmp_path / f"source{suffix}"
    with ZipFile(source, "w") as package:
        package.writestr("mimetype", mimetype, compress_type=ZIP_STORED)
        package.writestr("content.xml", "<document/>", compress_type=ZIP_DEFLATED)

    probe = FileProbe().probe(source)

    assert probe.source_format == suffix[1:]
    assert probe.facts["container"] == "zip"


def test_mimetype_zip_probe_rejects_disguised_package(tmp_path: Path) -> None:
    source = tmp_path / "source.epub"
    with ZipFile(source, "w") as package:
        package.writestr("mimetype", "application/vnd.oasis.opendocument.text")

    with pytest.raises(ValidationError) as raised:
        FileProbe().probe(source)

    assert raised.value.error_code == "knowledge_format_mismatch"


def test_mimetype_zip_probe_rejects_unsafe_member_path(tmp_path: Path) -> None:
    source = tmp_path / "source.odt"
    with ZipFile(source, "w") as package:
        package.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        package.writestr("../escape", "bad")

    with pytest.raises(ValidationError) as raised:
        FileProbe().probe(source)

    assert raised.value.error_code == "knowledge_package_path_unsafe"


def test_markdown_adapter_preserves_structure() -> None:
    document = _markdown_to_docling_document(
        "# Handbook\n\nIntro text.\n\n- first\n- second\n\n```py\nprint('ok')\n```",
        name="handbook",
    )
    exported = document.export_to_text()

    assert "Handbook" in exported
    assert "Intro text" in exported
    assert "first" in exported
    assert "print('ok')" in exported


def test_bounded_markdown_lines_normalizes_mixed_newlines() -> None:
    assert list(_bounded_markdown_lines("one\r\ntwo\rthree\n")) == ["one", "two", "three"]


def test_bounded_markdown_lines_rejects_oversized_line() -> None:
    with pytest.raises(ValidationError) as raised:
        list(_bounded_markdown_lines("x" * (MAX_TEXT_LINE_CHARS + 1)))

    assert raised.value.error_code == "knowledge_anydoc_output_limit"


def test_anydoc_conversion_records_real_adapter_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.rtf"
    source.write_bytes(b"{\\rtf1\\ansi Heading}")
    fake = SimpleNamespace(
        format_from_path=lambda path: "rtf",
        to_markdown=lambda path: "# Heading\n\nBody sentence.",
    )
    monkeypatch.setitem(sys.modules, "anydoc", fake)

    document = _anydoc_convert(source, source_format="rtf")

    assert "Heading" in document.export_to_text()
    assert "Body sentence" in document.export_to_text()
