from __future__ import annotations

import json

from sqlalchemy.engine import Engine

from ....exceptions import ValidationError
from ._helpers import _json_object, _table_columns, _table_names


def _require_legacy_shape(connection) -> None:
    required = {
        "agent_thread": {"id", "title", "system_prompt", "selected_fq_model_key", "created_at", "updated_at"},
        "agent_turn": {"id", "thread_id", "sequence_index", "status", "user_message_id", "created_at", "ended_at", "updated_at"},
        "agent_message": {
            "id", "thread_id", "turn_id", "sequence_index", "kind", "ui_author",
            "content_blocks", "provider_payload", "status", "created_at", "updated_at", "finalized_at",
        },
        "agent_run": {"id", "thread_id", "turn_id", "status", "provider_name", "started_at", "finished_at", "error_summary", "usage_payload"},
        "agent_tool_call": {
            "id", "thread_id", "turn_id", "request_message_id", "result_message_id", "tool_name",
            "status", "arguments_payload", "result_payload", "error_summary", "created_at", "updated_at",
        },
        "agent_turn_completion_guard": {"id", "turn_id", "attempt_index", "input", "output", "created_at"},
        "agent_provider_request": {
            "id", "thread_id", "turn_id", "run_id", "provider_name", "model", "request_kind", "status",
            "input_message_ids", "output_message_ids", "usage_payload", "created_at", "completed_at",
        },
        "artifact": {
            "id", "thread_id", "turn_id", "message_id", "tool_call_id", "kind", "title", "absolute_path",
            "mime_type", "summary", "preview_payload", "metadata_payload", "ready_to_open", "created_at",
        },
    }
    tables = _table_names(connection)
    missing_tables = sorted(set(required) - tables)
    if missing_tables:
        raise ValidationError(
            "Unsupported v14 database: missing required tables " + ", ".join(missing_tables)
        )
    for table_name, columns in required.items():
        missing_columns = sorted(columns - _table_columns(connection, table_name))
        if missing_columns:
            raise ValidationError(
                f"Unsupported v14 database: {table_name} is missing columns {', '.join(missing_columns)}"
            )


def _content_text(value: object) -> str | None:
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = []
    if not isinstance(parsed, list):
        return None
    parts = [
        str(block.get("text", ""))
        for block in parsed
        if isinstance(block, dict) and block.get("type") in {"text", "markdown"}
    ]
    text_value = "\n".join(part for part in parts if part)
    return text_value or None


def _provider_field(payload: object, key: str) -> str | None:
    parsed = _json_object(payload)
    value = parsed.get(key)
    return value if isinstance(value, str) and value else None


def _create_v15_tables(connection) -> None:
    connection.exec_driver_sql(
        """
        CREATE TABLE conversation_thread (
            id VARCHAR NOT NULL PRIMARY KEY,
            title VARCHAR,
            system_prompt VARCHAR NOT NULL,
            selected_fq_model_key VARCHAR,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
        """
    )
    connection.exec_driver_sql(
        """
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
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TRIGGER conversation_message_tool_result_guard
        BEFORE INSERT ON conversation_message
        WHEN NEW.kind = 'tool_result' AND (
            NEW.tool_call_message_id IS NULL
            OR NOT EXISTS (
                SELECT 1 FROM conversation_message call
                WHERE call.id = NEW.tool_call_message_id
                  AND call.thread_id = NEW.thread_id
                  AND call.kind = 'tool_call'
            )
        )
        BEGIN
            SELECT RAISE(ABORT, 'tool result must reference a same-thread tool call');
        END
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TRIGGER conversation_message_final_immutable
        BEFORE UPDATE ON conversation_message
        WHEN OLD.kind <> 'pending_llm_sampling' OR NEW.kind <> 'pending_llm_sampling'
        BEGIN
            SELECT RAISE(ABORT, 'final conversation messages are immutable');
        END
        """
    )
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX ux_conversation_message_pending_thread "
        "ON conversation_message (thread_id) WHERE kind='pending_llm_sampling'"
    )
    for index_sql in (
        "CREATE INDEX ix_conversation_thread_title ON conversation_thread (title)",
        "CREATE INDEX ix_conversation_thread_selected_fq_model_key ON conversation_thread (selected_fq_model_key)",
        "CREATE INDEX ix_conversation_message_thread_id ON conversation_message (thread_id)",
        "CREATE INDEX ix_conversation_message_sequence_index ON conversation_message (sequence_index)",
        "CREATE INDEX ix_conversation_message_kind ON conversation_message (kind)",
        "CREATE INDEX ix_conversation_message_client_submission_id ON conversation_message (client_submission_id)",
        "CREATE INDEX ix_conversation_message_provider_call_id ON conversation_message (provider_call_id)",
        "CREATE INDEX ix_conversation_message_tool_id ON conversation_message (tool_id)",
        "CREATE INDEX ix_conversation_message_tool_call_message_id ON conversation_message (tool_call_message_id)",
        "CREATE INDEX ix_conversation_message_result_status ON conversation_message (result_status)",
    ):
        connection.exec_driver_sql(index_sql)

    connection.exec_driver_sql(
        """
        CREATE TABLE artifact_v15 (
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
        )
        """
    )


def _ensure_v15_triggers(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS conversation_message_tool_result_guard
            BEFORE INSERT ON conversation_message
            WHEN NEW.kind = 'tool_result' AND (
                NEW.tool_call_message_id IS NULL
                OR NOT EXISTS (
                    SELECT 1 FROM conversation_message call
                    WHERE call.id = NEW.tool_call_message_id
                      AND call.thread_id = NEW.thread_id
                      AND call.kind = 'tool_call'
                )
            )
            BEGIN
                SELECT RAISE(ABORT, 'tool result must reference a same-thread tool call');
            END
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS conversation_message_final_immutable
            BEFORE UPDATE ON conversation_message
            WHEN OLD.kind <> 'pending_llm_sampling' OR NEW.kind <> 'pending_llm_sampling'
            BEGIN
                SELECT RAISE(ABORT, 'final conversation messages are immutable');
            END
            """
        )


def _copy_v14_rows(connection) -> None:
    """Rebuild conversation_message rows from legacy agent_message / agent_tool_call.

    A tool_call is carried over only when its agent_tool_call and its matching
    terminal tool_call_result both exist; otherwise the remainder of the turn is
    discarded (cut_until_user) up to the next user message, because an incomplete
    tool-call chain cannot be reconstructed into the append-only v15 contract
    without inventing state.
    """
    connection.exec_driver_sql(
        """
        INSERT INTO artifact_v15 (
            id, kind, title, absolute_path, mime_type, summary,
            preview_payload, metadata_payload, ready_to_open, created_at
        )
        SELECT id, kind, title, absolute_path, mime_type, summary,
               preview_payload, metadata_payload, ready_to_open, created_at
        FROM artifact
        """
    )
    connection.exec_driver_sql(
        """
        INSERT INTO conversation_thread (
            id, title, system_prompt, selected_fq_model_key, created_at, updated_at
        )
        SELECT id, title, system_prompt, selected_fq_model_key, created_at, updated_at
        FROM agent_thread
        """
    )
    tool_rows = {
        str(row[0]): row
        for row in connection.exec_driver_sql(
            "SELECT id, request_message_id, result_message_id, tool_name, status, arguments_payload, result_payload, error_summary "
            "FROM agent_tool_call"
        ).all()
    }
    result_rows = {
        str(row[0]): row
        for row in connection.exec_driver_sql(
            "SELECT id, thread_id, turn_id, sequence_index, content_blocks, provider_payload, status, created_at "
            "FROM agent_message WHERE kind IN ('tool_call_result','TOOL_CALL_RESULT')"
        ).all()
    }
    messages_by_thread: dict[str, list[tuple]] = {}
    for row in connection.exec_driver_sql(
        "SELECT id, thread_id, turn_id, sequence_index, kind, content_blocks, provider_payload, status, created_at "
        "FROM agent_message ORDER BY thread_id, sequence_index, id"
    ).all():
        messages_by_thread.setdefault(str(row[1]), []).append(row)

    for thread_id, messages in messages_by_thread.items():
        target_sequence = 0
        cut_until_user = False
        for row in messages:
            message_id, _thread, _turn, _old_sequence, raw_kind, blocks, payload, status, created_at = row
            kind = str(raw_kind).lower()
            if kind == "system":
                continue
            if kind in {"tool_call_result", "tool_result"}:
                continue
            if cut_until_user and kind != "user":
                continue
            if kind == "tool_call":
                tool = next((candidate for candidate in tool_rows.values() if str(candidate[1]) == str(message_id)), None)
                result = tool and result_rows.get(str(tool[2])) if tool else None
                terminal = tool and str(tool[4]).lower() in {"succeeded", "failed", "cancelled"}
                if tool is None or result is None or not terminal:
                    cut_until_user = True
                    continue
                tool_id = str(tool[3])
                arguments = _json_object(tool[5])
                provider_call_id = _provider_field(payload, "tool_call_id")
                provider_name = _provider_field(payload, "provider_name")
                call_payload = {"tool_name": tool_id}
                if provider_name:
                    call_payload["provider_name"] = provider_name
                connection.exec_driver_sql(
                    "INSERT INTO conversation_message (id, thread_id, sequence_index, kind, content_payload, provider_call_id, tool_id, arguments_payload, created_at) VALUES (?, ?, ?, 'tool_call', ?, ?, ?, ?, ?)",
                    (
                        str(message_id),
                        thread_id,
                        target_sequence,
                        json.dumps(call_payload),
                        provider_call_id,
                        tool_id,
                        json.dumps(arguments),
                        created_at,
                    ),
                )
                target_sequence += 1
                result_payload = _json_object(tool[6])
                result_status = str(tool[4]).lower()
                result_error = str(tool[7]) if tool[7] else None
                result_id = str(tool[2])
                connection.exec_driver_sql(
                    "INSERT INTO conversation_message (id, thread_id, sequence_index, kind, content_payload, tool_call_message_id, result_status, value_payload, error_summary, created_at) VALUES (?, ?, ?, 'tool_result', ?, ?, ?, ?, ?, ?)",
                    (result_id, thread_id, target_sequence, "{}", str(message_id), result_status, json.dumps(result_payload), result_error, result[7]),
                )
                target_sequence += 1
                continue

            target_kind = "user" if kind == "user" else "assistant" if kind == "assistant" else None
            if target_kind is None or str(status).lower() != "completed":
                continue
            raw_blocks = blocks if isinstance(blocks, str) else json.dumps(blocks or [])
            try:
                block_list = json.loads(raw_blocks)
            except json.JSONDecodeError:
                block_list = []
            parsed_blocks = json.dumps({"content_blocks": block_list if isinstance(block_list, list) else []})
            parsed_payload = _json_object(payload)
            submission_id = parsed_payload.get("client_submission_id") if target_kind == "user" else None
            connection.exec_driver_sql(
                "INSERT INTO conversation_message (id, thread_id, sequence_index, kind, client_submission_id, content_payload, text, reasoning, refusal, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(message_id), thread_id, target_sequence, target_kind, submission_id,
                    parsed_blocks,
                    _content_text(blocks) if target_kind == "assistant" else None,
                    _provider_field(payload, "reasoning_content") if target_kind == "assistant" else None,
                    _provider_field(payload, "refusal") if target_kind == "assistant" else None,
                    created_at,
                ),
            )
            target_sequence += 1
            cut_until_user = False


def migrate_v14_to_v15(engine: Engine) -> int:
    with engine.begin() as connection:
        _require_legacy_shape(connection)
        if _table_names(connection) & {"conversation_thread", "conversation_message", "artifact_v15"}:
            raise ValidationError("Unsupported v14 database: target migration tables already exist")
        _create_v15_tables(connection)
        _copy_v14_rows(connection)
        connection.exec_driver_sql("DROP TABLE artifact")
        connection.exec_driver_sql("ALTER TABLE artifact_v15 RENAME TO artifact")
        connection.exec_driver_sql("CREATE INDEX ix_artifact_kind ON artifact (kind)")
        connection.exec_driver_sql("CREATE INDEX ix_artifact_title ON artifact (title)")
        connection.exec_driver_sql("CREATE INDEX ix_artifact_mime_type ON artifact (mime_type)")

        # Drop old children before parents. Null the optional edge that forms
        # the legacy Turn <-> Message foreign-key cycle before dropping either.
        connection.exec_driver_sql("DROP TABLE agent_provider_request")
        connection.exec_driver_sql("DROP TABLE agent_turn_completion_guard")
        connection.exec_driver_sql("DROP TABLE agent_tool_call")
        connection.exec_driver_sql("DROP TABLE agent_run")
        connection.exec_driver_sql("UPDATE agent_turn SET user_message_id=NULL")
        connection.exec_driver_sql("DROP TABLE agent_message")
        connection.exec_driver_sql("DROP TABLE agent_turn")
        connection.exec_driver_sql("DROP TABLE agent_thread")
        connection.exec_driver_sql("PRAGMA user_version=15")
    return 15
