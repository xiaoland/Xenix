"""Read-only source, delivery and canonical-state helpers for benchmark cases."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

import polars as pl

from xenix.exceptions import NotFoundError, ValidationError
from xenix.services.dataset_inspection import detect_source_format
from xenix.services.llm.messages import DatasetBlock, blocks_from_payload
from xenix.services.tabular import load_tabular_frame

from .contracts import BenchmarkCaseContext, BenchmarkCaseServices, BenchmarkInputError


def linked_tables(context: BenchmarkCaseContext) -> dict[str, pl.DataFrame]:
    """Read tables actually delivered by link, independent of Dataset lineage.

    Invalid or unavailable links provide no delivery. Unexpected service or
    table-reading errors propagate as measurement failures.
    """
    messages = list(getattr(context.snapshot, "messages", ()))
    final_text = str(getattr(messages[-1], "text", "") or "") if messages else ""
    uris = re.findall(r"artifact://[A-Za-z0-9-]+(?:\?[^)\s>\]]+)?", final_text)
    tables = {}
    for uri in dict.fromkeys(uris):
        try:
            artifact = context.services.artifacts.resolve_uri(uri)
        except NotFoundError, ValidationError:
            continue
        if not artifact.exists or not artifact.ready_to_open:
            continue
        path = Path(artifact.absolute_path)
        if not is_within(path, context.runtime_home):
            continue
        source_format = detect_source_format(path)
        if source_format.value != "unknown":
            tables[uri] = load_tabular_frame(path, source_format)
    return tables


@dataclass(frozen=True)
class AttachedSourceState:
    external_sha256: str
    source_dataset_ids: tuple[int, ...]
    registered_dataset_sha256: dict[int, str]


def capture_attached_source_state(
    *,
    source_path: Path,
    snapshot: Any,
    services: BenchmarkCaseServices,
) -> AttachedSourceState:
    source_dataset_ids = source_dataset_ids_from_snapshot(snapshot)
    registered_hashes: dict[int, str] = {}
    for dataset_id in source_dataset_ids:
        dataset = services.datasets.get_dataset(dataset_id)
        registered_path = Path(dataset.source_path)
        if not registered_path.is_file():
            raise BenchmarkInputError("registered_source_unreadable")
        registered_hashes[dataset_id] = sha256_file(registered_path)
    return AttachedSourceState(
        external_sha256=sha256_file(source_path),
        source_dataset_ids=tuple(source_dataset_ids),
        registered_dataset_sha256=registered_hashes,
    )


def attached_source_unchanged(
    *,
    source_path: Path,
    source_state: AttachedSourceState,
    services: BenchmarkCaseServices,
) -> bool:
    if sha256_file(source_path) != source_state.external_sha256:
        return False
    try:
        return all(
            sha256_file(Path(services.datasets.get_dataset(dataset_id).source_path)) == digest
            for dataset_id, digest in source_state.registered_dataset_sha256.items()
        )
    except Exception:
        return False


def source_dataset_ids_from_snapshot(snapshot: Any) -> list[int]:
    dataset_ids: list[int] = []
    for message in getattr(snapshot, "messages", []):
        if enum_value(getattr(message, "kind", None)) != "user":
            continue
        payload = getattr(message, "content_payload", None)
        for block in blocks_from_payload(payload if isinstance(payload, dict) else None):
            if isinstance(block, DatasetBlock) and block.dataset_id not in dataset_ids:
                dataset_ids.append(block.dataset_id)
    return dataset_ids


def registered_source_ids_for_digest(
    *,
    snapshot: Any,
    services: BenchmarkCaseServices,
    digest: str,
) -> set[int]:
    """Resolve attachment Dataset identity from the final canonical snapshot.

    Multi-attachment submission can emit an early snapshot before every source
    is registered. Source immutability still uses the first captured external
    digest, while identity and lineage resolution use the complete final list.
    """

    matches: set[int] = set()
    for dataset_id in source_dataset_ids_from_snapshot(snapshot):
        try:
            dataset = services.datasets.get_dataset(dataset_id)
            registered_path = Path(dataset.source_path)
            if registered_path.is_file() and sha256_file(registered_path) == digest:
                matches.add(dataset_id)
        except Exception:
            continue
    return matches


def source_dataset_ids_for_external_digest(
    *,
    snapshot: Any,
    services: BenchmarkCaseServices,
    digest: str,
) -> set[int]:
    """Map a canonical Dataset block back to its immutable imported source.

    Registered Dataset rows point at app-owned Parquet materializations, so
    their content hash intentionally differs from an attached CSV/XLSX file.
    Source presentation is the read-only provenance seam that retains the
    original attachment path without projecting it to the subject or report.
    """

    resolver = getattr(services.datasets, "resolve_dataset_source_presentation", None)
    if not callable(resolver):
        return set()
    matches: set[int] = set()
    for dataset_id in source_dataset_ids_from_snapshot(snapshot):
        try:
            presentation = resolver(dataset_id)
            open_path = getattr(presentation, "open_path", None)
            source_path = Path(open_path) if isinstance(open_path, str) else None
            if source_path is not None and source_path.is_file() and sha256_file(source_path) == digest:
                matches.add(dataset_id)
        except Exception:
            continue
    return matches


def canonical_completion(snapshot: Any) -> bool:
    messages = list(getattr(snapshot, "messages", []))
    if not messages or any(enum_value(getattr(message, "kind", None)) == "pending_llm_sampling" for message in messages):
        return False
    terminal = messages[-1]
    return enum_value(getattr(terminal, "kind", None)) == "assistant" and not bool(
        getattr(terminal, "refusal", None)
    )


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest().upper()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")
