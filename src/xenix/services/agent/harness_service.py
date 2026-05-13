from __future__ import annotations

from dataclasses import dataclass
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
from .providers import AgentProvider, ProviderResponse, ProviderStreamEvent
from .tools import AgentToolRegistry, ToolExecutionContext


class SubmitUserTurnInput(SQLModel):
    thread_id: str | None = None
    text: str
    file_paths: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class AgentHarnessStreamEvent:
    kind: str
    thread_id: str | None = None
    message_id: str | None = None
    delta_text: str = ""
    snapshot: ThreadSnapshot | None = None


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

    def list_threads(self):
        return self._conversation_store.list_threads()

    def get_thread_snapshot(self, thread_id: str) -> ThreadSnapshot:
        return self._conversation_store.get_thread_snapshot(thread_id)

    def set_provider(self, provider: AgentProvider) -> None:
        self._provider = provider

    def submit_user_turn(self, input_data: SubmitUserTurnInput) -> ThreadSnapshot:
        thread_id, turn_id, run_id, file_paths = self._start_user_turn(input_data)

        try:
            snapshot = self._run_provider_loop(
                thread_id=thread_id,
                turn_id=turn_id,
                file_paths=file_paths,
            )
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=run_id,
                    status=AgentRunStatus.SUCCEEDED,
                )
            )
            return snapshot
        except Exception as exc:
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=run_id,
                    status=AgentRunStatus.FAILED,
                    error_summary=str(exc),
                )
            )
            raise

    def submit_user_turn_stream(self, input_data: SubmitUserTurnInput):
        thread_id, turn_id, run_id, file_paths = self._start_user_turn(input_data)
        yield AgentHarnessStreamEvent(
            kind="turn_started",
            thread_id=thread_id,
            snapshot=self._conversation_store.get_thread_snapshot(thread_id),
        )

        try:
            snapshot = yield from self._run_provider_loop_stream(
                thread_id=thread_id,
                turn_id=turn_id,
                file_paths=file_paths,
            )
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=run_id,
                    status=AgentRunStatus.SUCCEEDED,
                )
            )
            yield AgentHarnessStreamEvent(kind="snapshot", thread_id=thread_id, snapshot=snapshot)
        except Exception as exc:
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=run_id,
                    status=AgentRunStatus.FAILED,
                    error_summary=str(exc),
                )
            )
            raise

    def _start_user_turn(self, input_data: SubmitUserTurnInput) -> tuple[str, str, str, list[str]]:
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
        return thread_id, turn.id, run.id, list(input_data.file_paths)


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
                arguments = self._tool_call_arguments(tool_call.tool_name, tool_call.arguments)
                _request_message, persisted_tool_call = self._conversation_store.create_tool_call(
                    CreateToolCallInput(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        tool_name=tool_call.tool_name,
                        arguments_payload=arguments,
                        provider_payload={"tool_call_id": tool_call.provider_call_id},
                    )
                )
                try:
                    result = self._tool_registry.execute(
                        tool_call.tool_name,
                        arguments,
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

    def _run_provider_loop_stream(self, *, thread_id: str, turn_id: str, file_paths: list[str]):
        reminder_sent = False
        for _step in range(16):
            snapshot = self._conversation_store.get_thread_snapshot(thread_id)
            provider_response: ProviderResponse | None = None
            for stream_event in self._provider_stream(snapshot.messages, self._tool_registry.list_specs()):
                if stream_event.delta_text:
                    yield AgentHarnessStreamEvent(
                        kind="assistant_delta",
                        thread_id=thread_id,
                        delta_text=stream_event.delta_text,
                    )
                if stream_event.response is not None:
                    provider_response = stream_event.response

            if provider_response is None:
                raise ValidationError("Provider stream ended without a completed response.")

            if provider_response.assistant_content_blocks:
                assistant_message = self._conversation_store.append_message(
                    AppendAgentMessageInput(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        kind=AgentMessageKind.ASSISTANT,
                        ui_author=AgentMessageAuthor.ASSISTANT,
                        content_blocks=provider_response.assistant_content_blocks,
                        provider_payload=provider_response.raw_payload,
                    )
                )
                yield AgentHarnessStreamEvent(
                    kind="assistant_message_finished",
                    thread_id=thread_id,
                    message_id=assistant_message.id,
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
                arguments = self._tool_call_arguments(tool_call.tool_name, tool_call.arguments)
                _request_message, persisted_tool_call = self._conversation_store.create_tool_call(
                    CreateToolCallInput(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        tool_name=tool_call.tool_name,
                        arguments_payload=arguments,
                        provider_payload={"tool_call_id": tool_call.provider_call_id},
                    )
                )
                try:
                    result = self._tool_registry.execute(
                        tool_call.tool_name,
                        arguments,
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

    def _tool_call_arguments(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "turn_end":
            return {}
        return arguments

    def _provider_stream(
        self,
        messages: list[Any],
        tools: list[Any],
    ):
        stream = getattr(self._provider, "stream", None)
        if callable(stream):
            yield from stream(messages, tools)
            return
        yield ProviderStreamEvent(response=self._provider.complete(messages, tools))

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
