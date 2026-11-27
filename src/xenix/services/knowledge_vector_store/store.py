from __future__ import annotations

import gc
import math
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from uuid import uuid4

from ...config import AppPaths
from ...exceptions import report_exception
from ..storage.layout import (
    knowledge_indexes_root,
    knowledge_root,
    knowledge_staging_root,
)
from .contracts import (
    TABLE_NAME,
    TRASH_DIRECTORY_NAME,
    TRASH_TOKEN_PATTERN,
    VECTOR_STAGE_PREFIX,
    KnowledgeVectorGenerationState,
    KnowledgeVectorRecord,
    KnowledgeVectorStoreError,
    lifecycle_for,
)
from .filesystem import (
    assert_within,
    discard_exception_traceback,
    is_link_like,
    remove_path_with_retries,
    replace_with_retries,
)
from .manifest import (
    manifest_payload,
    read_manifest,
    unit_ids_digest,
    validate_generation_id,
    validated_fingerprint,
    validated_positive_int,
    validated_records,
    validated_unit_ids,
    validated_vector,
    write_manifest,
)


class LanceKnowledgeVectorStore:
    """Operation-scoped LanceDB adapter for immutable Knowledge generations."""

    def __init__(self, paths: AppPaths) -> None:
        self._knowledge_root = knowledge_root(paths)
        self._indexes_root = knowledge_indexes_root(paths)
        self._staging_root = knowledge_staging_root(paths)
        self._trash_root = self._indexes_root / TRASH_DIRECTORY_NAME
        self._lifecycle = lifecycle_for(self._knowledge_root)

    @contextmanager
    def lifecycle(self) -> Iterator[None]:
        """Serialize in-process vector publication, use, and reclamation per home."""

        with self._lifecycle.hold():
            self._validate_storage_topology()
            yield

    def write_generation(
        self,
        *,
        generation_id: int,
        records: Sequence[KnowledgeVectorRecord],
        dimensions: int,
        corpus_fingerprint: str,
        profile_fingerprint: str,
    ) -> str:
        with self.lifecycle():
            return self._write_generation(
                generation_id=generation_id,
                records=records,
                dimensions=dimensions,
                corpus_fingerprint=corpus_fingerprint,
                profile_fingerprint=profile_fingerprint,
            )

    def _write_generation(
        self,
        *,
        generation_id: int,
        records: Sequence[KnowledgeVectorRecord],
        dimensions: int,
        corpus_fingerprint: str,
        profile_fingerprint: str,
    ) -> str:
        validate_generation_id(generation_id)
        corpus_fingerprint = validated_fingerprint(corpus_fingerprint)
        profile_fingerprint = validated_fingerprint(profile_fingerprint)
        dimensions = validated_positive_int(dimensions)
        normalized = validated_records(records, dimensions=dimensions)
        unit_ids = [record.unit_id for record in normalized]
        stage = self._staging_root / f"vector-{generation_id}"
        final = self._indexes_root / str(generation_id)
        stage_created = False
        try:
            assert_within(stage, self._staging_root)
            assert_within(final, self._indexes_root)
            if (
                stage.exists()
                or is_link_like(stage)
                or final.exists()
                or is_link_like(final)
            ):
                raise KnowledgeVectorStoreError()
            self._staging_root.mkdir(parents=True, exist_ok=True)
            self._indexes_root.mkdir(parents=True, exist_ok=True)
            self._validate_storage_topology()
            stage.mkdir(parents=False)
            stage_created = True
            self._write_lance_table(stage, normalized, dimensions=dimensions)
            write_manifest(
                stage,
                generation_id=generation_id,
                corpus_fingerprint=corpus_fingerprint,
                profile_fingerprint=profile_fingerprint,
                dimensions=dimensions,
                unit_ids=unit_ids,
            )
            if not self._generation_matches(
                stage,
                expected_manifest=manifest_payload(
                    generation_id=generation_id,
                    corpus_fingerprint=corpus_fingerprint,
                    profile_fingerprint=profile_fingerprint,
                    dimensions=dimensions,
                    unit_ids=unit_ids,
                ),
                expected_unit_ids=unit_ids,
            ):
                raise KnowledgeVectorStoreError()
            if not replace_with_retries(stage, final):
                raise KnowledgeVectorStoreError()
        except Exception as exc:
            if stage_created:
                try:
                    self._remove_staging_tree(stage)
                except Exception:
                    raise KnowledgeVectorStoreError() from None
            if isinstance(exc, KnowledgeVectorStoreError):
                raise
            raise KnowledgeVectorStoreError() from None
        return final.relative_to(self._knowledge_root).as_posix()

    def generation_is_usable(
        self,
        relative_path: str,
        *,
        expected_generation_id: int,
        expected_corpus_fingerprint: str,
        expected_profile_fingerprint: str,
        expected_unit_ids: Sequence[int],
        expected_count: int,
        expected_dimensions: int,
    ) -> bool:
        with self.lifecycle():
            return self._generation_is_usable(
                relative_path,
                expected_generation_id=expected_generation_id,
                expected_corpus_fingerprint=expected_corpus_fingerprint,
                expected_profile_fingerprint=expected_profile_fingerprint,
                expected_unit_ids=expected_unit_ids,
                expected_count=expected_count,
                expected_dimensions=expected_dimensions,
            )

    def _generation_is_usable(
        self,
        relative_path: str,
        *,
        expected_generation_id: int,
        expected_corpus_fingerprint: str,
        expected_profile_fingerprint: str,
        expected_unit_ids: Sequence[int],
        expected_count: int,
        expected_dimensions: int,
    ) -> bool:
        try:
            validate_generation_id(expected_generation_id)
            expected_corpus_fingerprint = validated_fingerprint(expected_corpus_fingerprint)
            expected_profile_fingerprint = validated_fingerprint(expected_profile_fingerprint)
            expected_count = validated_positive_int(expected_count)
            expected_dimensions = validated_positive_int(expected_dimensions)
            unit_ids = validated_unit_ids(expected_unit_ids)
            if len(unit_ids) != expected_count:
                return False
            expected_relative_path = f"indexes/{expected_generation_id}"
            if relative_path != expected_relative_path:
                return False
            path = self._resolve_generation_path(relative_path)
            return self._generation_matches(
                path,
                expected_manifest=manifest_payload(
                    generation_id=expected_generation_id,
                    corpus_fingerprint=expected_corpus_fingerprint,
                    profile_fingerprint=expected_profile_fingerprint,
                    dimensions=expected_dimensions,
                    unit_ids=unit_ids,
                ),
                expected_unit_ids=unit_ids,
            )
        except Exception as exc:
            report_exception(exc)
            return False

    def search(
        self,
        relative_path: str,
        *,
        query_vector: Sequence[float],
        limit: int,
    ) -> list[int]:
        with self.lifecycle():
            return self._search(
                relative_path,
                query_vector=query_vector,
                limit=limit,
            )

    def _search(
        self,
        relative_path: str,
        *,
        query_vector: Sequence[float],
        limit: int,
    ) -> list[int]:
        if limit < 1:
            raise KnowledgeVectorStoreError()
        vector = validated_vector(query_vector)
        database = None
        table = None
        query = None
        result = None
        unit_id_column = None
        failed = False
        unit_ids: list[int] = []
        try:
            import lancedb

            path = self._resolve_generation_path(relative_path)
            database = lancedb.connect(str(path))
            table = database.open_table(TABLE_NAME)
            query = table.search(list(vector))
            query = query.distance_type("cosine")
            query = query.select(["unit_id", "_distance"])
            query = query.limit(limit)
            result = query.to_arrow()
            unit_id_column = result.column("unit_id")
            unit_ids = [int(value) for value in unit_id_column.to_pylist()]
        except Exception as exc:
            failed = True
            discard_exception_traceback(exc)
        finally:
            unit_id_column = None
            result = None
            query = None
            table = None
            database = None
            gc.collect()
        if failed:
            raise KnowledgeVectorStoreError() from None
        return unit_ids

    def inspect_generation(
        self,
        relative_path: str,
        *,
        expected_generation_id: int,
        expected_corpus_fingerprint: str,
        expected_profile_fingerprint: str,
        expected_count: int,
        expected_dimensions: int,
    ) -> KnowledgeVectorGenerationState:
        """Inspect one metadata-bound projection without trusting its stored path."""

        with self.lifecycle():
            try:
                path = self._strict_generation_path(
                    relative_path,
                    expected_generation_id=expected_generation_id,
                )
            except KnowledgeVectorStoreError:
                return KnowledgeVectorGenerationState.UNSAFE
            if is_link_like(path):
                return KnowledgeVectorGenerationState.UNSAFE
            if not path.exists():
                return KnowledgeVectorGenerationState.MISSING
            if not path.is_dir():
                return KnowledgeVectorGenerationState.CORRUPT
            try:
                matches = self._generation_matches_metadata(
                    path,
                    expected_generation_id=expected_generation_id,
                    expected_corpus_fingerprint=expected_corpus_fingerprint,
                    expected_profile_fingerprint=expected_profile_fingerprint,
                    expected_count=expected_count,
                    expected_dimensions=expected_dimensions,
                )
            except Exception as exc:
                report_exception(exc)
                return KnowledgeVectorGenerationState.CORRUPT
            return (
                KnowledgeVectorGenerationState.USABLE
                if matches
                else KnowledgeVectorGenerationState.CORRUPT
            )

    def list_definite_generation_paths(self) -> tuple[str, ...]:
        """List final directories whose bounded manifest proves vector provenance."""

        with self.lifecycle():
            if not self._indexes_root.is_dir():
                return ()
            entries: list[str] = []
            try:
                children = tuple(self._indexes_root.iterdir())
            except OSError as exc:
                raise KnowledgeVectorStoreError() from exc
            for child in children:
                if child.name == TRASH_DIRECTORY_NAME or is_link_like(child):
                    continue
                try:
                    validate_generation_id(child.name)
                except KnowledgeVectorStoreError:
                    continue
                if not child.is_dir():
                    continue
                try:
                    manifest = read_manifest(child)
                except (KnowledgeVectorStoreError, OSError):
                    continue
                if str(manifest["generation_id"]) == child.name:
                    entries.append(f"indexes/{child.name}")
            return tuple(sorted(entries))

    def quarantine_generation(
        self,
        relative_path: str,
        *,
        expected_generation_id: int,
    ) -> str | None:
        """Atomically detach one exact vector path into same-volume private trash."""

        with self.lifecycle():
            path = self._strict_generation_path(
                relative_path,
                expected_generation_id=expected_generation_id,
            )
            if is_link_like(path):
                raise KnowledgeVectorStoreError()
            if not path.exists():
                return None
            return self._quarantine_path(
                path,
                owned_root=self._indexes_root,
                kind="generation",
                identity=expected_generation_id,
            )

    def discard_unpublished_generation(
        self,
        relative_path: str,
        *,
        expected_generation_id: int,
    ) -> bool:
        """Best-effort reclamation for a final directory with no metadata row."""

        with self.lifecycle():
            try:
                token = self.quarantine_generation(
                    relative_path,
                    expected_generation_id=expected_generation_id,
                )
            except KnowledgeVectorStoreError:
                return False
            return token is None or self.delete_quarantined(token)

    def quarantine_stale_vector_staging(
        self,
        *,
        stale_before: float,
    ) -> tuple[str, ...]:
        """Detach only old, direct ``vector-<id>`` staging directories."""

        if not math.isfinite(stale_before):
            raise KnowledgeVectorStoreError()
        with self.lifecycle():
            if not self._staging_root.is_dir():
                return ()
            try:
                children = tuple(self._staging_root.iterdir())
            except OSError as exc:
                raise KnowledgeVectorStoreError() from exc
            tokens: list[str] = []
            for child in children:
                if (
                    not child.name.startswith(VECTOR_STAGE_PREFIX)
                    or is_link_like(child)
                ):
                    continue
                generation_id = child.name.removeprefix(VECTOR_STAGE_PREFIX)
                try:
                    validate_generation_id(generation_id)
                    if not child.is_dir() or child.stat().st_mtime > stale_before:
                        continue
                    token = self._quarantine_path(
                        child,
                        owned_root=self._staging_root,
                        kind="stage",
                        identity=generation_id,
                    )
                except (KnowledgeVectorStoreError, OSError):
                    continue
                tokens.append(token)
            return tuple(tokens)

    def list_quarantined(self) -> tuple[str, ...]:
        with self.lifecycle():
            if is_link_like(self._trash_root) or not self._trash_root.is_dir():
                return ()
            try:
                assert_within(self._trash_root, self._indexes_root)
                children = tuple(self._trash_root.iterdir())
            except (KnowledgeVectorStoreError, OSError):
                return ()
            return tuple(
                sorted(
                    child.name
                    for child in children
                    if TRASH_TOKEN_PATTERN.fullmatch(child.name)
                    and not is_link_like(child)
                )
            )

    def delete_quarantined(self, token: str) -> bool:
        """Best-effort deletion; a sharing violation leaves private trash retryable."""

        if not TRASH_TOKEN_PATTERN.fullmatch(str(token)):
            raise KnowledgeVectorStoreError()
        with self.lifecycle():
            if is_link_like(self._trash_root):
                return False
            path = self._trash_root / token
            try:
                assert_within(self._trash_root, self._indexes_root)
                assert_within(path, self._trash_root)
            except KnowledgeVectorStoreError:
                return False
            return remove_path_with_retries(path, best_effort=True)

    def _write_lance_table(
        self,
        path: Path,
        records: Sequence[KnowledgeVectorRecord],
        *,
        dimensions: int,
    ) -> None:
        schema = None
        payload = None
        database = None
        table = None
        failed = False
        try:
            import lancedb
            import pyarrow as pa

            schema = pa.schema(
                [
                    pa.field("unit_id", pa.int64(), nullable=False),
                    pa.field(
                        "vector",
                        pa.list_(pa.float32(), dimensions),
                        nullable=False,
                    ),
                ]
            )
            payload = pa.Table.from_pylist(
                [
                    {"unit_id": record.unit_id, "vector": list(record.vector)}
                    for record in records
                ],
                schema=schema,
            )
            database = lancedb.connect(str(path))
            table = database.create_table(TABLE_NAME, data=payload, mode="create")
            if table.count_rows() != len(records):
                raise KnowledgeVectorStoreError()
        except Exception as exc:
            failed = True
            discard_exception_traceback(exc)
        finally:
            table = None
            database = None
            payload = None
            schema = None
            gc.collect()
        if failed:
            raise KnowledgeVectorStoreError() from None

    def _generation_matches(
        self,
        path: Path,
        *,
        expected_manifest: dict[str, object],
        expected_unit_ids: Sequence[int],
    ) -> bool:
        if not path.is_dir():
            return False
        if read_manifest(path) != expected_manifest:
            return False
        return self._read_generation_unit_ids(
            path,
            expected_count=int(expected_manifest["unit_count"]),
            expected_dimensions=int(expected_manifest["dimensions"]),
        ) == list(expected_unit_ids)

    def _generation_matches_metadata(
        self,
        path: Path,
        *,
        expected_generation_id: int,
        expected_corpus_fingerprint: str,
        expected_profile_fingerprint: str,
        expected_count: int,
        expected_dimensions: int,
    ) -> bool:
        validate_generation_id(expected_generation_id)
        expected_corpus_fingerprint = validated_fingerprint(expected_corpus_fingerprint)
        expected_profile_fingerprint = validated_fingerprint(expected_profile_fingerprint)
        expected_count = validated_positive_int(expected_count)
        expected_dimensions = validated_positive_int(expected_dimensions)
        manifest = read_manifest(path)
        if (
            manifest["generation_id"] != expected_generation_id
            or manifest["corpus_fingerprint"] != expected_corpus_fingerprint
            or manifest["profile_fingerprint"] != expected_profile_fingerprint
            or manifest["unit_count"] != expected_count
            or manifest["dimensions"] != expected_dimensions
        ):
            return False
        unit_ids = self._read_generation_unit_ids(
            path,
            expected_count=expected_count,
            expected_dimensions=expected_dimensions,
        )
        return manifest["unit_ids_sha256"] == unit_ids_digest(unit_ids)

    def _read_generation_unit_ids(
        self,
        path: Path,
        *,
        expected_count: int,
        expected_dimensions: int,
    ) -> list[int]:
        database = None
        table = None
        schema = None
        vector_type = None
        query = None
        payload = None
        unit_id_column = None
        failed = False
        actual_unit_ids: list[int] = []
        try:
            import lancedb

            database = lancedb.connect(str(path))
            table = database.open_table(TABLE_NAME)
            schema = table.schema
            vector_type = schema.field("vector").type
            if (
                table.count_rows() != expected_count
                or getattr(vector_type, "list_size", None) != expected_dimensions
            ):
                raise KnowledgeVectorStoreError()
            else:
                query = table.search()
                query = query.select(["unit_id"])
                query = query.limit(expected_count + 1)
                payload = query.to_arrow()
                unit_id_column = payload.column("unit_id")
                actual_unit_ids = [int(value) for value in unit_id_column.to_pylist()]
                if len(actual_unit_ids) != expected_count:
                    raise KnowledgeVectorStoreError()
                actual_unit_ids = validated_unit_ids(actual_unit_ids)
        except Exception as exc:
            failed = True
            discard_exception_traceback(exc)
        finally:
            unit_id_column = None
            payload = None
            query = None
            vector_type = None
            schema = None
            table = None
            database = None
            gc.collect()
        if failed:
            raise KnowledgeVectorStoreError() from None
        return actual_unit_ids

    def _resolve_generation_path(self, value: str) -> Path:
        if type(value) is not str:
            raise KnowledgeVectorStoreError()
        relative = PurePosixPath(value)
        if (
            not value
            or value != relative.as_posix()
            or relative.is_absolute()
            or ".." in relative.parts
            or len(relative.parts) != 2
            or relative.parts[0] != "indexes"
        ):
            raise KnowledgeVectorStoreError()
        validate_generation_id(relative.parts[1])
        path = self._knowledge_root.joinpath(*relative.parts)
        if is_link_like(path):
            raise KnowledgeVectorStoreError()
        assert_within(path, self._indexes_root)
        return path

    def _strict_generation_path(
        self,
        value: str,
        *,
        expected_generation_id: int,
    ) -> Path:
        validate_generation_id(expected_generation_id)
        if value != f"indexes/{expected_generation_id}":
            raise KnowledgeVectorStoreError()
        return self._resolve_generation_path(value)

    def _validate_storage_topology(self) -> None:
        try:
            resolved_knowledge_root = self._knowledge_root.resolve()
            expected_roots = (
                (self._indexes_root, resolved_knowledge_root / "indexes"),
                (self._staging_root, resolved_knowledge_root / "staging"),
                (
                    self._trash_root,
                    resolved_knowledge_root / "indexes" / TRASH_DIRECTORY_NAME,
                ),
            )
            for path, expected in expected_roots:
                if (
                    is_link_like(path)
                    or path.resolve() != expected
                    or (path.exists() and not path.is_dir())
                ):
                    raise KnowledgeVectorStoreError()
        except KnowledgeVectorStoreError:
            raise
        except (OSError, RuntimeError) as exc:
            raise KnowledgeVectorStoreError() from exc

    def _quarantine_path(
        self,
        path: Path,
        *,
        owned_root: Path,
        kind: str,
        identity: int | str,
    ) -> str:
        if kind not in {"generation", "stage"}:
            raise KnowledgeVectorStoreError()
        validate_generation_id(identity)
        if is_link_like(path):
            raise KnowledgeVectorStoreError()
        assert_within(path, owned_root)
        try:
            self._indexes_root.mkdir(parents=True, exist_ok=True)
            self._trash_root.mkdir(parents=False, exist_ok=True)
        except OSError as exc:
            raise KnowledgeVectorStoreError() from exc
        self._validate_storage_topology()
        if is_link_like(self._trash_root) or not self._trash_root.is_dir():
            raise KnowledgeVectorStoreError()
        assert_within(self._trash_root, self._indexes_root)
        token = f"vector-{kind}-{identity}-{uuid4().hex}"
        target = self._trash_root / token
        assert_within(target, self._trash_root)
        if not replace_with_retries(path, target):
            raise KnowledgeVectorStoreError()
        return token

    def _remove_staging_tree(self, path: Path) -> None:
        assert_within(path, self._staging_root)
        remove_path_with_retries(path, best_effort=False)
