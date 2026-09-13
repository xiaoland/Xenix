from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


RETRIEVAL_PROJECTION_VERSION = 4
CORPUS_FINGERPRINT_SCHEMA = 5

_PROJECTION_FINGERPRINT_DOMAIN = "xenix.knowledge-projection/v4"
_CORPUS_FINGERPRINT_DOMAIN = "xenix.knowledge-corpus/v5"


@dataclass(frozen=True)
class KnowledgeProjectionMetadata:
    document_id: int
    retrieval_generation_id: int
    projection_version: int
    content_fingerprint: str
    unit_count: int


@dataclass(frozen=True)
class KnowledgeProjectionUnit:
    id: int
    document_id: int
    canonical_generation_id: int
    ordinal: int
    text: str


@dataclass(frozen=True)
class KnowledgeProjectionIdentity:
    """Metadata and persisted Unit identities for one retrieval corpus revision."""

    metadata: tuple[KnowledgeProjectionMetadata, ...]
    unit_ids: tuple[int, ...]

    @property
    def corpus_fingerprint(self) -> str:
        return corpus_fingerprint(self.metadata, self.unit_ids)

    @property
    def unit_count(self) -> int:
        return sum(item.unit_count for item in self.metadata)



@dataclass(frozen=True)
class KnowledgeProjectionSnapshot:
    """One frozen SQLite view used throughout a vector build."""

    identity: KnowledgeProjectionIdentity
    units: tuple[KnowledgeProjectionUnit, ...]

def retrieval_content_fingerprint(
    units: Iterable[tuple[int, str, Mapping[str, object]]],
) -> str:
    """Fingerprint one derived text projection without depending on row ids."""

    digest = hashlib.sha256()
    digest.update(_PROJECTION_FINGERPRINT_DOMAIN.encode("ascii"))
    for ordinal, text, locator in units:
        payload = {
            "locator": dict(locator),
            "ordinal": int(ordinal),
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def corpus_fingerprint(metadata: Sequence[KnowledgeProjectionMetadata], unit_ids: Sequence[int]) -> str:
    """Fingerprint document revisions and Unit IDs without loading text bodies."""

    payload = {
        "schema": _CORPUS_FINGERPRINT_DOMAIN,
        "unit_ids": list(unit_ids),
        "documents": [
            {
                "content_fingerprint": item.content_fingerprint,
                "document_id": item.document_id,
                "projection_version": item.projection_version,
                "retrieval_generation_id": item.retrieval_generation_id,
                "unit_count": item.unit_count,
            }
            for item in sorted(metadata, key=lambda value: value.document_id)
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "CORPUS_FINGERPRINT_SCHEMA",
    "KnowledgeProjectionIdentity",
    "KnowledgeProjectionMetadata",
    "KnowledgeProjectionSnapshot",
    "KnowledgeProjectionUnit",
    "RETRIEVAL_PROJECTION_VERSION",
    "corpus_fingerprint",
    "retrieval_content_fingerprint",
]
