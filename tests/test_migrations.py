import sqlite3
from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.layout import database_path


def _create_v1_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.executescript(
            """
            CREATE TABLE project (
                id TEXT NOT NULL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX ix_project_name ON project (name);

            CREATE TABLE dataset (
                id TEXT NOT NULL PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_format TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES project (id)
            );
            CREATE INDEX ix_dataset_project_id ON dataset (project_id);
            CREATE INDEX ix_dataset_name ON dataset (name);
            CREATE INDEX ix_dataset_source_format ON dataset (source_format);

            CREATE TABLE work_item (
                id TEXT NOT NULL PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES project (id)
            );
            CREATE INDEX ix_work_item_project_id ON work_item (project_id);
            CREATE INDEX ix_work_item_name ON work_item (name);
            """
        )
        connection.execute(
            """
            INSERT INTO project (id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("project-1", "Retail", None, "2026-03-10T00:00:00+00:00", "2026-03-10T00:00:00+00:00"),
        )
        connection.execute(
            """
            INSERT INTO work_item (id, project_id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("work-item-1", "project-1", "Churn", None, "2026-03-10T00:00:00+00:00", "2026-03-10T00:00:00+00:00"),
        )
        connection.execute("PRAGMA user_version=1")
        connection.commit()
    finally:
        connection.close()


def test_storage_bootstrap_migrates_v1_work_item_schema(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    _create_v1_database(database_path(paths))

    context = StorageBootstrapService().initialize(paths)

    with context.session_factory() as session:
        row = session.connection().exec_driver_sql(
            """
            SELECT dataset_id, best_trained_model_id, feature_columns, target_columns
            FROM work_item
            WHERE id = 'work-item-1'
            """
        ).one()

    assert row[0] is None
    assert row[1] is None
    assert row[2] == "[]"
    assert row[3] == "[]"
