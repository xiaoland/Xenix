from __future__ import annotations

import json

from sqlalchemy.engine import Connection, Engine


def get_user_version(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())


def set_user_version(engine: Engine, version: int) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(f"PRAGMA user_version={version}")


def _table_names(connection: Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).all()
    }


def _table_columns(connection: Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})").all()
    }


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
