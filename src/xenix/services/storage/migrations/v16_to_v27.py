from __future__ import annotations

from sqlalchemy.engine import Engine

from ....exceptions import ValidationError
from ._helpers import _table_columns, _table_names


def _require_knowledge_source_shape(connection, version: int) -> None:
    """Reject incomplete databases before advancing a deployed Knowledge edge."""

    required: dict[str, set[str]] = {
        "conversation_thread": {
            "id",
            "title",
            "system_prompt",
            "selected_fq_model_key",
            "created_at",
            "updated_at",
        },
        "conversation_message": {
            "id",
            "thread_id",
            "sequence_index",
            "kind",
            "content_payload",
            "created_at",
        },
        "artifact": {
            "id",
            "kind",
            "title",
            "absolute_path",
            "metadata_payload",
            "ready_to_open",
            "created_at",
        },
    }
    if version >= 16:
        required.update(
            {
                "knowledge_document": {
                    "id",
                    "library_id",
                    "title",
                    "source_artifact_id",
                    "canonical_generation_id",
                    "active",
                    "created_at",
                    "updated_at",
                },
                "knowledge_unit": {
                    "id",
                    "document_id",
                    "canonical_generation_id",
                    "ordinal",
                    "text",
                    "search_text",
                    "locator_payload",
                    "created_at",
                },
                "knowledge_unit_fts": {"unit_id", "title", "search_text"},
                "knowledge_import": {
                    "id",
                    "library_id",
                    "original_file_name",
                    "source_format",
                    "source_sha256",
                    "status",
                    "document_id",
                    "source_artifact_id",
                    "canonical_path",
                    "reused_existing",
                    "error_code",
                    "error_summary",
                    "created_at",
                    "updated_at",
                },
            }
        )
    if version >= 17:
        required["knowledge_document"].update(
            {"source_sha256", "source_format", "canonical_path"}
        )
    if version >= 18:
        required["knowledge_vector_generation"] = {
            "id",
            "library_id",
            "corpus_fingerprint",
            "profile_fingerprint",
            "provider_key",
            "model",
            "dimensions",
            "distance_metric",
            "relative_path",
            "unit_count",
            "created_at",
        }
    if version >= 19:
        required["knowledge_document"].update(
            {"retrieval_generation_id", "retrieval_status"}
        )
        required["knowledge_import"].update(
            {
                "phase",
                "attempt_number",
                "retry_of",
                "planned_document_id",
                "canonical_generation_id",
                "envelope_sha256",
                "content_ir_sha256",
                "retryable",
                "cancel_requested",
            }
        )
        required["knowledge_canonical_generation"] = {
            "id",
            "document_id",
            "import_id",
            "source_artifact_id",
            "library_id",
            "source_sha256",
            "source_format",
            "media_type",
            "display_name",
            "envelope_sha256",
            "content_ir_sha256",
            "relative_path",
            "schema_version",
            "pipeline_payload",
            "warnings_payload",
            "compatibility_state",
            "created_at",
        }
        required["knowledge_derivation"] = {
            "id",
            "document_id",
            "canonical_generation_id",
            "import_id",
            "status",
            "phase",
            "attempt_number",
            "retry_of",
            "error_code",
            "error_summary",
            "retryable",
            "created_at",
            "updated_at",
        }
    if version >= 21:
        required["knowledge_index_task"] = {
            "id",
            "library_id",
            "index_kinds_payload",
            "trigger",
            "status",
            "phase",
            "profile_fingerprint",
            "corpus_fingerprint",
            "vector_generation_id",
            "error_code",
            "error_summary",
            "created_at",
            "updated_at",
        }
    if version >= 22:
        required["knowledge_document"].update(
            {
                "retrieval_projection_version",
                "retrieval_content_fingerprint",
                "retrieval_unit_count",
            }
        )
        required["knowledge_vector_generation"].add(
            "corpus_fingerprint_schema"
        )

    tables = _table_names(connection)
    missing_tables = sorted(set(required) - tables)
    if missing_tables:
        raise ValidationError(
            f"Unsupported v{version} database: missing required tables "
            + ", ".join(missing_tables)
        )
    for table_name, columns in required.items():
        missing_columns = sorted(columns - _table_columns(connection, table_name))
        if missing_columns:
            raise ValidationError(
                f"Unsupported v{version} database: {table_name} is missing columns "
                + ", ".join(missing_columns)
            )


def _ensure_v16_knowledge_fts(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_unit_fts USING fts5("
            "unit_id UNINDEXED, title, search_text, tokenize='unicode61')"
        )


def migrate_v15_to_v16(engine: Engine) -> int:
    with engine.begin() as connection:
        _require_knowledge_source_shape(connection, 15)
        _create_v16_knowledge_schema(connection)
        connection.exec_driver_sql("PRAGMA user_version=16")
    return 16


def migrate_v16_to_v17(engine: Engine) -> int:
    with engine.begin() as connection:
        _require_knowledge_source_shape(connection, 16)
        columns = {str(row[1]) for row in connection.exec_driver_sql("PRAGMA table_info(knowledge_document)")}
        if "source_sha256" not in columns:
            connection.exec_driver_sql("ALTER TABLE knowledge_document ADD COLUMN source_sha256 VARCHAR")
        if "source_format" not in columns:
            connection.exec_driver_sql("ALTER TABLE knowledge_document ADD COLUMN source_format VARCHAR")
        if "canonical_path" not in columns:
            connection.exec_driver_sql("ALTER TABLE knowledge_document ADD COLUMN canonical_path VARCHAR")
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_document_source_sha256 "
            "ON knowledge_document (source_sha256)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_document_source_format "
            "ON knowledge_document (source_format)"
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_document_library_source_sha256 "
            "ON knowledge_document (library_id, source_sha256)"
        )
        connection.exec_driver_sql("PRAGMA user_version=17")
    return 17


def migrate_v17_to_v18(engine: Engine) -> int:
    with engine.begin() as connection:
        _require_knowledge_source_shape(connection, 17)
        connection.exec_driver_sql(
            """
            CREATE TABLE knowledge_vector_generation (
                id VARCHAR NOT NULL PRIMARY KEY,
                library_id VARCHAR NOT NULL,
                corpus_fingerprint VARCHAR NOT NULL,
                profile_fingerprint VARCHAR NOT NULL,
                provider_key VARCHAR NOT NULL,
                model VARCHAR NOT NULL,
                dimensions INTEGER NOT NULL,
                distance_metric VARCHAR NOT NULL,
                relative_path VARCHAR NOT NULL,
                unit_count INTEGER NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_knowledge_vector_generation_library_id "
            "ON knowledge_vector_generation (library_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_knowledge_vector_generation_corpus_fingerprint "
            "ON knowledge_vector_generation (corpus_fingerprint)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_knowledge_vector_generation_profile_fingerprint "
            "ON knowledge_vector_generation (profile_fingerprint)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_knowledge_vector_generation_lookup "
            "ON knowledge_vector_generation "
            "(library_id, profile_fingerprint, corpus_fingerprint, created_at)"
        )
        connection.exec_driver_sql("PRAGMA user_version=18")
    return 18


def migrate_v18_to_v19(engine: Engine) -> int:
    with engine.begin() as connection:
        _require_knowledge_source_shape(connection, 18)

        connection.exec_driver_sql(
            "ALTER TABLE knowledge_document ADD COLUMN retrieval_generation_id VARCHAR"
        )
        connection.exec_driver_sql(
            "ALTER TABLE knowledge_document ADD COLUMN retrieval_status "
            "VARCHAR NOT NULL DEFAULT 'pending'"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_knowledge_document_retrieval_generation_id "
            "ON knowledge_document (retrieval_generation_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_knowledge_document_retrieval_status "
            "ON knowledge_document (retrieval_status)"
        )
        connection.exec_driver_sql(
            """
            UPDATE knowledge_document
            SET retrieval_generation_id=canonical_generation_id,
                retrieval_status='ready'
            WHERE EXISTS (
                SELECT 1
                FROM knowledge_unit
                WHERE knowledge_unit.document_id=knowledge_document.id
                  AND knowledge_unit.canonical_generation_id=
                      knowledge_document.canonical_generation_id
            )
            """
        )

        import_columns = (
            ("phase", "VARCHAR NOT NULL DEFAULT 'queued'"),
            ("attempt_number", "INTEGER NOT NULL DEFAULT 1"),
            ("retry_of", "VARCHAR"),
            ("planned_document_id", "VARCHAR"),
            ("canonical_generation_id", "VARCHAR"),
            ("envelope_sha256", "VARCHAR"),
            ("content_ir_sha256", "VARCHAR"),
            ("retryable", "BOOLEAN NOT NULL DEFAULT 0"),
            ("cancel_requested", "BOOLEAN NOT NULL DEFAULT 0"),
        )
        for column_name, declaration in import_columns:
            connection.exec_driver_sql(
                f"ALTER TABLE knowledge_import ADD COLUMN {column_name} {declaration}"
            )
        for column_name in (
            "phase",
            "retry_of",
            "planned_document_id",
            "canonical_generation_id",
        ):
            connection.exec_driver_sql(
                f"CREATE INDEX ix_knowledge_import_{column_name} "
                f"ON knowledge_import ({column_name})"
            )
        connection.exec_driver_sql(
            "UPDATE knowledge_import "
            "SET planned_document_id=document_id "
            "WHERE planned_document_id IS NULL AND document_id IS NOT NULL"
        )
        connection.exec_driver_sql(
            """
            UPDATE knowledge_import
            SET canonical_generation_id=(
                SELECT knowledge_document.canonical_generation_id
                FROM knowledge_document
                WHERE knowledge_document.id=knowledge_import.document_id
            )
            WHERE canonical_generation_id IS NULL AND document_id IS NOT NULL
            """
        )

        connection.exec_driver_sql(
            """
            CREATE TABLE knowledge_canonical_generation (
                id VARCHAR NOT NULL PRIMARY KEY,
                document_id VARCHAR NOT NULL,
                import_id VARCHAR,
                source_artifact_id VARCHAR,
                library_id VARCHAR NOT NULL,
                source_sha256 VARCHAR NOT NULL,
                source_format VARCHAR NOT NULL,
                media_type VARCHAR,
                display_name VARCHAR NOT NULL,
                envelope_sha256 VARCHAR NOT NULL,
                content_ir_sha256 VARCHAR NOT NULL,
                relative_path VARCHAR NOT NULL,
                schema_version INTEGER NOT NULL,
                pipeline_payload JSON NOT NULL,
                warnings_payload JSON NOT NULL,
                compatibility_state VARCHAR NOT NULL DEFAULT 'verified',
                created_at DATETIME NOT NULL,
                FOREIGN KEY(document_id) REFERENCES knowledge_document (id),
                FOREIGN KEY(import_id) REFERENCES knowledge_import (id),
                FOREIGN KEY(source_artifact_id) REFERENCES artifact (id)
            )
            """
        )
        for column_name in (
            "document_id",
            "import_id",
            "source_artifact_id",
            "library_id",
            "source_sha256",
            "source_format",
            "envelope_sha256",
            "content_ir_sha256",
            "compatibility_state",
        ):
            connection.exec_driver_sql(
                f"CREATE INDEX ix_knowledge_canonical_generation_{column_name} "
                f"ON knowledge_canonical_generation ({column_name})"
            )

        connection.exec_driver_sql(
            """
            CREATE TABLE knowledge_derivation (
                id VARCHAR NOT NULL PRIMARY KEY,
                document_id VARCHAR NOT NULL,
                canonical_generation_id VARCHAR NOT NULL,
                import_id VARCHAR,
                status VARCHAR NOT NULL,
                phase VARCHAR NOT NULL,
                attempt_number INTEGER NOT NULL,
                retry_of VARCHAR,
                error_code VARCHAR,
                error_summary VARCHAR,
                retryable BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(document_id) REFERENCES knowledge_document (id),
                FOREIGN KEY(canonical_generation_id)
                    REFERENCES knowledge_canonical_generation (id),
                FOREIGN KEY(import_id) REFERENCES knowledge_import (id),
                FOREIGN KEY(retry_of) REFERENCES knowledge_derivation (id)
            )
            """
        )
        for column_name in (
            "document_id",
            "canonical_generation_id",
            "import_id",
            "status",
            "phase",
            "retry_of",
            "error_code",
        ):
            connection.exec_driver_sql(
                f"CREATE INDEX ix_knowledge_derivation_{column_name} "
                f"ON knowledge_derivation ({column_name})"
            )
        connection.exec_driver_sql(
            "CREATE INDEX ix_knowledge_derivation_lookup "
            "ON knowledge_derivation "
            "(document_id, canonical_generation_id, created_at)"
        )
        connection.exec_driver_sql("PRAGMA user_version=19")
    return 19


def migrate_v19_to_v20(engine: Engine) -> int:
    with engine.begin() as connection:
        _require_knowledge_source_shape(connection, 19)
        connection.exec_driver_sql(
            "UPDATE knowledge_import "
            "SET status='canonical_ready', phase='completed' "
            "WHERE status='succeeded'"
        )
        attempts = connection.exec_driver_sql(
            "SELECT id, planned_document_id "
            "FROM knowledge_import "
            "WHERE planned_document_id IS NOT NULL "
            "ORDER BY planned_document_id, attempt_number, created_at, id"
        ).fetchall()
        current_document_id: str | None = None
        ordinal = 0
        for import_id, planned_document_id in attempts:
            if planned_document_id != current_document_id:
                current_document_id = planned_document_id
                ordinal = 1
            else:
                ordinal += 1
            connection.exec_driver_sql(
                "UPDATE knowledge_import SET attempt_number=? WHERE id=?",
                (ordinal, import_id),
            )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX uq_knowledge_import_planned_document_attempt "
            "ON knowledge_import (planned_document_id, attempt_number)"
        )
        connection.exec_driver_sql("PRAGMA user_version=20")
    return 20


def migrate_v20_to_v21(engine: Engine) -> int:
    with engine.begin() as connection:
        _require_knowledge_source_shape(connection, 20)
        connection.exec_driver_sql(
            """
            CREATE TABLE knowledge_index_task (
                id VARCHAR NOT NULL PRIMARY KEY,
                library_id VARCHAR NOT NULL,
                index_kinds_payload JSON NOT NULL,
                trigger VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                phase VARCHAR NOT NULL,
                profile_fingerprint VARCHAR,
                corpus_fingerprint VARCHAR,
                vector_generation_id VARCHAR,
                error_code VARCHAR,
                error_summary VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        for column_name in (
            "library_id",
            "trigger",
            "status",
            "phase",
            "profile_fingerprint",
            "corpus_fingerprint",
            "vector_generation_id",
            "error_code",
        ):
            connection.exec_driver_sql(
                f"CREATE INDEX ix_knowledge_index_task_{column_name} "
                f"ON knowledge_index_task ({column_name})"
            )
        connection.exec_driver_sql("PRAGMA user_version=21")
    return 21


def migrate_v21_to_v22(engine: Engine) -> int:
    with engine.begin() as connection:
        _require_knowledge_source_shape(connection, 21)
        connection.exec_driver_sql(
            "ALTER TABLE knowledge_document "
            "ADD COLUMN retrieval_projection_version INTEGER"
        )
        connection.exec_driver_sql(
            "ALTER TABLE knowledge_document "
            "ADD COLUMN retrieval_content_fingerprint VARCHAR"
        )
        connection.exec_driver_sql(
            "ALTER TABLE knowledge_document "
            "ADD COLUMN retrieval_unit_count INTEGER NOT NULL DEFAULT 0"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_knowledge_document_retrieval_projection_version "
            "ON knowledge_document (retrieval_projection_version)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_knowledge_document_retrieval_content_fingerprint "
            "ON knowledge_document (retrieval_content_fingerprint)"
        )
        connection.exec_driver_sql(
            "ALTER TABLE knowledge_vector_generation "
            "ADD COLUMN corpus_fingerprint_schema INTEGER NOT NULL DEFAULT 1"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_knowledge_vector_generation_corpus_fingerprint_schema "
            "ON knowledge_vector_generation (corpus_fingerprint_schema)"
        )
        # Historical rows have no proof that they satisfy the current bounded
        # projection contract. Keep the derived bytes for cleanup, but make them
        # unreachable until service-owned re-derivation publishes v2 atomically.
        connection.exec_driver_sql(
            "UPDATE knowledge_document "
            "SET retrieval_generation_id=NULL, retrieval_status='pending', "
            "retrieval_projection_version=NULL, "
            "retrieval_content_fingerprint=NULL, retrieval_unit_count=0 "
            "WHERE active=1"
        )
        connection.exec_driver_sql("PRAGMA user_version=22")
    return 22


def migrate_v22_to_v23(engine: Engine) -> int:
    """Invalidate row-id-dependent v2 projections before deterministic v3 derivation."""

    with engine.begin() as connection:
        _require_knowledge_source_shape(connection, 22)
        connection.exec_driver_sql(
            "UPDATE knowledge_document "
            "SET retrieval_generation_id=NULL, retrieval_status='pending', "
            "retrieval_projection_version=NULL, "
            "retrieval_content_fingerprint=NULL, retrieval_unit_count=0 "
            "WHERE active=1"
        )
        connection.exec_driver_sql("PRAGMA user_version=23")
    return 23


def migrate_v23_to_v24(engine: Engine) -> int:
    """Add immutable Dataset identity to newly created ML column bindings."""

    with engine.begin() as connection:
        tables = _table_names(connection)
        if "dataset_column_binding" in tables:
            columns = _table_columns(connection, "dataset_column_binding")
            if "dataset_snapshot_payload" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE dataset_column_binding "
                    "ADD COLUMN dataset_snapshot_payload JSON"
                )
        connection.exec_driver_sql("PRAGMA user_version=24")
    return 24


def migrate_v24_to_v25(engine: Engine) -> int:
    """Link ready ML task outputs to their one public Artifact identity."""

    with engine.begin() as connection:
        tables = _table_names(connection)
        if "ml_task_artifact" in tables:
            columns = _table_columns(connection, "ml_task_artifact")
            if "artifact_id" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE ml_task_artifact ADD COLUMN artifact_id VARCHAR "
                    "REFERENCES artifact(id)"
                )
                connection.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_ml_task_artifact_artifact_id "
                    "ON ml_task_artifact (artifact_id)"
                )
        connection.exec_driver_sql("PRAGMA user_version=25")
    return 25


def migrate_v25_to_v26(engine: Engine) -> int:
    """Add authoritative Dataset derivation records and ordered input edges."""

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE dataset_derivation (
                dataset_id VARCHAR NOT NULL PRIMARY KEY,
                operation_name VARCHAR NOT NULL,
                parameters_payload JSON NOT NULL,
                agent_explanation VARCHAR,
                tool_call_message_id VARCHAR,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(dataset_id) REFERENCES dataset (id)
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_dataset_derivation_operation_name "
            "ON dataset_derivation (operation_name)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_dataset_derivation_tool_call_message_id "
            "ON dataset_derivation (tool_call_message_id)"
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE dataset_derivation_input (
                id VARCHAR NOT NULL PRIMARY KEY,
                derivation_dataset_id VARCHAR NOT NULL,
                input_dataset_id VARCHAR NOT NULL,
                input_position INTEGER NOT NULL,
                alias VARCHAR,
                CONSTRAINT uq_dataset_derivation_input_position
                    UNIQUE (derivation_dataset_id, input_position),
                FOREIGN KEY(derivation_dataset_id) REFERENCES dataset_derivation (dataset_id),
                FOREIGN KEY(input_dataset_id) REFERENCES dataset (id)
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_dataset_derivation_input_derivation_dataset_id "
            "ON dataset_derivation_input (derivation_dataset_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_dataset_derivation_input_input_dataset_id "
            "ON dataset_derivation_input (input_dataset_id)"
        )
        connection.exec_driver_sql("PRAGMA user_version=26")
    return 26


_KNOWLEDGE_JOB_STATUS_CASE = (
    "CASE status "
    "WHEN 'pending' THEN 'queued' "
    "WHEN 'queued' THEN 'queued' "
    "WHEN 'running' THEN 'running' "
    "WHEN 'succeeded' THEN 'succeeded' "
    "WHEN 'canonical_ready' THEN 'succeeded' "
    "WHEN 'retrieval_ready' THEN 'succeeded' "
    "WHEN 'reused' THEN 'succeeded' "
    "WHEN 'failed' THEN 'failed' "
    "WHEN 'needs_attention' THEN 'failed' "
    "WHEN 'cancelled' THEN 'cancelled' "
    "ELSE 'queued' END"
)


def migrate_v26_to_v27(engine: Engine) -> int:
    """Add the unified Job table and backfill jobs from domain authorities."""

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE job (
                id VARCHAR NOT NULL PRIMARY KEY,
                domain VARCHAR NOT NULL,
                kind VARCHAR NOT NULL,
                reference VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                phase VARCHAR NOT NULL,
                error_summary VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                started_at DATETIME,
                finished_at DATETIME,
                CONSTRAINT uq_job_domain_reference UNIQUE (domain, reference)
            )
            """
        )
        for column in ("domain", "kind", "reference", "status"):
            connection.exec_driver_sql(
                f"CREATE INDEX ix_job_{column} ON job ({column})"
            )
        _backfill_jobs(connection)
        connection.exec_driver_sql("PRAGMA user_version=27")
    return 27


def _backfill_jobs(connection) -> None:
    tables = {
        str(row[0])
        for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).all()
    }
    if "ml_task" in tables:
        connection.exec_driver_sql(
            """
            INSERT INTO job (id, domain, kind, reference, status, phase,
                             error_summary, created_at, updated_at, started_at, finished_at)
            SELECT id, 'ml', task_type, id,
                   CASE status WHEN 'pending' THEN 'queued' ELSE status END,
                   status, error_summary, created_at, updated_at, started_at, finished_at
            FROM ml_task
            """
        )
    if "knowledge_import" in tables:
        connection.exec_driver_sql(
            f"""
            INSERT INTO job (id, domain, kind, reference, status, phase,
                             error_summary, created_at, updated_at)
            SELECT id, 'knowledge', 'import', id, {_KNOWLEDGE_JOB_STATUS_CASE},
                   phase, error_summary, created_at, updated_at
            FROM knowledge_import
            """
        )
    if "knowledge_derivation" in tables:
        connection.exec_driver_sql(
            f"""
            INSERT INTO job (id, domain, kind, reference, status, phase,
                             error_summary, created_at, updated_at)
            SELECT id, 'knowledge', 'content_preparation', id, {_KNOWLEDGE_JOB_STATUS_CASE},
                   phase, error_summary, created_at, updated_at
            FROM knowledge_derivation
            """
        )
    if "knowledge_index_task" in tables:
        connection.exec_driver_sql(
            f"""
            INSERT INTO job (id, domain, kind, reference, status, phase,
                             error_summary, created_at, updated_at)
            SELECT id, 'knowledge', 'index_build', id, {_KNOWLEDGE_JOB_STATUS_CASE},
                   phase, error_summary, created_at, updated_at
            FROM knowledge_index_task
            """
        )


def _create_v16_knowledge_schema(connection) -> None:
    """Create the fixed historical v16 Knowledge shape without current metadata."""

    connection.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS knowledge_document (
            id VARCHAR NOT NULL PRIMARY KEY,
            library_id VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            source_artifact_id VARCHAR,
            canonical_generation_id VARCHAR NOT NULL,
            active BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(source_artifact_id) REFERENCES artifact (id)
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS knowledge_unit (
            id VARCHAR NOT NULL PRIMARY KEY,
            document_id VARCHAR NOT NULL,
            canonical_generation_id VARCHAR NOT NULL,
            ordinal INTEGER NOT NULL,
            text VARCHAR NOT NULL,
            search_text VARCHAR NOT NULL,
            locator_payload JSON NOT NULL,
            created_at DATETIME NOT NULL,
            CONSTRAINT uq_knowledge_unit_generation_ordinal
                UNIQUE (document_id, canonical_generation_id, ordinal),
            FOREIGN KEY(document_id) REFERENCES knowledge_document (id)
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS knowledge_import (
            id VARCHAR NOT NULL PRIMARY KEY,
            library_id VARCHAR NOT NULL,
            original_file_name VARCHAR NOT NULL,
            source_format VARCHAR NOT NULL,
            source_sha256 VARCHAR,
            status VARCHAR NOT NULL,
            document_id VARCHAR,
            source_artifact_id VARCHAR,
            canonical_path VARCHAR,
            reused_existing BOOLEAN NOT NULL,
            error_code VARCHAR,
            error_summary VARCHAR,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(document_id) REFERENCES knowledge_document (id),
            FOREIGN KEY(source_artifact_id) REFERENCES artifact (id)
        )
        """
    )
    indexes = (
        ("ix_knowledge_document_library_id", "knowledge_document", "library_id"),
        ("ix_knowledge_document_title", "knowledge_document", "title"),
        ("ix_knowledge_document_source_artifact_id", "knowledge_document", "source_artifact_id"),
        ("ix_knowledge_document_canonical_generation_id", "knowledge_document", "canonical_generation_id"),
        ("ix_knowledge_document_active", "knowledge_document", "active"),
        ("ix_knowledge_unit_document_id", "knowledge_unit", "document_id"),
        ("ix_knowledge_unit_canonical_generation_id", "knowledge_unit", "canonical_generation_id"),
        ("ix_knowledge_unit_ordinal", "knowledge_unit", "ordinal"),
        ("ix_knowledge_import_library_id", "knowledge_import", "library_id"),
        ("ix_knowledge_import_source_format", "knowledge_import", "source_format"),
        ("ix_knowledge_import_source_sha256", "knowledge_import", "source_sha256"),
        ("ix_knowledge_import_status", "knowledge_import", "status"),
        ("ix_knowledge_import_document_id", "knowledge_import", "document_id"),
        ("ix_knowledge_import_source_artifact_id", "knowledge_import", "source_artifact_id"),
        ("ix_knowledge_import_error_code", "knowledge_import", "error_code"),
    )
    for name, table, column in indexes:
        connection.exec_driver_sql(
            f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})"
        )
    connection.exec_driver_sql(
        "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_unit_fts USING fts5("
        "unit_id UNINDEXED, title, search_text, tokenize='unicode61')"
    )
