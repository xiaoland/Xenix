from __future__ import annotations

import json

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from ...exceptions import ValidationError
from . import models  # noqa: F401

CURRENT_SCHEMA_VERSION = 9


def get_user_version(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())


def set_user_version(engine: Engine, version: int) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(f"PRAGMA user_version={version}")


def bootstrap_current_schema(engine: Engine) -> int:
    SQLModel.metadata.create_all(engine)
    set_user_version(engine, CURRENT_SCHEMA_VERSION)
    return CURRENT_SCHEMA_VERSION


def migrate_v1_to_v2(engine: Engine) -> int:
    with engine.begin() as connection:
        dataset_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(dataset)").all()
        }
        if "derived_from_dataset_id" not in dataset_columns:
            connection.exec_driver_sql(
                "ALTER TABLE dataset ADD COLUMN derived_from_dataset_id VARCHAR"
            )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dataset_derived_from_dataset_id "
            "ON dataset (derived_from_dataset_id)"
        )
        connection.exec_driver_sql("PRAGMA user_version=2")
    return 2


def migrate_v2_to_v3(engine: Engine) -> int:
    with engine.begin() as connection:
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if "agent_message" not in table_names:
            connection.exec_driver_sql("PRAGMA user_version=3")
            return 3
        agent_message_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(agent_message)").all()
        }
        if "status" not in agent_message_columns:
            connection.exec_driver_sql(
                "ALTER TABLE agent_message ADD COLUMN status VARCHAR"
            )
            connection.exec_driver_sql(
                "UPDATE agent_message SET status='completed' WHERE status IS NULL"
            )
        if "updated_at" not in agent_message_columns:
            connection.exec_driver_sql(
                "ALTER TABLE agent_message ADD COLUMN updated_at DATETIME"
            )
            connection.exec_driver_sql(
                "UPDATE agent_message SET updated_at=created_at WHERE updated_at IS NULL"
            )
        if "finalized_at" not in agent_message_columns:
            connection.exec_driver_sql(
                "ALTER TABLE agent_message ADD COLUMN finalized_at DATETIME"
            )
            connection.exec_driver_sql(
                "UPDATE agent_message SET finalized_at=created_at WHERE finalized_at IS NULL"
            )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_agent_message_status "
            "ON agent_message (status)"
        )
        connection.exec_driver_sql("PRAGMA user_version=3")
    return 3


def migrate_v3_to_v4(engine: Engine) -> int:
    with engine.begin() as connection:
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if "agent_message" not in table_names:
            connection.exec_driver_sql("PRAGMA user_version=4")
            return 4
        agent_message_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(agent_message)").all()
        }
        if "status" in agent_message_columns:
            status_pairs = {
                "IN_PROGRESS": "in_progress",
                "COMPLETED": "completed",
                "FAILED": "failed",
                "CANCELLED": "cancelled",
            }
            for old_value, new_value in status_pairs.items():
                connection.exec_driver_sql(
                    "UPDATE agent_message SET status=? WHERE status=?",
                    (new_value, old_value),
                )
        connection.exec_driver_sql("PRAGMA user_version=4")
    return 4


def migrate_v4_to_v5(engine: Engine) -> int:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS dataset_column_selection (
                id VARCHAR NOT NULL PRIMARY KEY,
                dataset_id VARCHAR NOT NULL,
                feature_columns JSON NOT NULL,
                target_columns JSON NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(dataset_id) REFERENCES dataset (id)
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dataset_column_selection_dataset_id "
            "ON dataset_column_selection (dataset_id)"
        )
        connection.exec_driver_sql("PRAGMA user_version=5")
    return 5


def migrate_v5_to_v6(engine: Engine) -> int:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS agent_turn_completion_guard (
                id VARCHAR NOT NULL PRIMARY KEY,
                turn_id VARCHAR NOT NULL,
                attempt_index INTEGER NOT NULL,
                input JSON NOT NULL,
                output JSON NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(turn_id) REFERENCES agent_turn (id)
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_agent_turn_completion_guard_turn_id "
            "ON agent_turn_completion_guard (turn_id)"
        )
        connection.exec_driver_sql("PRAGMA user_version=6")
    return 6


def migrate_v6_to_v7(engine: Engine) -> int:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS dataset_column_binding (
                id VARCHAR NOT NULL PRIMARY KEY,
                dataset_id VARCHAR NOT NULL,
                role_bindings JSON NOT NULL,
                model_key VARCHAR,
                model_family VARCHAR,
                model_task_kind VARCHAR,
                schema_version INTEGER NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(dataset_id) REFERENCES dataset (id)
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dataset_column_binding_dataset_id "
            "ON dataset_column_binding (dataset_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dataset_column_binding_model_key "
            "ON dataset_column_binding (model_key)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dataset_column_binding_model_family "
            "ON dataset_column_binding (model_family)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dataset_column_binding_model_task_kind "
            "ON dataset_column_binding (model_task_kind)"
        )

        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if "dataset_column_selection" in table_names:
            rows = connection.exec_driver_sql(
                """
                SELECT id, dataset_id, feature_columns, target_columns, created_at
                FROM dataset_column_selection
                """
            ).all()
            for row in rows:
                feature_columns = _json_list(row[2])
                target_columns = _json_list(row[3])
                role_bindings: list[dict[str, object]] = []
                if feature_columns:
                    role_bindings.append(
                        {
                            "role": "feature",
                            "columns": feature_columns,
                            "role_kind": "many_columns",
                            "required": True,
                            "metadata": {},
                        }
                    )
                if len(target_columns) == 1:
                    role_bindings.append(
                        {
                            "role": "target",
                            "columns": target_columns,
                            "role_kind": "single_column",
                            "required": True,
                            "metadata": {},
                        }
                    )
                elif target_columns:
                    role_bindings.append(
                        {
                            "role": "target",
                            "columns": target_columns,
                            "role_kind": "many_columns",
                            "required": True,
                            "metadata": {},
                        }
                    )
                connection.exec_driver_sql(
                    """
                    INSERT OR REPLACE INTO dataset_column_binding (
                        id,
                        dataset_id,
                        role_bindings,
                        model_key,
                        model_family,
                        model_task_kind,
                        schema_version,
                        created_at
                    )
                    VALUES (?, ?, ?, NULL, NULL, NULL, 1, ?)
                    """,
                    (row[0], row[1], json.dumps(role_bindings), row[4]),
                )
            connection.exec_driver_sql("DROP TABLE dataset_column_selection")
        connection.exec_driver_sql("PRAGMA user_version=7")
    return 7


def migrate_v7_to_v8(engine: Engine) -> int:
    with engine.begin() as connection:
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if "ml_task" in table_names:
            connection.exec_driver_sql(
                "UPDATE ml_task SET task_type='apply' WHERE task_type='inference'"
            )
        if "ml_task_artifact" in table_names:
            connection.exec_driver_sql(
                "UPDATE ml_task_artifact SET artifact_kind='apply_result' WHERE artifact_kind='inference_result'"
            )
        connection.exec_driver_sql("PRAGMA user_version=8")
    return 8


def migrate_v8_to_v9(engine: Engine) -> int:
    with engine.begin() as connection:
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if "ml_task" in table_names:
            task_rows = connection.exec_driver_sql(
                "SELECT id, request_payload, result_payload FROM ml_task"
            ).all()
            for row in task_rows:
                request_payload = _migrate_evaluation_payload(_json_object(row[1]))
                result_payload = _migrate_evaluation_payload(_json_object(row[2]))
                connection.exec_driver_sql(
                    """
                    UPDATE ml_task
                    SET request_payload=?, result_payload=?
                    WHERE id=?
                    """,
                    (
                        json.dumps(request_payload),
                        json.dumps(result_payload) if row[2] is not None else None,
                        row[0],
                    ),
                )

        if "trained_model" in table_names:
            rows = connection.exec_driver_sql(
                """
                SELECT
                    id,
                    dataset_id,
                    ml_task_id,
                    model_key,
                    problem_kind,
                    artifact_path,
                    metadata_payload,
                    created_at,
                    updated_at
                FROM trained_model
                """
            ).all()
            connection.exec_driver_sql("DROP TABLE trained_model")
            connection.exec_driver_sql(
                """
                CREATE TABLE trained_model (
                    id VARCHAR NOT NULL PRIMARY KEY,
                    dataset_id VARCHAR,
                    ml_task_id VARCHAR NOT NULL,
                    model_key VARCHAR NOT NULL,
                    problem_kind VARCHAR,
                    artifact_path VARCHAR NOT NULL,
                    metadata_payload JSON NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY(dataset_id) REFERENCES dataset (id),
                    FOREIGN KEY(ml_task_id) REFERENCES ml_task (id)
                )
                """
            )
            for row in rows:
                problem_kind = str(row[4]) if row[4] is not None else ""
                normalized_problem_kind = None if problem_kind == "analysis" else (problem_kind or None)
                metadata_payload = _json_object(row[6])
                metadata_payload.setdefault(
                    "evaluation_kind",
                    _evaluation_kind_for_problem_kind(problem_kind),
                )
                connection.exec_driver_sql(
                    """
                    INSERT INTO trained_model (
                        id,
                        dataset_id,
                        ml_task_id,
                        model_key,
                        problem_kind,
                        artifact_path,
                        metadata_payload,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row[0],
                        row[1],
                        row[2],
                        row[3],
                        normalized_problem_kind,
                        row[5],
                        json.dumps(metadata_payload),
                        row[7],
                        row[8],
                    ),
                )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_trained_model_dataset_id "
                "ON trained_model (dataset_id)"
            )
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_trained_model_ml_task_id "
                "ON trained_model (ml_task_id)"
            )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_trained_model_model_key "
                "ON trained_model (model_key)"
            )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_trained_model_problem_kind "
                "ON trained_model (problem_kind)"
            )
        connection.exec_driver_sql("PRAGMA user_version=9")
    return 9


def run_migrations(engine: Engine) -> int:
    current_version = get_user_version(engine)
    if current_version == 0:
        return bootstrap_current_schema(engine)
    if current_version == 1:
        current_version = migrate_v1_to_v2(engine)
    if current_version == 2:
        current_version = migrate_v2_to_v3(engine)
    if current_version == 3:
        current_version = migrate_v3_to_v4(engine)
    if current_version == 4:
        current_version = migrate_v4_to_v5(engine)
    if current_version == 5:
        current_version = migrate_v5_to_v6(engine)
    if current_version == 6:
        current_version = migrate_v6_to_v7(engine)
    if current_version == 7:
        current_version = migrate_v7_to_v8(engine)
    if current_version == 8:
        current_version = migrate_v8_to_v9(engine)
    if current_version == CURRENT_SCHEMA_VERSION:
        return current_version
    raise ValidationError(
        f"Local schema version {current_version} belongs to an obsolete development baseline. "
        f"Delete the local database and restart the app to bootstrap schema v{CURRENT_SCHEMA_VERSION}."
    )


def _json_list(value: object) -> list[str]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = []
    else:
        parsed = value
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item)]


def _json_object(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
    else:
        parsed = value
    if not isinstance(parsed, dict):
        return {}
    return dict(parsed)


def _evaluation_kind_for_problem_kind(problem_kind: object) -> str:
    if problem_kind == "regression":
        return "regression"
    if problem_kind == "classification":
        return "classification"
    if problem_kind in {"clustering", "anomaly_detection", "analysis"}:
        return "summary"
    return "none"


def _migrate_evaluation_payload(payload: dict[str, object]) -> dict[str, object]:
    problem_kind = payload.pop("problem_kind", None)
    evaluation_policy = payload.get("evaluation_policy")
    has_evaluation_contract = (
        problem_kind is not None
        or "evaluation_kind" in payload
        or isinstance(evaluation_policy, dict)
    )
    if not has_evaluation_contract:
        return payload
    if "evaluation_kind" not in payload:
        payload["evaluation_kind"] = _evaluation_kind_for_problem_kind(problem_kind)
    if isinstance(evaluation_policy, dict):
        policy_problem_kind = evaluation_policy.pop("problem_kind", problem_kind)
        if "evaluation_kind" not in evaluation_policy:
            evaluation_policy["evaluation_kind"] = _evaluation_kind_for_problem_kind(policy_problem_kind)
    return payload
