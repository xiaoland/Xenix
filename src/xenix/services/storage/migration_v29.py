"""Add audit provenance without inventing historical explanations or execution values."""

import json

from sqlalchemy.engine import Engine


def migrate_v28_to_v29(engine: Engine) -> int:
    with engine.begin() as connection:
        # sqlite3 legacy transaction mode does not start a transaction for DDL.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        tables = {row[0] for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, fields in {
            "dataset_derivation": {"origin_thread_id": "INTEGER"},
            "ml_task": {
                "origin_thread_id": "INTEGER",
                "origin_tool_call_message_id": "INTEGER",
                "agent_explanation": "VARCHAR",
                "submitted_parameters": "JSON",
            },
        }.items():
            if table not in tables:
                continue
            for name, sql_type in fields.items():
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")
                if name.startswith("origin_"):
                    connection.exec_driver_sql(f"CREATE INDEX ix_{table}_{name} ON {table} ({name})")
        connection.exec_driver_sql(
            "CREATE TABLE artifact_derivation (artifact_id INTEGER PRIMARY KEY NOT NULL REFERENCES artifact(id), origin_thread_id INTEGER NOT NULL, origin_tool_call_message_id INTEGER, payload JSON NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE audit_explanation (id INTEGER PRIMARY KEY NOT NULL, object_kind VARCHAR NOT NULL, object_id INTEGER NOT NULL, thread_id INTEGER NOT NULL, tool_call_message_id INTEGER, text VARCHAR NOT NULL, evidence JSON NOT NULL, created_at DATETIME NOT NULL)"
        )
        for table, fields in {
            "artifact_derivation": ("origin_thread_id", "origin_tool_call_message_id"),
            "audit_explanation": ("object_kind", "object_id", "thread_id"),
        }.items():
            for field in fields:
                connection.exec_driver_sql(f"CREATE INDEX ix_{table}_{field} ON {table} ({field})")
        # Dataset derivations already record a stable ToolCall identity.
        if "conversation_message" in tables:
            connection.exec_driver_sql(
                "UPDATE dataset_derivation SET origin_thread_id = "
                "(SELECT thread_id FROM conversation_message WHERE id = dataset_derivation.tool_call_message_id)"
            )
            if "ml_task" in tables:
                candidates: dict[int, set[tuple[int, int]]] = {}
                rows = connection.exec_driver_sql(
                    "SELECT c.id, c.thread_id, r.value_payload FROM conversation_message c "
                    "JOIN conversation_message r ON r.tool_call_message_id=c.id "
                    "WHERE c.tool_id IN ('model.train','model.hyper_train','model.apply')"
                )
                for call_id, thread_id, raw in rows:
                    payload = json.loads(raw) if raw else None
                    if not isinstance(payload, dict):
                        continue
                    ids = payload.get("task_ids", [])
                    ids = list(ids) if isinstance(ids, list) else []
                    ids.append(payload.get("ml_task_id"))
                    for task_id in ids:
                        if type(task_id) is int:
                            candidates.setdefault(task_id, set()).add((thread_id, call_id))
                for task_id, origins in candidates.items():
                    if len(origins) == 1:
                        thread_id, call_id = next(iter(origins))
                        connection.exec_driver_sql(
                            "UPDATE ml_task SET origin_thread_id=?, origin_tool_call_message_id=? WHERE id=?",
                            (thread_id, call_id, task_id),
                        )
                # Follow only the retained model's explicit evaluation relationship.
                if "trained_model" in tables:
                    for root_id, raw in connection.exec_driver_sql(
                        "SELECT ml_task_id, metadata_payload FROM trained_model"
                    ):
                        metadata = json.loads(raw) if raw else {}
                        evaluation_id = metadata.get("evaluation_ml_task_id")
                        if type(evaluation_id) is int and len(candidates.get(root_id, set())) == 1:
                            thread_id, call_id = next(iter(candidates[root_id]))
                            connection.exec_driver_sql(
                                "UPDATE ml_task SET origin_thread_id=?, origin_tool_call_message_id=? "
                                "WHERE id=? AND origin_thread_id IS NULL",
                                (thread_id, call_id, evaluation_id),
                            )
        connection.exec_driver_sql("PRAGMA user_version=29")
    return 29
