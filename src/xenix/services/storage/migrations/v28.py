"""Replace application-owned string identities without retaining an alias table.

The source table definitions are preserved except for identity column types.
This edge is intentionally independent of the current ORM schema. Managed files
are copied to their new locations before SQLite publishes the new references;
original bytes remain available if the database transaction fails.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any

from sqlalchemy.engine import Engine
import zstandard


_TABLES = (
    "project", "dataset", "dataset_import", "dataset_workbook",
    "dataset_derivation", "dataset_derivation_input", "dataset_column_binding",
    "ml_task", "job", "ml_task_artifact", "conversation_thread",
    "conversation_message", "artifact", "knowledge_document", "knowledge_unit",
    "knowledge_vector_generation", "knowledge_index_task", "knowledge_import",
    "knowledge_canonical_generation", "knowledge_derivation", "trained_model",
)
_IDENTITIES = frozenset({
    "id", "project_id", "dataset_id", "import_id", "workbook_id", "copied_from",
    "derived_from_dataset_id", "ml_task_id", "derivation_dataset_id",
    "input_dataset_id", "tool_call_message_id", "thread_id", "artifact_id",
    "source_artifact_id", "canonical_generation_id", "retrieval_generation_id",
    "document_id", "vector_generation_id", "retry_of", "planned_document_id",
})
_TOKEN = re.compile(r"[A-Za-z0-9_-]+")
_PATH = re.compile(r"^(?:[A-Za-z]:[/\\]|/|objects/|indexes/)")


class _References:
    def __init__(self) -> None:
        self.ids: dict[str, int] = {}
        self.paths: dict[str, str] = {}
        self.digests: dict[str, str] = {}

    def identity(self, value: str | None) -> int | None:
        if value is None:
            return None
        if value not in self.ids:
            self.ids[value] = len(self.ids) + 1
        return self.ids[value]

    def rewrite(self, value: Any) -> Any:
        if isinstance(value, dict):
            rewritten = {str(self.rewrite(key)): self.rewrite(item) for key, item in value.items()}
            if {"dataset_id", "source_sha256", "source_byte_size", "schema_digest"} <= value.keys():
                # Preserve the historical sampling seed while references change.
                snapshot = {"schema_version": 1, **value}
                encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                rewritten["sampling_fingerprint"] = value.get("sampling_fingerprint") or hashlib.sha256(encoded).hexdigest()
            return rewritten
        if isinstance(value, list):
            return [self.rewrite(item) for item in value]
        if not isinstance(value, str):
            return value
        if value in self.ids:
            return self.ids[value]
        if value in self.digests:
            return self.digests[value]
        for old, new in self.paths.items():
            value = value.replace(old, new)
        # Registered source/model files keep their stored path. Only directories
        # located by identity (task roots) and copied bundles move above.
        if _PATH.match(value):
            return value
        return _TOKEN.sub(lambda match: str(self.ids.get(match[0], match[0])), value)


def migrate_v27_to_v28(engine: Engine) -> int:
    refs = _References()
    journals: list[tuple[Path, bytes]] = []
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        try:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            schema = connection.exec_driver_sql(
                "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql IS NOT NULL"
            ).all()
            definitions = {name: sql for kind, name, _, sql in schema if kind == "table"}
            tables = [table for table in _TABLES if table in definitions]
            rows = {
                table: [dict(row) for row in connection.exec_driver_sql(f'SELECT * FROM "{table}"').mappings()]
                for table in tables
            }
            identity_columns: dict[str, set[str]] = {}
            for table in tables:
                columns = connection.exec_driver_sql(f'PRAGMA table_info("{table}")').all()
                identity_columns[table] = {
                    column[1] for column in columns
                    if column[1] in _IDENTITIES or (table == "job" and column[1] == "reference")
                }
                for row in rows[table]:
                    for column in sorted(identity_columns[table]):
                        refs.identity(row[column])

            runtime = Path(str(engine.url.database)).resolve().parent.parent
            _copy_managed_files(runtime, rows, refs)
            _rewrite_usage_journals(runtime, refs, journals)

            for table in tables:
                temporary = f"integer_{table}"
                sql = re.sub(r'CREATE TABLE\s+(?:"[^"]+"|\w+)', f'CREATE TABLE "{temporary}"', definitions[table], count=1, flags=re.I)
                for column in identity_columns[table]:
                    sql = re.sub(rf'(\b{column}\b"?\s+)VARCHAR(?:\(\d+\))?', r'\1INTEGER', sql, flags=re.I)
                connection.exec_driver_sql(sql)
                columns = [column[1] for column in connection.exec_driver_sql(f'PRAGMA table_info("{table}")')]
                json_columns = {
                    column[1] for column in connection.exec_driver_sql(f'PRAGMA table_info("{table}")')
                    if column[2].upper() == "JSON"
                }
                for row in rows[table]:
                    converted = []
                    for column in columns:
                        value = row[column]
                        if column in identity_columns[table]:
                            value = refs.identity(value)
                        elif column in json_columns and value is not None:
                            value = json.dumps(refs.rewrite(json.loads(value)), ensure_ascii=False)
                        elif isinstance(value, str) and column not in {"client_submission_id", "provider_call_id", "scope_fingerprint"}:
                            value = refs.rewrite(value)
                        converted.append(value)
                    quoted = ', '.join(f'"{column}"' for column in columns)
                    placeholders = ', '.join('?' for _ in columns)
                    connection.exec_driver_sql(f'INSERT INTO "{temporary}" ({quoted}) VALUES ({placeholders})', tuple(converted))
            for table in tables:
                connection.exec_driver_sql(f'DROP TABLE "{table}"')
            for table in tables:
                connection.exec_driver_sql(f'ALTER TABLE "integer_{table}" RENAME TO "{table}"')
            for kind, _, owner, sql in schema:
                if kind in {"index", "trigger"} and owner in tables:
                    connection.exec_driver_sql(sql)
            if "knowledge_unit_fts" in definitions:
                connection.exec_driver_sql("DELETE FROM knowledge_unit_fts")
                connection.exec_driver_sql(
                    "INSERT INTO knowledge_unit_fts(unit_id, title, search_text) "
                    "SELECT u.id, d.title, u.search_text FROM knowledge_unit u "
                    "JOIN knowledge_document d ON d.id=u.document_id"
                )
            if "knowledge_vector_generation" in tables:
                # Unit identities changed; vectors are rebuilt from retained text.
                connection.exec_driver_sql("UPDATE knowledge_vector_generation SET corpus_fingerprint_schema=0")
            connection.exec_driver_sql(
                "CREATE TABLE object_id_sequence (singleton INTEGER PRIMARY KEY, last_id INTEGER NOT NULL)"
            )
            connection.exec_driver_sql("INSERT INTO object_id_sequence VALUES (1, ?)", (len(refs.ids),))
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
            if violations:
                raise ValueError(f"Integer identity migration found invalid relationships: {violations[:5]}")
            connection.exec_driver_sql("PRAGMA user_version=28")
            connection.commit()
        except Exception:
            connection.rollback()
            for path, original in journals:
                _replace_file(path, original)
            raise
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
    return 28


def _replace_file(path: Path, data: bytes) -> None:
    staged = path.with_name(path.name + ".integer-v28.tmp")
    staged.write_bytes(data)
    os.replace(staged, path)


def _rewrite_usage_journals(runtime: Path, refs: _References, originals: list[tuple[Path, bytes]]) -> None:
    def key(value: str | int) -> str:
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]

    hashes = {key(old): key(new) for old, new in refs.ids.items()}
    for suffix in ("", ".1", ".2", ".3"):
        path = runtime / "logs" / f"llm-usage.jsonl{suffix}"
        if not path.is_file():
            continue
        original = path.read_bytes()
        # Only known correlation hashes change; all counts and record bytes
        # otherwise retain their historical representation.
        updated = re.sub(
            rb'"(?:thread_key|root_user_key|frontier_key|sampling_key)":"([0-9a-f]{16})"',
            lambda match: match[0].replace(match[1], hashes.get(match[1].decode(), match[1].decode()).encode()),
            original,
        )
        if updated != original:
            originals.append((path, original))
            _replace_file(path, updated)


def _copy_managed_files(runtime: Path, rows: dict[str, list[dict[str, Any]]], refs: _References) -> None:
    roots = (
        ("ml_task", runtime / "artifacts" / "ml-tasks"),
        ("dataset", runtime / "artifacts" / "models" / "datasets"),
        ("dataset", runtime / "artifacts" / "apply" / "datasets"),
        ("knowledge_import", runtime / "artifacts" / "knowledge" / "tasks" / "imports"),
        ("knowledge_vector_generation", runtime / "artifacts" / "knowledge" / "indexes"),
    )
    copied: list[Path] = []
    for table, root in roots:
        for row in rows.get(table, []):
            old = root / row["id"]
            new = root / str(refs.ids[row["id"]])
            for old_text, new_text in ((str(old), str(new)), (old.as_posix(), new.as_posix())):
                refs.paths[old_text] = new_text
            if table == "knowledge_vector_generation":
                refs.paths[f'indexes/{row["id"]}'] = f'indexes/{refs.ids[row["id"]]}'
            if old.is_dir():
                shutil.copytree(old, new, dirs_exist_ok=True)
                copied.append(new)
    _copy_canonical_bundles(runtime, rows, refs)
    _copy_page_cache(runtime, refs)
    for root in copied:
        for path in root.rglob("*text_*.joblib"):
            _rewrite_text_model(path, refs)
        for path in root.rglob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            path.write_text(json.dumps(refs.rewrite(payload), ensure_ascii=False), encoding="utf-8")


def _rewrite_text_model(path: Path, refs: _References) -> None:
    # Only copied Xenix text analyzers retain Dataset references in the model.
    # Vocabulary, learned weights and historical preparation digests stay intact.
    import joblib

    analyzer = joblib.load(path)
    preparer = getattr(analyzer, "preparer", None)
    if preparer is None:
        return
    specification = preparer.specification
    payload = specification.model_dump(mode="json", warnings=False)
    rewritten = refs.rewrite(payload)
    if rewritten != payload:
        preparer.specification = type(specification).model_validate(rewritten)
        joblib.dump(analyzer, path)


def _copy_page_cache(runtime: Path, refs: _References) -> None:
    root = runtime / "state" / "paged_results"
    pages = []
    for path in root.glob("*.meta.json"):
        old_id = path.name.removesuffix(".meta.json")
        if not re.fullmatch(r"[0-9a-f]{32}", old_id):
            continue
        metadata = json.loads(path.read_text(encoding="utf-8"))
        call_id = metadata.get("tool_call_message_id")
        refs.ids[old_id] = refs.identity(call_id) if call_id else refs.identity(old_id)
        pages.append((old_id, metadata))
    for old_id, metadata in pages:
        text_path = root / f"{old_id}.txt"
        if not text_path.is_file():
            continue
        new_id = refs.ids[old_id]
        (root / f"{new_id}.txt").write_text(
            str(refs.rewrite(text_path.read_text(encoding="utf-8"))), encoding="utf-8",
        )
        (root / f"{new_id}.meta.json").write_text(
            json.dumps(refs.rewrite(metadata), ensure_ascii=False), encoding="utf-8",
        )


def _copy_canonical_bundles(runtime: Path, rows: dict[str, list[dict[str, Any]]], refs: _References) -> None:
    root = runtime / "artifacts" / "knowledge"
    for row in rows.get("knowledge_canonical_generation", []):
        relative = row["relative_path"]
        old = root / relative
        manifest_path = old / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        envelope_path = old / manifest["envelope_file"]
        decoded = zstandard.ZstdDecompressor().decompress(envelope_path.read_bytes())
        if hashlib.sha256(decoded).hexdigest() != row["envelope_sha256"]:
            raise ValueError(f"Canonical envelope for {row['id']} has changed before migration.")
        envelope = refs.rewrite(json.loads(decoded))
        encoded = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        new_relative = f"objects/canonical/{digest[:2]}/{digest[2:4]}/{digest}"
        new = root / new_relative
        shutil.copytree(old, new, dirs_exist_ok=True)
        (new / manifest["envelope_file"]).write_bytes(zstandard.ZstdCompressor(level=7, write_checksum=True).compress(encoded))
        manifest["envelope_sha256"] = digest
        (new / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        refs.paths[relative] = new_relative
        refs.digests[row["envelope_sha256"]] = digest
