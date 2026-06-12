from __future__ import annotations

from .conversation_store import (
    AppendAgentMessageInput,
    CompleteToolCallInput,
    ConversationStore,
    CreateAgentThreadInput,
    CreateToolCallInput,
    StartTurnInput,
)
from ..storage.models import AgentMessageAuthor, AgentMessageKind, AgentToolCallStatus

MESSAGE_RENDERING_FIXTURE_TITLE = "Mock: Message rendering fixture"
SHORT_HISTORY_FIXTURE_TITLE = "Mock: Short analysis history"


def ensure_mock_conversation_history(store: ConversationStore) -> None:
    existing_titles = {thread.title for thread in store.list_threads()}
    if SHORT_HISTORY_FIXTURE_TITLE not in existing_titles:
        _create_short_history_fixture(store)
    if MESSAGE_RENDERING_FIXTURE_TITLE not in existing_titles:
        _create_message_rendering_fixture(store)


def _create_message_rendering_fixture(store: ConversationStore) -> None:
    thread = store.create_thread(CreateAgentThreadInput(title=MESSAGE_RENDERING_FIXTURE_TITLE))
    first_turn, _user = store.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[
                {
                    "type": "text",
                    "text": "请检查这个销售数据文件，并给我一个后续分析计划。",
                },
                {
                    "type": "dataset",
                    "dataset_id": "mock_dataset_sales",
                    "name": "sales-demand",
                    "file_name": "sales-demand.csv",
                    "source_format": "csv",
                    "row_count": 128,
                    "column_count": 5,
                    "preview_columns": ["price", "traffic", "sales"],
                },
            ],
        )
    )
    store.append_message(
        AppendAgentMessageInput(
            thread_id=thread.id,
            turn_id=first_turn.id,
            kind=AgentMessageKind.ASSISTANT,
            ui_author=AgentMessageAuthor.ASSISTANT,
            content_blocks=[
                {
                    "type": "markdown",
                    "text": (
                        "我会先读取数据结构，然后确认可用于训练的字段。\n\n"
                        "| field | role | note |\n"
                        "| --- | --- | --- |\n"
                        "| `price` | feature | numeric |\n"
                        "| `traffic` | feature | numeric |\n"
                        "| `sales` | target | numeric |"
                    ),
                }
            ],
        )
    )
    _peek_message, peek_call = store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=first_turn.id,
            tool_name="data.peek",
            arguments_payload={"dataset_id": "mock_dataset_sales"},
        )
    )
    store.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=peek_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={
                "dataset_id": "mock_dataset_sales",
                "row_count": 128,
                "column_count": 5,
            },
        )
    )
    store.end_turn(thread.id, first_turn.id)

    second_turn, _second_user = store.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[
                {
                    "type": "text",
                    "text": "用 price 和 traffic 预测 sales，并输出预测结果。",
                }
            ],
        )
    )
    store.append_message(
        AppendAgentMessageInput(
            thread_id=thread.id,
            turn_id=second_turn.id,
            kind=AgentMessageKind.ASSISTANT,
            ui_author=AgentMessageAuthor.ASSISTANT,
            content_blocks=[
                {
                    "type": "markdown",
                    "text": "我会训练一个回归模型，然后用上传的未来计划表生成预测。",
                }
            ],
        )
    )
    _selection_message, selection_call = store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=second_turn.id,
            tool_name="data.feature.select",
            arguments_payload={
                "dataset_id": "mock_dataset_sales",
                "model_key": "regression.linear",
                "role_bindings": [
                    {
                        "role": "feature",
                        "columns": ["price", "traffic"],
                        "role_kind": "many_columns",
                    },
                    {
                        "role": "target",
                        "columns": ["sales"],
                        "role_kind": "single_column",
                    },
                ],
            },
        )
    )
    store.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=selection_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={
                "binding_id": "mock_binding_sales",
                "dataset_id": "mock_dataset_sales",
                "model_key": "regression.linear",
                "model_family": "supervised",
                "model_task_kind": "predictor",
                "role_bindings": [
                    {
                        "role": "feature",
                        "columns": ["price", "traffic"],
                        "role_kind": "many_columns",
                    },
                    {
                        "role": "target",
                        "columns": ["sales"],
                        "role_kind": "single_column",
                    },
                ],
            },
            content_blocks=[
                {
                    "type": "markdown",
                    "text": "Binding id: `mock_binding_sales`\n\nBound roles: feature, target",
                }
            ],
        )
    )
    _train_message, train_call = store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=second_turn.id,
            tool_name="model.train",
            arguments_payload={
                "binding_id": "mock_binding_sales",
                "models": ["regression.linear"],
            },
        )
    )
    store.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=train_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={
                "trained_models": [
                    {
                        "trained_model_id": "mock_linear_model",
                        "model_key": "regression.linear",
                    }
                ]
            },
            content_blocks=[
                {
                    "type": "markdown",
                    "text": "训练完成。`regression.linear` 的 R2 为 `0.91`。",
                }
            ],
        )
    )
    _apply_message, apply_call = store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=second_turn.id,
            tool_name="model.apply",
            arguments_payload={
                "trained_model_id": "mock_linear_model",
                "input_files": ["C:/mock-data/future-plan.csv"],
            },
        )
    )
    store.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=apply_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={
                "artifact_id": "mock-apply-results",
                "row_count": 12,
            },
        )
    )
    store.append_message(
        AppendAgentMessageInput(
            thread_id=thread.id,
            turn_id=second_turn.id,
            kind=AgentMessageKind.ASSISTANT,
            ui_author=AgentMessageAuthor.ASSISTANT,
            content_blocks=[
                {
                    "type": "markdown",
                    "text": (
                        "分析完成。你可以打开预测结果，也可以继续要求我解释关键驱动因素。"
                    ),
                }
            ],
        )
    )
    store.end_turn(thread.id, second_turn.id)


def _create_short_history_fixture(store: ConversationStore) -> None:
    thread = store.create_thread(CreateAgentThreadInput(title=SHORT_HISTORY_FIXTURE_TITLE))
    turn, _user = store.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "快速总结这个客户分群结果。"}],
        )
    )
    store.append_message(
        AppendAgentMessageInput(
            thread_id=thread.id,
            turn_id=turn.id,
            kind=AgentMessageKind.ASSISTANT,
            ui_author=AgentMessageAuthor.ASSISTANT,
            content_blocks=[
                {
                    "type": "markdown",
                    "text": "当前分群结果包含 3 个主要客群：高价值、价格敏感、低频浏览。",
                }
            ],
        )
    )
    store.end_turn(thread.id, turn.id)
