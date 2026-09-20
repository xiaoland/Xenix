import json

import pytest
from sqlalchemy import inspect
from sqlmodel import Session, create_engine

from xenix.services.storage.migration_v29 import migrate_v28_to_v29
from xenix.services.storage.migrations import get_user_version, run_migrations
from xenix.services.storage.models import MLTaskRow, MLTaskStatus


def _prior_database(tmp_path, *, invalid=False):
    engine = create_engine(f"sqlite:///{tmp_path / 'v28.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE dataset_derivation (dataset_id INTEGER PRIMARY KEY, tool_call_message_id INTEGER)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE ml_task (id INTEGER PRIMARY KEY, project_id INTEGER, dataset_id INTEGER, task_type VARCHAR, status VARCHAR, request_payload JSON, result_payload JSON, error_summary VARCHAR, created_at DATETIME, started_at DATETIME, finished_at DATETIME, updated_at DATETIME)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE conversation_message (id INTEGER PRIMARY KEY, thread_id INTEGER, tool_id VARCHAR, tool_call_message_id INTEGER, value_payload JSON)"
        )
        conn.exec_driver_sql("CREATE TABLE trained_model (ml_task_id INTEGER, metadata_payload JSON)")
        conn.exec_driver_sql("CREATE TABLE artifact (id INTEGER PRIMARY KEY)")
        for task_id in (101, 102, 103, 104):
            conn.exec_driver_sql(
                "INSERT INTO ml_task VALUES (?,1,2,'fit','succeeded','{}',NULL,NULL,'2026-09-20',NULL,NULL,'2026-09-20')",
                (task_id,),
            )
        conn.exec_driver_sql(
            "INSERT INTO conversation_message VALUES (10,201,'model.train',NULL,NULL),(11,201,NULL,10,?),(12,202,'model.task.query',NULL,NULL),(13,202,NULL,12,?)",
            ("broken" if invalid else json.dumps({"task_ids": [101]}), json.dumps({"task_ids": [103]})),
        )
        conn.exec_driver_sql("INSERT INTO trained_model VALUES (101,?)", (json.dumps({"evaluation_ml_task_id": 102}),))
        conn.exec_driver_sql("INSERT INTO dataset_derivation VALUES (2,10)")
        conn.exec_driver_sql("PRAGMA user_version=28")
    return engine


def test_upgrade_retains_proven_origin_without_inventing_explanations(tmp_path):
    engine = _prior_database(tmp_path)
    try:
        assert run_migrations(engine) == 29
        assert run_migrations(engine) == 29
        with Session(engine) as session:
            root, evaluation = session.get(MLTaskRow, 101), session.get(MLTaskRow, 102)
            assert root.status is MLTaskStatus.SUCCEEDED
            assert root.origin_thread_id == evaluation.origin_thread_id == 201
            assert root.origin_tool_call_message_id == 10
            assert root.agent_explanation is None
            assert root.submitted_parameters is None
            assert session.get(MLTaskRow, 103).origin_thread_id is None
            assert session.get(MLTaskRow, 104).origin_thread_id is None
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT origin_thread_id FROM dataset_derivation").scalar_one() == 201
    finally:
        engine.dispose()


def test_failed_upgrade_rolls_back_ddl_and_version(tmp_path):
    engine = _prior_database(tmp_path, invalid=True)
    try:
        with pytest.raises(json.JSONDecodeError):
            migrate_v28_to_v29(engine)
        assert get_user_version(engine) == 28
        assert "audit_explanation" not in inspect(engine).get_table_names()
        assert "origin_thread_id" not in {column["name"] for column in inspect(engine).get_columns("ml_task")}
    finally:
        engine.dispose()
