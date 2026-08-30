from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, create_engine, select

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import StorageBootstrapError
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.layout import database_path
from xenix.services.storage.migrations import (
    CURRENT_SCHEMA_VERSION,
    get_user_version,
    migrate_v23_to_v24,
    migrate_v24_to_v25,
    migrate_v25_to_v26,
    migrate_v26_to_v27,
)
from xenix.services.storage.models import (
    ArtifactKind,
    ArtifactRow,
    DatasetColumnBindingRow,
    DatasetDerivationInputRow,
    DatasetDerivationRow,
    JobDomain,
    JobRow,
    JobStatus,
    KnowledgeCanonicalGenerationRow,
    KnowledgeDerivationRow,
    KnowledgeDocumentRow,
    KnowledgeImportRow,
    KnowledgeUnitRow,
    KnowledgeVectorGenerationRow,
)
from xenix.services.storage.repositories.knowledge import KnowledgeRepository
from xenix.services.knowledge_projection import (
    RETRIEVAL_PROJECTION_VERSION,
    retrieval_content_fingerprint,
)

_NOW = "2026-07-01T00:00:00+00:00"


def test_v23_to_v24_adds_nullable_dataset_snapshot_without_inventing_history(
    tmp_path: Path,
) -> None:
    database = tmp_path / "v23.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE dataset_column_binding (
                id VARCHAR NOT NULL PRIMARY KEY,
                dataset_id VARCHAR NOT NULL,
                role_bindings JSON NOT NULL,
                model_key VARCHAR,
                model_family VARCHAR,
                model_task_kind VARCHAR,
                schema_version INTEGER NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO dataset_column_binding VALUES "
            "('binding-legacy', 'dataset-1', '[]', NULL, NULL, NULL, 1, ?)",
            (_NOW,),
        )
        connection.exec_driver_sql("PRAGMA user_version=23")

    assert migrate_v23_to_v24(engine) == 24
    assert get_user_version(engine) == 24
    with engine.connect() as connection:
        columns = {
            str(row[1])
            for row in connection.exec_driver_sql(
                "PRAGMA table_info(dataset_column_binding)"
            ).all()
        }
    assert "dataset_snapshot_payload" in columns
    with Session(engine) as session:
        binding = session.get(DatasetColumnBindingRow, "binding-legacy")
        assert binding is not None
        assert binding.schema_version == 1
        assert binding.dataset_snapshot_payload is None


def test_v24_to_v25_adds_nullable_public_artifact_reference(tmp_path: Path) -> None:
    database = tmp_path / "v24.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE artifact (
                id VARCHAR NOT NULL PRIMARY KEY
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE ml_task_artifact (
                id VARCHAR NOT NULL PRIMARY KEY,
                ml_task_id VARCHAR NOT NULL,
                artifact_kind VARCHAR NOT NULL,
                absolute_path VARCHAR NOT NULL,
                ready_to_open BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO ml_task_artifact VALUES "
            "('task-artifact-1', 'task-1', 'evaluation_report', 'C:/report.json', 1, ?)",
            (_NOW,),
        )
        connection.exec_driver_sql("PRAGMA user_version=24")

    assert migrate_v24_to_v25(engine) == 25
    assert get_user_version(engine) == 25
    with engine.connect() as connection:
        columns = {
            str(row[1])
            for row in connection.exec_driver_sql(
                "PRAGMA table_info(ml_task_artifact)"
            ).all()
        }
        foreign_keys = connection.exec_driver_sql(
            "PRAGMA foreign_key_list(ml_task_artifact)"
        ).all()
        legacy_artifact_id = connection.exec_driver_sql(
            "SELECT artifact_id FROM ml_task_artifact WHERE id='task-artifact-1'"
        ).scalar_one()
    assert "artifact_id" in columns
    assert any(row[2] == "artifact" and row[3] == "artifact_id" for row in foreign_keys)
    assert legacy_artifact_id is None


def test_v25_to_v26_adds_dataset_derivation_tables(tmp_path: Path) -> None:
    database = tmp_path / "v25.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA user_version=25")

    assert migrate_v25_to_v26(engine) == 26
    assert get_user_version(engine) == 26
    inspector = inspect(engine)
    assert {"dataset_derivation", "dataset_derivation_input"}.issubset(
        inspector.get_table_names()
    )
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO dataset_derivation VALUES (?, ?, ?, ?, ?, ?)",
            (
                "dataset-output",
                "data.transform",
                '{"sql":"SELECT 1"}',
                "keep valid rows",
                "tool-call-1",
                _NOW,
            ),
        )
        connection.exec_driver_sql(
            "INSERT INTO dataset_derivation_input VALUES (?, ?, ?, ?, ?)",
            ("edge-1", "dataset-output", "dataset-input", 0, "input"),
        )
    with Session(engine) as session:
        derivation = session.get(DatasetDerivationRow, "dataset-output")
        edge = session.get(DatasetDerivationInputRow, "edge-1")
        assert derivation is not None
        assert derivation.parameters_payload == {"sql": "SELECT 1"}
        assert derivation.tool_call_message_id == "tool-call-1"
        assert edge is not None and edge.input_position == 0


def test_v26_to_v27_adds_job_table_and_backfills_domain_authorities(tmp_path: Path) -> None:
    database = tmp_path / "v26.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE ml_task (
                id VARCHAR NOT NULL PRIMARY KEY,
                task_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                error_summary VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                started_at DATETIME,
                finished_at DATETIME
            )
            """
        )
        for table in ("knowledge_import", "knowledge_derivation", "knowledge_index_task"):
            connection.exec_driver_sql(
                f"""
                CREATE TABLE {table} (
                    id VARCHAR NOT NULL PRIMARY KEY,
                    status VARCHAR NOT NULL,
                    phase VARCHAR NOT NULL,
                    error_summary VARCHAR,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        connection.exec_driver_sql(
            "INSERT INTO ml_task (id, task_type, status, created_at, updated_at) "
            "VALUES ('ml-pending', 'fit', 'pending', ?, ?), "
            "('ml-running', 'apply', 'running', ?, ?), "
            "('ml-done', 'evaluate', 'succeeded', ?, ?), "
            "('ml-failed', 'fit', 'failed', ?, ?)",
            (_NOW, _NOW, _NOW, _NOW, _NOW, _NOW, _NOW, _NOW),
        )
        connection.exec_driver_sql(
            "INSERT INTO knowledge_import (id, status, phase, created_at, updated_at) "
            "VALUES ('imp-pending', 'pending', 'queued', ?, ?), "
            "('imp-ready', 'canonical_ready', 'completed', ?, ?), "
            "('imp-reused', 'reused', 'completed', ?, ?), "
            "('imp-attention', 'needs_attention', 'parsing', ?, ?), "
            "('imp-cancelled', 'cancelled', 'parsing', ?, ?)",
            (_NOW, _NOW, _NOW, _NOW, _NOW, _NOW, _NOW, _NOW, _NOW, _NOW),
        )
        connection.exec_driver_sql(
            "INSERT INTO knowledge_derivation (id, status, phase, created_at, updated_at) "
            "VALUES ('der-queued', 'queued', 'queued', ?, ?), "
            "('der-ready', 'retrieval_ready', 'completed', ?, ?)",
            (_NOW, _NOW, _NOW, _NOW),
        )
        connection.exec_driver_sql(
            "INSERT INTO knowledge_index_task (id, status, phase, created_at, updated_at) "
            "VALUES ('idx-queued', 'queued', 'queued', ?, ?), "
            "('idx-failed', 'failed', 'indexing', ?, ?)",
            (_NOW, _NOW, _NOW, _NOW),
        )
        connection.exec_driver_sql("PRAGMA user_version=26")

    assert migrate_v26_to_v27(engine) == 27
    assert get_user_version(engine) == 27
    inspector = inspect(engine)
    assert "job" in inspector.get_table_names()
    assert {"uq_job_domain_reference"}.issubset(
        {constraint["name"] for constraint in inspector.get_unique_constraints("job")}
    )

    with Session(engine) as session:
        jobs = {job.reference: job for job in session.exec(select(JobRow))}
        assert len(jobs) == 13
        assert jobs["ml-pending"].domain is JobDomain.ML
        assert jobs["ml-pending"].status is JobStatus.QUEUED
        assert jobs["ml-pending"].kind == "fit"
        assert jobs["ml-done"].status is JobStatus.SUCCEEDED
        assert jobs["ml-failed"].status is JobStatus.FAILED
        assert jobs["imp-pending"].domain is JobDomain.KNOWLEDGE
        assert jobs["imp-pending"].kind == "import"
        assert jobs["imp-pending"].status is JobStatus.QUEUED
        assert jobs["imp-ready"].status is JobStatus.SUCCEEDED
        assert jobs["imp-reused"].status is JobStatus.SUCCEEDED
        assert jobs["imp-attention"].status is JobStatus.FAILED
        assert jobs["imp-cancelled"].status is JobStatus.CANCELLED
        assert jobs["der-queued"].kind == "content_preparation"
        assert jobs["der-ready"].status is JobStatus.SUCCEEDED
        assert jobs["idx-queued"].kind == "index_build"
        assert jobs["idx-failed"].status is JobStatus.FAILED


def _create_unsupported_database(db_path: Path, version: int) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(f"PRAGMA user_version={version}")


def _create_static_knowledge_database(db_path: Path, version: int) -> None:
    """Materialize historical SQL without importing current models or migrations."""

    if version not in {15, 16, 17, 18, 19, 20, 21}:
        raise ValueError(version)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE conversation_thread (
                id VARCHAR NOT NULL PRIMARY KEY,
                title VARCHAR,
                system_prompt VARCHAR NOT NULL,
                selected_fq_model_key VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            CREATE TABLE conversation_message (
                id VARCHAR NOT NULL PRIMARY KEY,
                thread_id VARCHAR NOT NULL,
                sequence_index INTEGER NOT NULL,
                kind VARCHAR(20) NOT NULL,
                client_submission_id VARCHAR,
                content_payload JSON NOT NULL,
                text VARCHAR,
                reasoning VARCHAR,
                refusal VARCHAR,
                provider_call_id VARCHAR,
                tool_id VARCHAR,
                contract_version VARCHAR,
                arguments_payload JSON,
                scope_fingerprint VARCHAR,
                tool_call_message_id VARCHAR,
                result_status VARCHAR,
                value_payload JSON,
                error_summary VARCHAR,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(thread_id) REFERENCES conversation_thread (id),
                FOREIGN KEY(tool_call_message_id) REFERENCES conversation_message (id),
                UNIQUE(thread_id, sequence_index),
                UNIQUE(thread_id, client_submission_id),
                UNIQUE(tool_call_message_id)
            );
            CREATE TABLE artifact (
                id VARCHAR NOT NULL PRIMARY KEY,
                kind VARCHAR(10) NOT NULL,
                title VARCHAR NOT NULL,
                absolute_path VARCHAR NOT NULL,
                mime_type VARCHAR,
                summary VARCHAR,
                preview_payload JSON,
                metadata_payload JSON NOT NULL,
                ready_to_open BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL
            );
            CREATE UNIQUE INDEX ux_conversation_message_pending_thread
                ON conversation_message (thread_id)
                WHERE kind='pending_llm_sampling';
            """
        )
        connection.execute(
            "INSERT INTO conversation_thread VALUES (?, ?, ?, ?, ?, ?)",
            ("thread-1", "Historical", "You are Xenix.", None, _NOW, _NOW),
        )
        connection.execute(
            "INSERT INTO conversation_message "
            "(id, thread_id, sequence_index, kind, content_payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("message-1", "thread-1", 0, "user", '{"text":"kept"}', _NOW),
        )
        connection.execute(
            "INSERT INTO artifact VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "artifact-1",
                "FILE",
                "规则.txt",
                "C:/xenix/artifacts/knowledge/source.txt",
                "text/plain",
                None,
                None,
                '{"source":"historical"}',
                1,
                _NOW,
            ),
        )

        if version >= 16:
            _create_static_v16_knowledge_shape(connection)
        if version >= 17:
            connection.executescript(
                """
                ALTER TABLE knowledge_document ADD COLUMN source_sha256 VARCHAR;
                ALTER TABLE knowledge_document ADD COLUMN source_format VARCHAR;
                ALTER TABLE knowledge_document ADD COLUMN canonical_path VARCHAR;
                CREATE INDEX ix_knowledge_document_source_sha256
                    ON knowledge_document (source_sha256);
                CREATE INDEX ix_knowledge_document_source_format
                    ON knowledge_document (source_format);
                CREATE UNIQUE INDEX uq_knowledge_document_library_source_sha256
                    ON knowledge_document (library_id, source_sha256);
                """
            )
            connection.execute(
                "UPDATE knowledge_document "
                "SET source_sha256=?, source_format='txt', canonical_path=? "
                "WHERE id='document-1'",
                ("A" * 64, "objects/legacy/canonical.json.zst"),
            )
        if version >= 18:
            connection.executescript(
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
                );
                CREATE INDEX ix_knowledge_vector_generation_library_id
                    ON knowledge_vector_generation (library_id);
                CREATE INDEX ix_knowledge_vector_generation_corpus_fingerprint
                    ON knowledge_vector_generation (corpus_fingerprint);
                CREATE INDEX ix_knowledge_vector_generation_profile_fingerprint
                    ON knowledge_vector_generation (profile_fingerprint);
                CREATE INDEX ix_knowledge_vector_generation_lookup
                    ON knowledge_vector_generation
                    (library_id, profile_fingerprint, corpus_fingerprint, created_at);
                """
            )
            connection.execute(
                "INSERT INTO knowledge_vector_generation VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "vector-generation-1",
                    "global",
                    "B" * 64,
                    "C" * 64,
                    "provider",
                    "embedding-model",
                    3,
                    "cosine",
                    "indexes/vector-generation-1",
                    1,
                    _NOW,
                ),
            )
        if version >= 19:
            _create_static_v19_knowledge_shape(connection)
        if version >= 20:
            connection.execute(
                "UPDATE knowledge_import SET status='canonical_ready', phase='completed' "
                "WHERE status='succeeded'"
            )
            connection.execute(
                "CREATE UNIQUE INDEX uq_knowledge_import_planned_document_attempt "
                "ON knowledge_import (planned_document_id, attempt_number)"
            )
        if version >= 21:
            connection.executescript(
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
                );
                CREATE INDEX ix_knowledge_index_task_library_id
                    ON knowledge_index_task (library_id);
                CREATE INDEX ix_knowledge_index_task_trigger
                    ON knowledge_index_task (trigger);
                CREATE INDEX ix_knowledge_index_task_status
                    ON knowledge_index_task (status);
                CREATE INDEX ix_knowledge_index_task_phase
                    ON knowledge_index_task (phase);
                CREATE INDEX ix_knowledge_index_task_profile_fingerprint
                    ON knowledge_index_task (profile_fingerprint);
                CREATE INDEX ix_knowledge_index_task_corpus_fingerprint
                    ON knowledge_index_task (corpus_fingerprint);
                CREATE INDEX ix_knowledge_index_task_vector_generation_id
                    ON knowledge_index_task (vector_generation_id);
                CREATE INDEX ix_knowledge_index_task_error_code
                    ON knowledge_index_task (error_code);
                """
            )
        connection.execute(f"PRAGMA user_version={version}")


def _create_static_v16_knowledge_shape(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE knowledge_document (
            id VARCHAR NOT NULL PRIMARY KEY,
            library_id VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            source_artifact_id VARCHAR,
            canonical_generation_id VARCHAR NOT NULL,
            active BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(source_artifact_id) REFERENCES artifact (id)
        );
        CREATE TABLE knowledge_unit (
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
        );
        CREATE TABLE knowledge_import (
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
        );
        CREATE VIRTUAL TABLE knowledge_unit_fts USING fts5(
            unit_id UNINDEXED, title, search_text, tokenize='unicode61'
        );
        CREATE INDEX ix_knowledge_document_library_id ON knowledge_document (library_id);
        CREATE INDEX ix_knowledge_document_title ON knowledge_document (title);
        CREATE INDEX ix_knowledge_document_source_artifact_id
            ON knowledge_document (source_artifact_id);
        CREATE INDEX ix_knowledge_document_canonical_generation_id
            ON knowledge_document (canonical_generation_id);
        CREATE INDEX ix_knowledge_document_active ON knowledge_document (active);
        CREATE INDEX ix_knowledge_unit_document_id ON knowledge_unit (document_id);
        CREATE INDEX ix_knowledge_unit_canonical_generation_id
            ON knowledge_unit (canonical_generation_id);
        CREATE INDEX ix_knowledge_unit_ordinal ON knowledge_unit (ordinal);
        CREATE INDEX ix_knowledge_import_library_id ON knowledge_import (library_id);
        CREATE INDEX ix_knowledge_import_source_format ON knowledge_import (source_format);
        CREATE INDEX ix_knowledge_import_source_sha256 ON knowledge_import (source_sha256);
        CREATE INDEX ix_knowledge_import_status ON knowledge_import (status);
        CREATE INDEX ix_knowledge_import_document_id ON knowledge_import (document_id);
        CREATE INDEX ix_knowledge_import_source_artifact_id
            ON knowledge_import (source_artifact_id);
        CREATE INDEX ix_knowledge_import_error_code ON knowledge_import (error_code);
        """
    )
    connection.execute(
        "INSERT INTO knowledge_document VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "document-1",
            "global",
            "雨季规则",
            "artifact-1",
            "canonical-generation-1",
            1,
            _NOW,
            _NOW,
        ),
    )
    connection.execute(
        "INSERT INTO knowledge_unit VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "unit-1",
            "document-1",
            "canonical-generation-1",
            0,
            "雨具按三周需求备货。",
            "雨具 三周 需求 备货",
            '{"passage":1}',
            _NOW,
        ),
    )
    connection.execute(
        "INSERT INTO knowledge_unit_fts VALUES (?, ?, ?)",
        ("unit-1", "雨季规则", "雨具 三周 需求 备货"),
    )
    connection.execute(
        "INSERT INTO knowledge_import VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "import-1",
            "global",
            "规则.txt",
            "txt",
            "A" * 64,
            "succeeded",
            "document-1",
            "artifact-1",
            "objects/legacy/canonical.json.zst",
            0,
            None,
            None,
            _NOW,
            _NOW,
        ),
    )


def _create_static_v19_knowledge_shape(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        ALTER TABLE knowledge_document ADD COLUMN retrieval_generation_id VARCHAR;
        ALTER TABLE knowledge_document ADD COLUMN retrieval_status
            VARCHAR NOT NULL DEFAULT 'pending';
        CREATE INDEX ix_knowledge_document_retrieval_generation_id
            ON knowledge_document (retrieval_generation_id);
        CREATE INDEX ix_knowledge_document_retrieval_status
            ON knowledge_document (retrieval_status);
        UPDATE knowledge_document
        SET retrieval_generation_id=canonical_generation_id,
            retrieval_status='ready'
        WHERE EXISTS (
            SELECT 1
            FROM knowledge_unit
            WHERE knowledge_unit.document_id=knowledge_document.id
              AND knowledge_unit.canonical_generation_id=
                  knowledge_document.canonical_generation_id
        );

        ALTER TABLE knowledge_import ADD COLUMN phase
            VARCHAR NOT NULL DEFAULT 'queued';
        ALTER TABLE knowledge_import ADD COLUMN attempt_number
            INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE knowledge_import ADD COLUMN retry_of VARCHAR;
        ALTER TABLE knowledge_import ADD COLUMN planned_document_id VARCHAR;
        ALTER TABLE knowledge_import ADD COLUMN canonical_generation_id VARCHAR;
        ALTER TABLE knowledge_import ADD COLUMN envelope_sha256 VARCHAR;
        ALTER TABLE knowledge_import ADD COLUMN content_ir_sha256 VARCHAR;
        ALTER TABLE knowledge_import ADD COLUMN retryable
            BOOLEAN NOT NULL DEFAULT 0;
        ALTER TABLE knowledge_import ADD COLUMN cancel_requested
            BOOLEAN NOT NULL DEFAULT 0;
        CREATE INDEX ix_knowledge_import_phase ON knowledge_import (phase);
        CREATE INDEX ix_knowledge_import_retry_of ON knowledge_import (retry_of);
        CREATE INDEX ix_knowledge_import_planned_document_id
            ON knowledge_import (planned_document_id);
        CREATE INDEX ix_knowledge_import_canonical_generation_id
            ON knowledge_import (canonical_generation_id);
        UPDATE knowledge_import
        SET planned_document_id=document_id
        WHERE planned_document_id IS NULL AND document_id IS NOT NULL;
        UPDATE knowledge_import
        SET canonical_generation_id=(
            SELECT knowledge_document.canonical_generation_id
            FROM knowledge_document
            WHERE knowledge_document.id=knowledge_import.document_id
        )
        WHERE canonical_generation_id IS NULL AND document_id IS NOT NULL;

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
        );
        CREATE INDEX ix_knowledge_canonical_generation_document_id
            ON knowledge_canonical_generation (document_id);
        CREATE INDEX ix_knowledge_canonical_generation_import_id
            ON knowledge_canonical_generation (import_id);
        CREATE INDEX ix_knowledge_canonical_generation_source_artifact_id
            ON knowledge_canonical_generation (source_artifact_id);
        CREATE INDEX ix_knowledge_canonical_generation_library_id
            ON knowledge_canonical_generation (library_id);
        CREATE INDEX ix_knowledge_canonical_generation_source_sha256
            ON knowledge_canonical_generation (source_sha256);
        CREATE INDEX ix_knowledge_canonical_generation_source_format
            ON knowledge_canonical_generation (source_format);
        CREATE INDEX ix_knowledge_canonical_generation_envelope_sha256
            ON knowledge_canonical_generation (envelope_sha256);
        CREATE INDEX ix_knowledge_canonical_generation_content_ir_sha256
            ON knowledge_canonical_generation (content_ir_sha256);
        CREATE INDEX ix_knowledge_canonical_generation_compatibility_state
            ON knowledge_canonical_generation (compatibility_state);

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
        );
        CREATE INDEX ix_knowledge_derivation_document_id
            ON knowledge_derivation (document_id);
        CREATE INDEX ix_knowledge_derivation_canonical_generation_id
            ON knowledge_derivation (canonical_generation_id);
        CREATE INDEX ix_knowledge_derivation_import_id
            ON knowledge_derivation (import_id);
        CREATE INDEX ix_knowledge_derivation_status
            ON knowledge_derivation (status);
        CREATE INDEX ix_knowledge_derivation_phase
            ON knowledge_derivation (phase);
        CREATE INDEX ix_knowledge_derivation_retry_of
            ON knowledge_derivation (retry_of);
        CREATE INDEX ix_knowledge_derivation_error_code
            ON knowledge_derivation (error_code);
        CREATE INDEX ix_knowledge_derivation_lookup
            ON knowledge_derivation
            (document_id, canonical_generation_id, created_at);
        """
    )


def _sqlite_user_version(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _assert_current_round_trip(context, *, suffix: str) -> None:
    repository = KnowledgeRepository()
    document_id = f"document-current-{suffix}"
    import_id = f"import-current-{suffix}"
    generation_id = f"canonical-current-{suffix}"
    with context.session_factory() as session:
        document = repository.create_document(
            session,
            KnowledgeDocumentRow(
                id=document_id,
                title="当前规则",
                source_artifact_id="artifact-1",
                source_sha256=(suffix * 64)[:64],
                source_format="txt",
                canonical_generation_id=generation_id,
                retrieval_generation_id=generation_id,
                retrieval_status="ready",
            ),
        )
        import_row = repository.create_import(
            session,
            KnowledgeImportRow(
                id=import_id,
                original_file_name="current.txt",
                source_format="txt",
                source_sha256=document.source_sha256,
                status="canonical_ready",
                phase="publish",
                planned_document_id=document_id,
                document_id=document_id,
                source_artifact_id="artifact-1",
                canonical_generation_id=generation_id,
                envelope_sha256="d" * 64,
                content_ir_sha256="e" * 64,
            ),
        )
        canonical = repository.create_canonical_generation(
            session,
            KnowledgeCanonicalGenerationRow(
                id=generation_id,
                document_id=document_id,
                import_id=import_row.id,
                source_artifact_id="artifact-1",
                library_id="global",
                source_sha256=document.source_sha256 or "",
                source_format="txt",
                media_type="text/plain",
                display_name="current.txt",
                envelope_sha256="d" * 64,
                content_ir_sha256="e" * 64,
                relative_path=f"objects/canonical/{suffix}",
                schema_version=2,
                pipeline_payload={"parser": "docling"},
                warnings_payload=["legacy_safe"],
            ),
        )
        first = repository.create_derivation(
            session,
            KnowledgeDerivationRow(
                id=f"derivation-1-{suffix}",
                document_id=document_id,
                canonical_generation_id=canonical.id,
                import_id=import_id,
                status="failed",
                phase="derive_units",
                attempt_number=1,
                retryable=True,
            ),
        )
        retry = repository.create_derivation(
            session,
            KnowledgeDerivationRow(
                id=f"derivation-2-{suffix}",
                document_id=document_id,
                canonical_generation_id=canonical.id,
                import_id=import_id,
                status="succeeded",
                phase="publish",
                attempt_number=2,
                retry_of=first.id,
            ),
        )
        repository.replace_units(
            session,
            document=document,
            units=[
                KnowledgeUnitRow(
                    id=f"unit-current-{suffix}",
                    document_id=document_id,
                    canonical_generation_id=generation_id,
                    ordinal=0,
                    text="当前雨具规则",
                    search_text="当前 雨具 规则",
                    locator_payload={"passage": 1},
                )
            ],
        )
        document.retrieval_projection_version = RETRIEVAL_PROJECTION_VERSION
        document.retrieval_content_fingerprint = retrieval_content_fingerprint(
            [(0, "当前雨具规则", {"passage": 1})]
        )
        document.retrieval_unit_count = 1
        session.add(document)
        session.commit()
        session.expire_all()

        loaded = repository.get_canonical_generation(session, canonical.id)
        assert loaded is not None
        assert loaded.pipeline_payload == {"parser": "docling"}
        assert loaded.warnings_payload == ["legacy_safe"]
        assert repository.get_derivation(session, retry.id).retry_of == first.id  # type: ignore[union-attr]
        assert [row.id for row in repository.list_current_units(session, library_id="global") if row.document_id == document_id] == [f"unit-current-{suffix}"]
        assert repository.search_unit_ids(
            session,
            fts_query='"当前"',
            library_id="global",
            document_ids=[document_id],
            limit=5,
        ) == [f"unit-current-{suffix}"]
        assert session.exec(text("PRAGMA foreign_key_check")).all() == []

        with pytest.raises(IntegrityError):
            repository.create_import(
                session,
                KnowledgeImportRow(
                    id=f"import-duplicate-{suffix}",
                    original_file_name="duplicate.txt",
                    source_format="txt",
                    planned_document_id=document_id,
                    attempt_number=1,
                ),
            )
        session.rollback()


def test_storage_bootstrap_rejects_unknown_schema_version(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    _create_unsupported_database(database_path(paths), 99)

    with pytest.raises(StorageBootstrapError):
        StorageBootstrapService().initialize(paths)


def test_fresh_v23_schema_is_orm_fts_fk_and_unique_readable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION == 27
    assert {
        "knowledge_canonical_generation",
        "knowledge_derivation",
        "knowledge_index_task",
    }.issubset(inspect(context.engine).get_table_names())
    with context.session_factory() as session:
        session.add(
            ArtifactRow(
                id="artifact-1",
                kind=ArtifactKind.FILE,
                title="source.txt",
                absolute_path="C:/xenix/artifacts/knowledge/source.txt",
            )
        )
        session.commit()
    _assert_current_round_trip(context, suffix="f")


def test_static_supported_fixture_upgrades_with_orm_fts_and_fk_proof(
    monkeypatch,
    tmp_path: Path,
) -> None:
    version = 21
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / f"xenix-home-{version}"))
    paths = ensure_app_dirs(get_app_paths())
    _create_static_knowledge_database(database_path(paths), version)

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION == 27
    with context.session_factory() as session:
        artifact = session.get(ArtifactRow, "artifact-1")
        assert artifact is not None and artifact.kind is ArtifactKind.FILE
        assert session.exec(text("PRAGMA foreign_key_check")).all() == []
        if version >= 16:
            document = session.get(KnowledgeDocumentRow, "document-1")
            unit = session.get(KnowledgeUnitRow, "unit-1")
            import_row = session.get(KnowledgeImportRow, "import-1")
            assert document is not None
            assert document.retrieval_generation_id is None
            assert document.retrieval_status == "pending"
            assert document.retrieval_projection_version is None
            assert document.retrieval_content_fingerprint is None
            assert document.retrieval_unit_count == 0
            assert unit is not None and unit.locator_payload == {"passage": 1}
            assert import_row is not None
            assert import_row.status == "canonical_ready"
            assert import_row.phase == "completed"
            assert import_row.attempt_number == 1
            assert import_row.planned_document_id == "document-1"
            assert import_row.canonical_generation_id == "canonical-generation-1"
            assert import_row.canonical_path == "objects/legacy/canonical.json.zst"
            assert session.get(KnowledgeCanonicalGenerationRow, "canonical-generation-1") is None
        if version in {18, 19, 20, 21}:
            vector = session.get(KnowledgeVectorGenerationRow, "vector-generation-1")
            assert vector is not None and vector.dimensions == 3
            assert vector.corpus_fingerprint_schema == 1
    _assert_current_round_trip(context, suffix=str(version)[-1])


def test_v20_migration_deterministically_repairs_duplicate_import_attempt_numbers(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home-duplicate-attempts"))
    paths = ensure_app_dirs(get_app_paths())
    path = database_path(paths)
    _create_static_knowledge_database(path, 19)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO knowledge_import (
                id, library_id, original_file_name, source_format, source_sha256,
                status, document_id, source_artifact_id, canonical_path,
                reused_existing, error_code, error_summary, created_at, updated_at,
                phase, attempt_number, retry_of, planned_document_id,
                canonical_generation_id, envelope_sha256, content_ir_sha256,
                retryable, cancel_requested
            )
            SELECT
                'import-duplicate', library_id, 'duplicate.txt', source_format,
                source_sha256, status, document_id, source_artifact_id,
                canonical_path, 1, error_code, error_summary, created_at, updated_at,
                phase, 1, 'import-1', planned_document_id,
                canonical_generation_id, envelope_sha256, content_ir_sha256,
                retryable, cancel_requested
            FROM knowledge_import WHERE id='import-1'
            """
        )

    context = StorageBootstrapService().initialize(paths)

    with context.session_factory() as session:
        rows = list(
            session.exec(
                select(KnowledgeImportRow)
                .where(KnowledgeImportRow.planned_document_id == "document-1")
                .order_by(KnowledgeImportRow.attempt_number)
            )
        )
        assert [(row.id, row.attempt_number) for row in rows] == [
            ("import-1", 1),
            ("import-duplicate", 2),
        ]


def test_supported_version_with_incomplete_source_shape_is_preserved(
    monkeypatch,
    tmp_path: Path,
) -> None:
    version = 20
    table_to_remove = "knowledge_derivation"
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / f"xenix-home-{version}"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    _create_static_knowledge_database(db_path, version)
    with sqlite3.connect(db_path) as connection:
        connection.execute(f"DROP TABLE {table_to_remove}")

    with pytest.raises(StorageBootstrapError):
        StorageBootstrapService().initialize(paths)

    assert _sqlite_user_version(db_path) == version
