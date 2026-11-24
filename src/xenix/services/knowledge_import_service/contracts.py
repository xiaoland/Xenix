from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

TERMINAL_IMPORT_STATUSES = frozenset(
    {"retrieval_ready", "canonical_ready", "needs_attention", "failed", "cancelled", "reused"}
)

SAFE_IMPORT_ERRORS = {
    "knowledge_password_required": "A password is required to continue this import.",
    "knowledge_password_invalid": "The document password was not accepted.",
    "knowledge_anydoc_dependency_failed": "The local document parser is unavailable.",
    "knowledge_anydoc_conversion_failed": "The document could not be parsed.",
    "knowledge_anydoc_malformed": "The document is malformed.",
    "knowledge_anydoc_resource_limit": "The document exceeds parser resource limits.",
    "knowledge_anydoc_unsupported": "The document uses unsupported features.",
    "knowledge_anydoc_output_invalid": "The document parser returned invalid content.",
    "knowledge_anydoc_output_limit": "The parsed document exceeds supported limits.",
    "knowledge_package_invalid": "The document package is invalid.",
    "knowledge_package_entry_limit": "The document package contains too many entries.",
    "knowledge_package_entries_ambiguous": "The document package contains ambiguous entries.",
    "knowledge_package_entry_encrypted": "The document package contains an unsupported encrypted entry.",
    "knowledge_package_entry_unsafe": "The document package contains an unsafe entry.",
    "knowledge_package_path_unsafe": "The document package contains an unsafe path.",
    "knowledge_package_size_invalid": "The document package contains invalid size metadata.",
    "knowledge_package_entry_too_large": "A document package entry is too large.",
    "knowledge_package_expansion_limit": "The expanded document package is too large.",
    "knowledge_package_compression_ratio": "The document package compression ratio is unsafe.",
    "knowledge_format_unsupported": "This file type is not supported by the Knowledge Library.",
    "knowledge_format_mismatch": "The file signature does not match its extension.",
    "knowledge_pdf_invalid": "The PDF is structurally invalid.",
    "knowledge_source_size_unsupported": "The file size is outside the supported range.",
    "knowledge_text_encoding_unknown": "The TXT encoding could not be identified safely.",
    "knowledge_text_encoding_invalid": "The TXT content is invalid for its encoding.",
    "knowledge_text_controls_invalid": "The TXT file contains unsupported control characters.",
    "knowledge_text_line_too_long": "The TXT file contains a line that is too long.",
    "knowledge_docx_package_invalid": "The DOCX file is not a valid Office document.",
    "knowledge_docx_entry_limit": "The DOCX package contains too many entries.",
    "knowledge_docx_entries_ambiguous": "The DOCX package contains ambiguous entries.",
    "knowledge_docx_entry_encrypted": "The DOCX package contains an unsupported encrypted entry.",
    "knowledge_docx_entry_unsafe": "The DOCX package contains an unsafe entry.",
    "knowledge_docx_path_unsafe": "The DOCX package contains an unsafe path.",
    "knowledge_docx_size_invalid": "The DOCX package contains invalid size metadata.",
    "knowledge_docx_entry_too_large": "The DOCX package contains an entry that is too large.",
    "knowledge_docx_expansion_limit": "The expanded DOCX package is too large.",
    "knowledge_docx_compression_ratio": "The DOCX package compression ratio is unsafe.",
    "knowledge_pptx_package_invalid": "The PPTX file is not a valid Office document.",
    "knowledge_pptx_entry_limit": "The PPTX package contains too many entries.",
    "knowledge_pptx_entries_ambiguous": "The PPTX package contains ambiguous entries.",
    "knowledge_pptx_entry_encrypted": "The PPTX package contains an unsupported encrypted entry.",
    "knowledge_pptx_entry_unsafe": "The PPTX package contains an unsafe entry.",
    "knowledge_pptx_path_unsafe": "The PPTX package contains an unsafe path.",
    "knowledge_pptx_size_invalid": "The PPTX package contains invalid size metadata.",
    "knowledge_pptx_entry_too_large": "The PPTX package contains an entry that is too large.",
    "knowledge_pptx_expansion_limit": "The expanded PPTX package is too large.",
    "knowledge_pptx_compression_ratio": "The PPTX package compression ratio is unsafe.",
    "knowledge_docling_conversion_failed": "The document could not be parsed into canonical content.",
    "knowledge_canonical_integrity_failed": "Canonical content failed integrity validation.",
    "knowledge_source_integrity_failed": "The app-owned source snapshot failed integrity validation.",
    "knowledge_source_reselection_required": "Select the source file again to retry this import.",
    "knowledge_import_not_retryable": "This import attempt cannot be retried.",
    "knowledge_import_cancelled": "The import was cancelled.",
    "knowledge_import_worker_crashed": "The import worker stopped unexpectedly.",
    "knowledge_import_worker_launch_failed": "The import worker could not be started.",
    "knowledge_import_worker_timed_out": "The import worker exceeded the allowed execution time.",
    "knowledge_import_failed": "The file could not be imported.",
}


@dataclass(frozen=True)
class KnowledgeImportReceipt:
    import_id: int
    status: str
    reused_existing: bool


@dataclass(frozen=True)
class KnowledgeImportResult:
    import_id: int
    document_id: int
    source_artifact_id: int | None
    source_sha256: str
    canonical_path: str | None
    canonical_generation_id: int | None
    canonical_ready: bool
    reused_existing: bool


@dataclass(frozen=True)
class KnowledgeImportView:
    import_id: int
    file_name: str
    source_format: str
    status: str
    phase: str
    attempt_number: int
    document_id: int | None
    canonical_generation_id: int | None
    reused_existing: bool
    error_code: str | None
    error_summary: str | None
    retryable: bool
    cancel_requested: bool


class ImportCancelled(Exception):
    pass


def path_is_lexically_within(candidate: Path, root: Path) -> bool:
    try:
        absolute_candidate = Path(os.path.abspath(candidate.expanduser()))
        absolute_root = Path(os.path.abspath(root.expanduser()))
        absolute_candidate.relative_to(absolute_root)
    except (OSError, ValueError):
        return False
    return True


def is_current_source_cas_reference(candidate: Path, root: Path) -> bool:
    if not path_is_lexically_within(candidate, root):
        return False
    absolute_candidate = Path(os.path.abspath(candidate.expanduser()))
    absolute_root = Path(os.path.abspath(root.expanduser()))
    relative = absolute_candidate.relative_to(absolute_root)
    parts = relative.parts
    if len(parts) != 6 or parts[:2] != ("objects", "source"):
        return False
    digest = parts[4]
    return bool(
        len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
        and parts[2] == digest[:2]
        and parts[3] == digest[2:4]
        and (parts[5] == "source" or parts[5].startswith("source."))
    )
