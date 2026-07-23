from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class KnowledgeFormatCapability:
    """One complete source-format route through the document pipeline."""

    source_format: str
    display_name: str
    suffixes: tuple[str, ...]
    media_type: str
    probe_provider_id: str
    normalizer_provider_id: str
    parser_format: str
    route_provider_id: str
    parser_provider_id: str


class KnowledgeFormatRegistry:
    """Validated immutable product-format registry with derived UI/admission views."""

    def __init__(
        self,
        capabilities: Iterable[KnowledgeFormatCapability],
        *,
        version: int = 1,
    ) -> None:
        if type(version) is not int or version < 1:
            raise ValueError(
                "Knowledge format registry version must be a positive integer."
            )
        ordered = tuple(capabilities)
        if not ordered:
            raise ValueError("Knowledge format registry cannot be empty.")
        by_format: dict[str, KnowledgeFormatCapability] = {}
        by_suffix: dict[str, KnowledgeFormatCapability] = {}
        for capability in ordered:
            source_format = capability.source_format.strip().casefold()
            if not source_format or source_format in by_format:
                raise ValueError("Knowledge source formats must be unique and non-empty.")
            if capability.source_format != source_format:
                raise ValueError("Knowledge source formats must be normalized.")
            provider_ids = (
                capability.probe_provider_id,
                capability.normalizer_provider_id,
                capability.route_provider_id,
                capability.parser_provider_id,
            )
            if any(not value or value != value.strip().casefold() for value in provider_ids):
                raise ValueError("Knowledge format provider IDs must be normalized.")
            if not capability.suffixes:
                raise ValueError("Knowledge format capabilities require suffixes.")
            for suffix in capability.suffixes:
                normalized_suffix = suffix.casefold()
                if suffix != normalized_suffix or not suffix.startswith("."):
                    raise ValueError("Knowledge format suffixes must be normalized extensions.")
                if normalized_suffix in by_suffix:
                    raise ValueError("Knowledge format suffixes must be unique.")
                by_suffix[normalized_suffix] = capability
            by_format[source_format] = capability
        self._capabilities = ordered
        self._by_format = by_format
        self._by_suffix = by_suffix
        self._version = version

    @property
    def version(self) -> int:
        return self._version

    @property
    def capabilities(self) -> tuple[KnowledgeFormatCapability, ...]:
        return self._capabilities

    @property
    def supported_suffixes(self) -> frozenset[str]:
        return frozenset(self._by_suffix)

    @property
    def probe_provider_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.probe_provider_id for item in self._capabilities))

    @property
    def normalizer_provider_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.normalizer_provider_id for item in self._capabilities))

    @property
    def route_provider_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.route_provider_id for item in self._capabilities))

    @property
    def parser_provider_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.parser_provider_id for item in self._capabilities))

    @property
    def display_names(self) -> tuple[str, ...]:
        return tuple(item.display_name for item in self._capabilities)

    def capability_for_suffix(self, suffix: str) -> KnowledgeFormatCapability | None:
        return self._by_suffix.get(suffix.casefold())

    def capability_for_format(self, source_format: str) -> KnowledgeFormatCapability | None:
        return self._by_format.get(source_format.casefold())

    def file_dialog_filter(self, label: str = "Knowledge documents") -> str:
        patterns = " ".join(
            f"*{suffix}"
            for capability in self._capabilities
            for suffix in capability.suffixes
        )
        display_label = label.strip() or "Knowledge documents"
        return f"{display_label} ({patterns})"

    def supported_formats_message(self) -> str:
        names = self.display_names
        joined = names[0] if len(names) == 1 else f"{', '.join(names[:-1])}, and {names[-1]}"
        return f"Supported Knowledge formats are {joined}."


KNOWLEDGE_FORMAT_REGISTRY = KnowledgeFormatRegistry(
    (
        KnowledgeFormatCapability(
            "txt", "TXT", (".txt",), "text/plain",
            "text", "text", "txt", "text", "text",
        ),
        KnowledgeFormatCapability(
            "doc",
            "DOC",
            (".doc",),
            "application/msword",
            "cfb-word",
            "doc-to-docx",
            "docx",
            "docx",
            "docx",
        ),
        KnowledgeFormatCapability(
            "docx",
            "DOCX",
            (".docx",),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "ooxml-word",
            "docx",
            "docx",
            "docx",
            "docx",
        ),
        KnowledgeFormatCapability(
            "ppt",
            "PPT",
            (".ppt",),
            "application/vnd.ms-powerpoint",
            "cfb-presentation",
            "ppt-to-pptx",
            "pptx",
            "pptx",
            "pptx",
        ),
        KnowledgeFormatCapability(
            "pptx",
            "PPTX",
            (".pptx",),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "ooxml-presentation",
            "pptx",
            "pptx",
            "pptx",
            "pptx",
        ),
        KnowledgeFormatCapability(
            "pdf", "PDF", (".pdf",), "application/pdf",
            "pdf", "pdf", "pdf", "pdf", "pdf",
        ),
        KnowledgeFormatCapability(
            "jpeg",
            "JPEG",
            (".jpg", ".jpeg"),
            "image/jpeg",
            "image",
            "image",
            "image",
            "image",
            "image",
        ),
        KnowledgeFormatCapability(
            "png",
            "PNG",
            (".png",),
            "image/png",
            "image",
            "image",
            "image",
            "image",
            "image",
        ),
    ),
    version=2,
)
SUPPORTED_KNOWLEDGE_SUFFIXES = KNOWLEDGE_FORMAT_REGISTRY.supported_suffixes


def knowledge_file_dialog_filter(label: str = "Knowledge documents") -> str:
    return KNOWLEDGE_FORMAT_REGISTRY.file_dialog_filter(label)


__all__ = [
    "KNOWLEDGE_FORMAT_REGISTRY",
    "SUPPORTED_KNOWLEDGE_SUFFIXES",
    "KnowledgeFormatCapability",
    "KnowledgeFormatRegistry",
    "knowledge_file_dialog_filter",
]
