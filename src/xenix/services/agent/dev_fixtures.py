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
                    "type": "file",
                    "path": "C:/mock-data/sales-demand.csv",
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
            arguments_payload={"source_path": "C:/mock-data/sales-demand.csv"},
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
                "artifact_link": "[sales-demand.csv](artifact://mock-sales-dataset?view=preview)",
            },
            content_blocks=[
                {
                    "type": "markdown",
                    "text": (
                        "数据预览已就绪：[sales-demand.csv](artifact://mock-sales-dataset?view=preview)\n\n"
                        "Rows: 128; columns: `date`, `price`, `traffic`, `campaign`, `sales`"
                    ),
                },
                {
                    "type": "tool_result_payload",
                    "payload": {
                        "dataset_id": "mock_dataset_sales",
                        "artifact_link": "[sales-demand.csv](artifact://mock-sales-dataset?view=preview)",
                    },
                },
            ],
        )
    )
    _turn_end_message, turn_end_call = store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=first_turn.id,
            tool_name="turn_end",
            arguments_payload={"summary": "数据检查完成，等待用户确认特征和目标列。"},
        )
    )
    turn_end_result, _completed = store.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=turn_end_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={"turn_end": True},
            content_blocks=[
                {
                    "type": "turn_end",
                    "summary": "数据检查完成，等待用户确认特征和目标列。",
                }
            ],
        )
    )
    store.end_turn(thread.id, first_turn.id, turn_end_result.id)

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
    _train_message, train_call = store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=second_turn.id,
            tool_name="model.train",
            arguments_payload={
                "dataset_id": "mock_dataset_sales",
                "feature_columns": ["price", "traffic"],
                "target_columns": ["sales"],
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
    _inference_message, inference_call = store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=second_turn.id,
            tool_name="model.inference",
            arguments_payload={
                "dataset_id": "mock_dataset_sales",
                "trained_model_id": "mock_linear_model",
                "input_files": ["C:/mock-data/future-plan.csv"],
            },
        )
    )
    store.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=inference_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={
                "artifact_link": "[prediction-results.csv](artifact://mock-predictions?view=preview)",
                "row_count": 12,
            },
            content_blocks=[
                {
                    "type": "markdown",
                    "text": "预测结果已生成：[prediction-results.csv](artifact://mock-predictions?view=preview)",
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
                    "text": (
                        "分析完成。你可以打开预测结果，也可以继续要求我解释关键驱动因素。"
                    ),
                }
            ],
        )
    )
    _second_end_message, second_end_call = store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=second_turn.id,
            tool_name="turn_end",
            arguments_payload={"summary": "训练和预测流程完成。"},
        )
    )
    second_end_result, _second_completed = store.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=second_end_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={"turn_end": True},
            content_blocks=[{"type": "turn_end", "summary": "训练和预测流程完成。"}],
        )
    )
    store.end_turn(thread.id, second_turn.id, second_end_result.id)


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
    _end_message, end_call = store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name="turn_end",
            arguments_payload={"summary": "摘要完成。"},
        )
    )
    end_result, _completed = store.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=end_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={"turn_end": True},
            content_blocks=[{"type": "turn_end", "summary": "摘要完成。"}],
        )
    )
    store.end_turn(thread.id, turn.id, end_result.id)
