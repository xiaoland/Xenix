from __future__ import annotations

from typing import Any

from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel

from ...exceptions import ValidationError
from ..storage.models import (
    AgentMessageAuthor,
    AgentMessageKind,
    AgentRunStatus,
    AgentToolCallStatus,
)
from .conversation_store import (
    AppendAgentMessageInput,
    CompleteToolCallInput,
    ConversationStore,
    CreateAgentThreadInput,
    CreateToolCallInput,
    FinishAgentRunInput,
    StartAgentRunInput,
    StartTurnInput,
    ThreadSnapshot,
)
from .providers import AgentProvider
from .tools import AgentToolRegistry, ToolExecutionContext


class SubmitUserTurnInput(SQLModel):
    thread_id: str | None = None
    text: str
    file_paths: list[str] = Field(default_factory=list)


class AgentHarnessService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        provider: AgentProvider,
        tool_registry: AgentToolRegistry,
        conversation_store: ConversationStore | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._tool_registry = tool_registry
        self._conversation_store = conversation_store or ConversationStore(session_factory)

    def create_thread(self, title: str | None = None) -> ThreadSnapshot:
        thread = self._conversation_store.create_thread(CreateAgentThreadInput(title=title))
        return self._conversation_store.get_thread_snapshot(thread.id)

    def submit_user_turn(self, input_data: SubmitUserTurnInput) -> ThreadSnapshot:
        text = input_data.text.strip()
        if not text and not input_data.file_paths:
            raise ValidationError("A turn needs a user message or at least one file.")

        thread_id = input_data.thread_id
        if thread_id is None:
            thread_id = self._conversation_store.create_thread(CreateAgentThreadInput(title=self._title_from_text(text))).id

        content_blocks = self._user_content_blocks(text, input_data.file_paths)
        turn, _user_message = self._conversation_store.start_turn(
            StartTurnInput(
                thread_id=thread_id,
                user_content_blocks=content_blocks,
            )
        )
        run = self._conversation_store.start_run(
            StartAgentRunInput(
                thread_id=thread_id,
                turn_id=turn.id,
                provider_name=type(self._provider).__name__,
            )
        )

        try:
            snapshot = self._run_provider_loop(
                thread_id=thread_id,
                turn_id=turn.id,
                file_paths=list(input_data.file_paths),
            )
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=run.id,
                    status=AgentRunStatus.SUCCEEDED,
                )
            )
            return snapshot
        except Exception as exc:
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=run.id,
                    status=AgentRunStatus.FAILED,
                    error_summary=str(exc),
                )
            )
            raise

    def _run_provider_loop(self, *, thread_id: str, turn_id: str, file_paths: list[str]) -> ThreadSnapshot:
        reminder_sent = False
        for _step in range(16):
            snapshot = self._conversation_store.get_thread_snapshot(thread_id)
            provider_response = self._provider.complete(snapshot.messages, self._tool_registry.list_specs())
            if provider_response.assistant_content_blocks:
                self._conversation_store.append_message(
                    AppendAgentMessageInput(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        kind=AgentMessageKind.ASSISTANT,
                        ui_author=AgentMessageAuthor.ASSISTANT,
                        content_blocks=provider_response.assistant_content_blocks,
                        provider_payload=provider_response.raw_payload,
                    )
                )

            if not provider_response.tool_calls:
                if reminder_sent:
                    raise ValidationError("Provider stopped without calling turn_end.")
                self._conversation_store.append_message(
                    AppendAgentMessageInput(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        kind=AgentMessageKind.SYSTEM,
                        ui_author=AgentMessageAuthor.SYSTEM,
                        content_blocks=[
                            {
                                "type": "text",
                                "text": "If the turn is complete and user input is needed, call turn_end.",
                            }
                        ],
                    )
                )
                reminder_sent = True
                continue

            for tool_call in provider_response.tool_calls:
                _request_message, persisted_tool_call = self._conversation_store.create_tool_call(
                    CreateToolCallInput(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        tool_name=tool_call.tool_name,
                        arguments_payload=tool_call.arguments,
                        provider_payload={"tool_call_id": tool_call.provider_call_id},
                    )
                )
                try:
                    result = self._tool_registry.execute(
                        tool_call.tool_name,
                        tool_call.arguments,
                        ToolExecutionContext(
                            thread_id=thread_id,
                            turn_id=turn_id,
                            tool_call_id=persisted_tool_call.id,
                            attached_files=file_paths,
                        ),
                    )
                    status = AgentToolCallStatus.SUCCEEDED
                    error_summary = None
                except Exception as exc:
                    result = self._tool_error_result(exc)
                    status = AgentToolCallStatus.FAILED
                    error_summary = str(exc)

                result_message, _completed = self._conversation_store.complete_tool_call(
                    CompleteToolCallInput(
                        tool_call_id=persisted_tool_call.id,
                        status=status,
                        result_payload=result.payload,
                        error_summary=error_summary,
                        content_blocks=[
                            *result.content_blocks,
                            {"type": "tool_result_payload", "payload": result.payload},
                        ],
                        provider_payload={"tool_call_id": tool_call.provider_call_id},
                    )
                )
                if tool_call.tool_name == "turn_end" and status is AgentToolCallStatus.SUCCEEDED:
                    self._conversation_store.end_turn(thread_id, turn_id, result_message.id)
                    return self._conversation_store.get_thread_snapshot(thread_id)

        raise ValidationError("Provider exceeded the maximum number of tool-calling steps.")

    def _tool_error_result(self, exc: Exception):
        from .tools import ToolExecutionResult

        return ToolExecutionResult(
            payload={"error": str(exc)},
            content_blocks=[{"type": "markdown", "text": f"Tool failed: {exc}"}],
        )

    def _user_content_blocks(self, text: str, file_paths: list[str]) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        if text:
            blocks.append({"type": "text", "text": text})
        for file_path in file_paths:
            blocks.append({"type": "file", "path": file_path})
        return blocks

    def _title_from_text(self, text: str) -> str | None:
        if not text:
            return "New analysis"
        return text[:80]
