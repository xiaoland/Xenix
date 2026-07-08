from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from ...exceptions import ValidationError
from . import models  # noqa: F401

CURRENT_SCHEMA_VERSION = 14


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


def migrate_v9_to_v10(engine: Engine) -> int:
    with engine.begin() as connection:
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if "ml_task" in table_names:
            inspect_task_ids = [
                str(row[0])
                for row in connection.exec_driver_sql(
                    "SELECT id FROM ml_task WHERE task_type IN ('INSPECT_DATASET', 'inspect_dataset')"
                ).all()
            ]
            if inspect_task_ids and "dataset" in table_names:
                dataset_columns = {
                    str(row[1])
                    for row in connection.exec_driver_sql("PRAGMA table_info(dataset)").all()
                }
                if "ml_task_id" in dataset_columns:
                    for task_id in inspect_task_ids:
                        connection.exec_driver_sql(
                            "UPDATE dataset SET ml_task_id=NULL WHERE ml_task_id=?",
                            (task_id,),
                        )
            if inspect_task_ids and "ml_task_artifact" in table_names:
                for task_id in inspect_task_ids:
                    connection.exec_driver_sql(
                        "DELETE FROM ml_task_artifact WHERE ml_task_id=?",
                        (task_id,),
                    )
            for task_id in inspect_task_ids:
                connection.exec_driver_sql("DELETE FROM ml_task WHERE id=?", (task_id,))

            task_type_pairs = {
                "FIT": "fit",
                "HYPERPARAMETER_TUNING": "hyperparameter_tuning",
                "EVALUATE": "evaluate",
                "APPLY": "apply",
                "INFERENCE": "apply",
                "inference": "apply",
            }
            for old_value, new_value in task_type_pairs.items():
                connection.exec_driver_sql(
                    "UPDATE ml_task SET task_type=? WHERE task_type=?",
                    (new_value, old_value),
                )

            status_pairs = {
                "PENDING": "pending",
                "RUNNING": "running",
                "SUCCEEDED": "succeeded",
                "FAILED": "failed",
                "CANCELLED": "cancelled",
            }
            for old_value, new_value in status_pairs.items():
                connection.exec_driver_sql(
                    "UPDATE ml_task SET status=? WHERE status=?",
                    (new_value, old_value),
                )

        if "ml_task_artifact" in table_names:
            artifact_kind_pairs = {
                "MODEL": "model",
                "HOLDOUT_DATA": "holdout_data",
                "TRAINING_REPORT": "training_report",
                "EVALUATION_REPORT": "evaluation_report",
                "APPLY_RESULT": "apply_result",
                "INFERENCE_RESULT": "apply_result",
                "inference_result": "apply_result",
                "EXPORT_FILE": "export_file",
                "OTHER": "other",
            }
            for old_value, new_value in artifact_kind_pairs.items():
                connection.exec_driver_sql(
                    "UPDATE ml_task_artifact SET artifact_kind=? WHERE artifact_kind=?",
                    (new_value, old_value),
                )

        connection.exec_driver_sql("PRAGMA user_version=10")
    return 10


def migrate_v10_to_v11(engine: Engine) -> int:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS agent_provider_request (
                id VARCHAR NOT NULL PRIMARY KEY,
                thread_id VARCHAR NOT NULL,
                turn_id VARCHAR NOT NULL,
                run_id VARCHAR,
                provider_name VARCHAR,
                model VARCHAR,
                request_kind VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                input_message_ids JSON NOT NULL,
                output_message_ids JSON NOT NULL,
                usage_payload JSON,
                created_at DATETIME NOT NULL,
                completed_at DATETIME,
                FOREIGN KEY(thread_id) REFERENCES agent_thread (id),
                FOREIGN KEY(turn_id) REFERENCES agent_turn (id),
                FOREIGN KEY(run_id) REFERENCES agent_run (id)
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_agent_provider_request_thread_id "
            "ON agent_provider_request (thread_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_agent_provider_request_turn_id "
            "ON agent_provider_request (turn_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_agent_provider_request_run_id "
            "ON agent_provider_request (run_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_agent_provider_request_provider_name "
            "ON agent_provider_request (provider_name)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_agent_provider_request_model "
            "ON agent_provider_request (model)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_agent_provider_request_request_kind "
            "ON agent_provider_request (request_kind)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_agent_provider_request_status "
            "ON agent_provider_request (status)"
        )
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if {"agent_thread", "agent_turn", "agent_message"}.issubset(table_names):
            thread_rows = connection.exec_driver_sql(
                """
                SELECT id, system_prompt, created_at
                FROM agent_thread
                """
            ).all()
            for thread_row in thread_rows:
                thread_id = str(thread_row[0])
                has_system_message = connection.exec_driver_sql(
                    """
                    SELECT 1
                    FROM agent_message
                    WHERE thread_id=? AND kind IN ('SYSTEM', 'system')
                    LIMIT 1
                    """,
                    (thread_id,),
                ).first()
                if has_system_message is not None:
                    continue
                first_turn = connection.exec_driver_sql(
                    """
                    SELECT id, created_at
                    FROM agent_turn
                    WHERE thread_id=?
                    ORDER BY sequence_index
                    LIMIT 1
                    """,
                    (thread_id,),
                ).first()
                if first_turn is None:
                    continue
                timestamp = first_turn[1] or thread_row[2]
                system_prompt = str(thread_row[1] or models.DEFAULT_AGENT_THREAD_SYSTEM_PROMPT)
                connection.exec_driver_sql(
                    "UPDATE agent_message SET sequence_index=sequence_index + 1 WHERE thread_id=?",
                    (thread_id,),
                )
                connection.exec_driver_sql(
                    """
                    INSERT INTO agent_message (
                        id,
                        thread_id,
                        turn_id,
                        sequence_index,
                        kind,
                        ui_author,
                        content_blocks,
                        provider_payload,
                        status,
                        created_at,
                        updated_at,
                        finalized_at
                    )
                    VALUES (?, ?, ?, 0, 'SYSTEM', 'SYSTEM', ?, '{}', 'completed', ?, ?, ?)
                    """,
                    (
                        uuid4().hex,
                        thread_id,
                        first_turn[0],
                        json.dumps([{"type": "text", "text": system_prompt}]),
                        timestamp,
                        timestamp,
                        timestamp,
                    ),
                )
        connection.exec_driver_sql("PRAGMA user_version=11")
    return 11


def migrate_v11_to_v12(engine: Engine) -> int:
    with engine.begin() as connection:
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if "agent_message" in table_names:
            kind_pairs = {
                "system": "SYSTEM",
                "user": "USER",
                "assistant": "ASSISTANT",
                "tool_call": "TOOL_CALL",
                "tool_call_result": "TOOL_CALL_RESULT",
            }
            for old_value, new_value in kind_pairs.items():
                connection.exec_driver_sql(
                    "UPDATE agent_message SET kind=? WHERE kind=?",
                    (new_value, old_value),
                )

            author_pairs = {
                "system": "SYSTEM",
                "user": "USER",
                "assistant": "ASSISTANT",
                "tool": "TOOL",
            }
            for old_value, new_value in author_pairs.items():
                connection.exec_driver_sql(
                    "UPDATE agent_message SET ui_author=? WHERE ui_author=?",
                    (new_value, old_value),
                )

        connection.exec_driver_sql("PRAGMA user_version=12")
    return 12


def migrate_v12_to_v13(engine: Engine) -> int:
    with engine.begin() as connection:
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if "agent_thread" in table_names:
            thread_columns = {
                str(row[1])
                for row in connection.exec_driver_sql("PRAGMA table_info(agent_thread)").all()
            }
            if "selected_fq_model_key" not in thread_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE agent_thread ADD COLUMN selected_fq_model_key VARCHAR"
                )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_agent_thread_selected_fq_model_key "
                "ON agent_thread (selected_fq_model_key)"
            )
        connection.exec_driver_sql("PRAGMA user_version=13")
    return 13


def migrate_v13_to_v14(engine: Engine) -> int:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS dataset_import (
                id VARCHAR NOT NULL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                original_path VARCHAR NOT NULL,
                original_file_name VARCHAR NOT NULL,
                source_format VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(project_id) REFERENCES project (id)
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dataset_import_project_id "
            "ON dataset_import (project_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dataset_import_source_format "
            "ON dataset_import (source_format)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dataset_import_status "
            "ON dataset_import (status)"
        )

        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS dataset_workbook (
                id VARCHAR NOT NULL PRIMARY KEY,
                import_id VARCHAR NOT NULL,
                sheet_count INTEGER NOT NULL,
                engine VARCHAR,
                metadata_payload JSON NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(import_id) REFERENCES dataset_import (id)
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dataset_workbook_import_id "
            "ON dataset_workbook (import_id)"
        )

        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if "dataset" in table_names:
            dataset_columns = {
                str(row[1])
                for row in connection.exec_driver_sql("PRAGMA table_info(dataset)").all()
            }
            new_columns = {
                "import_id": "VARCHAR",
                "workbook_id": "VARCHAR",
                "sheet_name": "VARCHAR",
                "sheet_index": "INTEGER",
            }
            for column_name, column_type in new_columns.items():
                if column_name not in dataset_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE dataset ADD COLUMN {column_name} {column_type}"
                    )
            for column_name in new_columns:
                connection.exec_driver_sql(
                    f"CREATE INDEX IF NOT EXISTS ix_dataset_{column_name} "
                    f"ON dataset ({column_name})"
                )
        connection.exec_driver_sql("PRAGMA user_version=14")
    return 14


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
    if current_version == 9:
        current_version = migrate_v9_to_v10(engine)
    if current_version == 10:
        current_version = migrate_v10_to_v11(engine)
    if current_version == 11:
        current_version = migrate_v11_to_v12(engine)
    if current_version == 12:
        current_version = migrate_v12_to_v13(engine)
    if current_version == 13:
        current_version = migrate_v13_to_v14(engine)
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
