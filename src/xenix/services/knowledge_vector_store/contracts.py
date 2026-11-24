from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Lock, RLock

from ...exceptions import ValidationError

TABLE_NAME = "units"
MANIFEST_FILE_NAME = "manifest.json"
MANIFEST_SCHEMA_VERSION = 2
MAX_MANIFEST_BYTES = 4_096
MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "generation_id",
        "corpus_fingerprint",
        "profile_fingerprint",
        "dimensions",
        "unit_count",
        "unit_ids_sha256",
    }
)
GENERATION_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MAX_FINGERPRINT_CHARACTERS = 256
VECTOR_STAGE_PREFIX = "vector-"
TRASH_DIRECTORY_NAME = ".vector-trash"
TRASH_TOKEN_PATTERN = re.compile(
    r"^vector-(?:generation|stage)-[A-Za-z0-9_-]{1,80}-[0-9a-f]{32}$"
)


class VectorLifecycle:
    def __init__(self) -> None:
        self._lock = RLock()

    @contextmanager
    def hold(self) -> Iterator[None]:
        with self._lock:
            yield


_LIFECYCLES_GUARD = Lock()
_LIFECYCLES: dict[str, VectorLifecycle] = {}


def lifecycle_for(root: Path) -> VectorLifecycle:
    key = os.path.normcase(str(root.resolve()))
    with _LIFECYCLES_GUARD:
        lifecycle = _LIFECYCLES.get(key)
        if lifecycle is None:
            lifecycle = VectorLifecycle()
            _LIFECYCLES[key] = lifecycle
        return lifecycle


class KnowledgeVectorStoreError(ValidationError):
    def __init__(self, message: str = "Knowledge vector storage is unavailable.") -> None:
        super().__init__(
            message,
            error_code="knowledge_vector_store_unavailable",
            retryable=True,
        )


@dataclass(frozen=True)
class KnowledgeVectorRecord:
    unit_id: int
    vector: tuple[float, ...]


class KnowledgeVectorGenerationState(StrEnum):
    USABLE = "usable"
    MISSING = "missing"
    CORRUPT = "corrupt"
    UNSAFE = "unsafe"
