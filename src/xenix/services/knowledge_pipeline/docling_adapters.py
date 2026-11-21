"""Adapt text, AnyDoc Markdown, PDFs, and images into Docling documents."""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ...exceptions import ValidationError
from .contracts import _format_mismatch
from .text_decoding import MAX_TEXT_LINE_CHARS, _read_text, _reject_unsafe_text_controls


MAX_ANYDOC_MARKDOWN_BYTES = 64 * 1024 * 1024
MAX_ANYDOC_BLOCKS = 100_000
_ANYDOC_ERROR_CODES = {
    "EncryptedError": "knowledge_password_required",
    "MalformedError": "knowledge_anydoc_malformed",
    "MissingPartError": "knowledge_anydoc_malformed",
    "ResourceLimitError": "knowledge_anydoc_resource_limit",
    "UnsupportedError": "knowledge_anydoc_unsupported",
}
_MARKDOWN_HEADING = re.compile(r"^ {0,3}(#{1,6})[\t ]+(.+?)[\t ]*#*[\t ]*$")
_MARKDOWN_LIST_ITEM = re.compile(r"^ {0,12}([-+*]|\d+[.)])[\t ]+(.+)$")
_MARKDOWN_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^`]*)$")


def _plain_text_docling_document(path: Path):
    from docling_core.types.doc import DocItemLabel, DoclingDocument

    text = _read_text(path)
    document = DoclingDocument(name=path.stem)
    for paragraph in (part.strip() for part in text.split("\n\n")):
        if paragraph:
            document.add_text(DocItemLabel.TEXT, paragraph)
    return document


def _anydoc_convert(path: Path, *, source_format: str):
    try:
        import anydoc

        detected = anydoc.format_from_path(str(path))
        if detected != source_format:
            raise _format_mismatch()
        markdown = anydoc.to_markdown(str(path))
    except ValidationError:
        raise
    except (ImportError, ModuleNotFoundError) as exc:
        raise ValidationError(
            "The local AnyDoc parser is unavailable.",
            error_code="knowledge_anydoc_dependency_failed",
            error_details={"diagnostic_code": "anydoc_dependency_error"},
            retryable=True,
        ) from exc
    except Exception as exc:
        error_name = type(exc).__name__
        error_code = _ANYDOC_ERROR_CODES.get(
            error_name,
            "knowledge_anydoc_conversion_failed",
        )
        raise ValidationError(
            "AnyDoc could not parse the document.",
            error_code=error_code,
            error_details={"diagnostic_code": _anydoc_diagnostic_code(error_name)},
            retryable=error_code in {
                "knowledge_password_required",
                "knowledge_anydoc_conversion_failed",
            },
        ) from exc
    if not isinstance(markdown, str):
        raise ValidationError(
            "AnyDoc returned an invalid document.",
            error_code="knowledge_anydoc_conversion_failed",
            error_details={"diagnostic_code": "anydoc_output_invalid"},
            retryable=True,
        )
    return _markdown_to_docling_document(markdown, name=path.stem)


def _anydoc_diagnostic_code(error_name: str) -> str:
    token = re.sub(r"(?<!^)(?=[A-Z])", "_", error_name).casefold()
    token = re.sub(r"[^a-z0-9_.-]+", "_", token).strip("_")
    return f"anydoc_{token or 'conversion_error'}"[:80]


def _markdown_to_docling_document(markdown: str, *, name: str):
    from docling_core.types.doc import DocItemLabel, DoclingDocument, GroupLabel

    encoded_size = len(markdown.encode("utf-8"))
    if encoded_size < 1 or encoded_size > MAX_ANYDOC_MARKDOWN_BYTES:
        raise ValidationError(
            "AnyDoc output exceeds the supported size.",
            error_code="knowledge_anydoc_output_limit",
        )
    _reject_unsafe_text_controls(markdown)
    document = DoclingDocument(name=name or "document")
    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    fence_marker: str | None = None
    list_group: Any = None
    block_count = 0

    def add_block() -> None:
        nonlocal block_count
        block_count += 1
        if block_count > MAX_ANYDOC_BLOCKS:
            raise ValidationError(
                "AnyDoc output contains too many content blocks.",
                error_code="knowledge_anydoc_output_limit",
            )

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        text = "\n".join(paragraph_lines).strip()
        paragraph_lines.clear()
        if text:
            add_block()
            document.add_text(DocItemLabel.PARAGRAPH, text)

    for raw_line in _bounded_markdown_lines(markdown):
        line = raw_line.rstrip()
        fence = _MARKDOWN_FENCE.match(line)
        if fence_marker is not None:
            if fence and fence.group(1).startswith(fence_marker[0]) and len(fence.group(1)) >= len(fence_marker):
                add_block()
                document.add_code("\n".join(code_lines).rstrip())
                code_lines.clear()
                fence_marker = None
            else:
                code_lines.append(raw_line)
            continue
        if fence:
            flush_paragraph()
            list_group = None
            fence_marker = fence.group(1)
            continue
        if not line.strip():
            flush_paragraph()
            list_group = None
            continue
        heading = _MARKDOWN_HEADING.match(line)
        if heading:
            flush_paragraph()
            list_group = None
            add_block()
            document.add_heading(heading.group(2).strip(), level=len(heading.group(1)))
            continue
        list_item = _MARKDOWN_LIST_ITEM.match(line)
        if list_item:
            flush_paragraph()
            marker, text = list_item.groups()
            if list_group is None:
                list_group = document.add_group(label=GroupLabel.LIST, name="list")
            add_block()
            document.add_list_item(
                text.strip(),
                enumerated=marker[0].isdigit(),
                marker=marker,
                parent=list_group,
            )
            continue
        list_group = None
        paragraph_lines.append(line)

    if fence_marker is not None:
        paragraph_lines.extend((fence_marker, *code_lines))
    flush_paragraph()
    if block_count == 0:
        raise ValidationError(
            "AnyDoc returned no usable content.",
            error_code="knowledge_anydoc_malformed",
        )
    return document


def _bounded_markdown_lines(markdown: str) -> Iterable[str]:
    with io.StringIO(markdown, newline=None) as stream:
        while buffered_line := stream.readline(MAX_TEXT_LINE_CHARS + 2):
            raw_line = buffered_line.rstrip("\r\n")
            if len(raw_line) > MAX_TEXT_LINE_CHARS:
                raise ValidationError(
                    "AnyDoc output contains a line that is too long.",
                    error_code="knowledge_anydoc_output_limit",
                )
            yield raw_line


def _image_docling_document(path: Path):
    from docling_core.types.doc import DoclingDocument

    document = DoclingDocument(name=path.stem)
    document.add_picture()
    return document


def _docling_convert(
    path: Path,
    *,
    source_format: str,
    work_dir: Path,
):
    from ..knowledge_docling import convert_document

    _ = work_dir
    try:
        document = convert_document(path, source_format=source_format)
    except Exception as exc:
        raise ValidationError(
            "Docling could not parse the document.",
            error_code="knowledge_docling_conversion_failed",
            error_details={"diagnostic_code": _docling_diagnostic_code(exc)},
            retryable=True,
        ) from exc
    return document


def _docling_diagnostic_code(exc: Exception) -> str:
    if isinstance(exc, MemoryError):
        return "docling_memory_error"
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return "docling_dependency_error"
    if isinstance(exc, OSError):
        return "docling_runtime_error"
    return "docling_conversion_error"
