from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel

from ...exceptions import NotFoundError, ValidationError
from ..storage.models import (
    AgentMessageAuthor,
    AgentMessageKind,
    AgentMessageRow,
    AgentRunRow,
    AgentRunStatus,
    AgentThreadRow,
    AgentToolCallRow,
    AgentToolCallStatus,
    AgentTurnRow,
    AgentTurnStatus,
    ArtifactRow,
)
from ..storage.repositories import AgentConversationRepository, ArtifactRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CreateAgentThreadInput(SQLModel):
    title: str | None = None


class StartTurnInput(SQLModel):
    thread_id: str
    user_content_blocks: list[dict[str, Any]] = Field(default_factory=list)
    provider_payload: dict[str, Any] = Field(default_factory=dict)


class AppendAgentMessageInput(SQLModel):
    thread_id: str
    turn_id: str | None = None
    kind: AgentMessageKind
    ui_author: AgentMessageAuthor
    content_blocks: list[dict[str, Any]] = Field(default_factory=list)
    provider_payload: dict[str, Any] = Field(default_factory=dict)


class CreateToolCallInput(SQLModel):
    thread_id: str
    turn_id: str
    tool_name: str
    arguments_payload: dict[str, Any] = Field(default_factory=dict)
    content_blocks: list[dict[str, Any]] | None = None
    provider_payload: dict[str, Any] = Field(default_factory=dict)


class CompleteToolCallInput(SQLModel):
    tool_call_id: str
    status: AgentToolCallStatus = AgentToolCallStatus.SUCCEEDED
    result_payload: dict[str, Any] | None = None
    error_summary: str | None = None
    content_blocks: list[dict[str, Any]] | None = None
    provider_payload: dict[str, Any] = Field(default_factory=dict)


class StartAgentRunInput(SQLModel):
    thread_id: str
    turn_id: str
    provider_name: str | None = None


class FinishAgentRunInput(SQLModel):
    run_id: str
    status: AgentRunStatus
    error_summary: str | None = None
    usage_payload: dict[str, Any] | None = None


class ThreadSnapshot(SQLModel):
    thread: AgentThreadRow
    turns: list[AgentTurnRow] = Field(default_factory=list)
    messages: list[AgentMessageRow] = Field(default_factory=list)
    tool_calls: list[AgentToolCallRow] = Field(default_factory=list)
    artifacts: list[ArtifactRow] = Field(default_factory=list)


class ConversationStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        self._conversations = AgentConversationRepository()
        self._artifacts = ArtifactRepository()

    def create_thread(self, input_data: CreateAgentThreadInput | None = None) -> AgentThreadRow:
        input_data = input_data or CreateAgentThreadInput()
        title = input_data.title.strip() if input_data.title else None
        now = _utc_now()
        row = AgentThreadRow(title=title, created_at=now, updated_at=now)
        with self._session_factory() as session:
            self._conversations.create_thread(session, row)
            session.commit()
            return row

    def list_threads(self) -> list[AgentThreadRow]:
        with self._session_factory() as session:
            return self._conversations.list_threads(session)

    def get_thread_snapshot(self, thread_id: str) -> ThreadSnapshot:
        with self._session_factory() as session:
            thread = self._conversations.get_thread(session, thread_id)
            if thread is None:
                raise NotFoundError(f"Thread '{thread_id}' was not found.")

            turns = self._conversations.list_turns(session, thread_id)
            messages = self._conversations.list_messages(session, thread_id)
            tool_calls: list[AgentToolCallRow] = []
            for turn in turns:
                tool_calls.extend(self._conversations.list_tool_calls(session, turn.id))
            artifacts = self._artifacts.list_by_thread(session, thread_id)
            return ThreadSnapshot(
                thread=thread,
                turns=turns,
                messages=messages,
                tool_calls=tool_calls,
                artifacts=artifacts,
            )

    def start_turn(self, input_data: StartTurnInput) -> tuple[AgentTurnRow, AgentMessageRow]:
        if not input_data.user_content_blocks:
            raise ValidationError("A turn must start with a user message.")

        now = _utc_now()
        with self._session_factory() as session:
            thread = self._require_thread(session, input_data.thread_id)
            turn = AgentTurnRow(
                thread_id=thread.id,
                sequence_index=self._conversations.next_turn_sequence(session, thread.id),
                status=AgentTurnStatus.OPEN,
                created_at=now,
                updated_at=now,
            )
            self._conversations.create_turn(session, turn)
            message = AgentMessageRow(
                thread_id=thread.id,
                turn_id=turn.id,
                sequence_index=self._conversations.next_message_sequence(session, thread.id),
                kind=AgentMessageKind.USER,
                ui_author=AgentMessageAuthor.USER,
                content_blocks=list(input_data.user_content_blocks),
                provider_payload=dict(input_data.provider_payload),
                created_at=now,
            )
            self._conversations.append_message(session, message)
            self._conversations.set_turn_user_message(session, turn.id, message.id, now)
            self._touch_thread(session, thread, now)
            session.commit()
            return turn, message

    def append_message(self, input_data: AppendAgentMessageInput) -> AgentMessageRow:
        now = _utc_now()
        with self._session_factory() as session:
            thread = self._require_thread(session, input_data.thread_id)
            if input_data.turn_id is not None:
                self._require_open_turn(session, thread.id, input_data.turn_id)

            message = AgentMessageRow(
                thread_id=thread.id,
                turn_id=input_data.turn_id,
                sequence_index=self._conversations.next_message_sequence(session, thread.id),
                kind=input_data.kind,
                ui_author=input_data.ui_author,
                content_blocks=list(input_data.content_blocks),
                provider_payload=dict(input_data.provider_payload),
                created_at=now,
            )
            self._conversations.append_message(session, message)
            self._touch_thread(session, thread, now)
            session.commit()
            return message

    def create_tool_call(self, input_data: CreateToolCallInput) -> tuple[AgentMessageRow, AgentToolCallRow]:
        tool_name = input_data.tool_name.strip()
        if not tool_name:
            raise ValidationError("Tool name cannot be empty.")

        content_blocks = input_data.content_blocks
        if content_blocks is None:
            content_blocks = [
                {
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "arguments": dict(input_data.arguments_payload),
                }
            ]

        now = _utc_now()
        with self._session_factory() as session:
            thread = self._require_thread(session, input_data.thread_id)
            self._require_open_turn(session, thread.id, input_data.turn_id)
            message = AgentMessageRow(
                thread_id=thread.id,
                turn_id=input_data.turn_id,
                sequence_index=self._conversations.next_message_sequence(session, thread.id),
                kind=AgentMessageKind.TOOL_CALL,
                ui_author=AgentMessageAuthor.TOOL,
                content_blocks=content_blocks,
                provider_payload=dict(input_data.provider_payload),
                created_at=now,
            )
            self._conversations.append_message(session, message)
            row = AgentToolCallRow(
                thread_id=thread.id,
                turn_id=input_data.turn_id,
                request_message_id=message.id,
                tool_name=tool_name,
                status=AgentToolCallStatus.REQUESTED,
                arguments_payload=dict(input_data.arguments_payload),
                created_at=now,
                updated_at=now,
            )
            self._conversations.create_tool_call(session, row)
            self._touch_thread(session, thread, now)
            session.commit()
            return message, row

    def complete_tool_call(self, input_data: CompleteToolCallInput) -> tuple[AgentMessageRow, AgentToolCallRow]:
        now = _utc_now()
        with self._session_factory() as session:
            tool_call = self._conversations.get_tool_call(session, input_data.tool_call_id)
            if tool_call is None:
                raise NotFoundError(f"Tool call '{input_data.tool_call_id}' was not found.")
            self._require_open_turn(session, tool_call.thread_id, tool_call.turn_id)

            content_blocks = input_data.content_blocks
            if content_blocks is None:
                content_blocks = [
                    {
                        "type": "tool_call_result",
                        "tool_name": tool_call.tool_name,
                        "status": input_data.status.value,
                        "result": input_data.result_payload,
                        "error_summary": input_data.error_summary,
                    }
                ]

            message = AgentMessageRow(
                thread_id=tool_call.thread_id,
                turn_id=tool_call.turn_id,
                sequence_index=self._conversations.next_message_sequence(session, tool_call.thread_id),
                kind=AgentMessageKind.TOOL_CALL_RESULT,
                ui_author=AgentMessageAuthor.TOOL,
                content_blocks=content_blocks,
                provider_payload=dict(input_data.provider_payload),
                created_at=now,
            )
            self._conversations.append_message(session, message)
            updated = self._conversations.complete_tool_call(
                session,
                tool_call.id,
                message.id,
                input_data.status,
                now,
                result_payload=input_data.result_payload,
                error_summary=input_data.error_summary,
            )
            if updated is None:
                raise NotFoundError(f"Tool call '{tool_call.id}' was not found.")
            thread = self._require_thread(session, tool_call.thread_id)
            self._touch_thread(session, thread, now)
            session.commit()
            return message, updated

    def end_turn(self, thread_id: str, turn_id: str, end_message_id: str) -> AgentTurnRow:
        now = _utc_now()
        with self._session_factory() as session:
            self._require_thread(session, thread_id)
            turn = self._require_open_turn(session, thread_id, turn_id)
            message = self._conversations.get_message(session, end_message_id)
            if message is None:
                raise NotFoundError(f"Message '{end_message_id}' was not found.")
            if message.thread_id != thread_id or message.turn_id != turn.id:
                raise ValidationError("Turn end message does not belong to the provided turn.")

            updated = self._conversations.end_turn(session, turn.id, message.id, now)
            if updated is None:
                raise NotFoundError(f"Turn '{turn.id}' was not found.")
            thread = self._require_thread(session, thread_id)
            self._touch_thread(session, thread, now)
            session.commit()
            return updated

    def start_run(self, input_data: StartAgentRunInput) -> AgentRunRow:
        now = _utc_now()
        with self._session_factory() as session:
            self._require_thread(session, input_data.thread_id)
            self._require_open_turn(session, input_data.thread_id, input_data.turn_id)
            row = AgentRunRow(
                thread_id=input_data.thread_id,
                turn_id=input_data.turn_id,
                status=AgentRunStatus.RUNNING,
                provider_name=input_data.provider_name,
                started_at=now,
            )
            self._conversations.create_run(session, row)
            session.commit()
            return row

    def finish_run(self, input_data: FinishAgentRunInput) -> AgentRunRow:
        now = _utc_now()
        with self._session_factory() as session:
            updated = self._conversations.finish_run(
                session,
                input_data.run_id,
                input_data.status,
                now,
                error_summary=input_data.error_summary,
                usage_payload=input_data.usage_payload,
            )
            if updated is None:
                raise NotFoundError(f"Agent run '{input_data.run_id}' was not found.")
            session.commit()
            return updated

    def _require_thread(self, session, thread_id: str) -> AgentThreadRow:
        thread = self._conversations.get_thread(session, thread_id)
        if thread is None:
            raise NotFoundError(f"Thread '{thread_id}' was not found.")
        return thread

    def _require_open_turn(self, session, thread_id: str, turn_id: str) -> AgentTurnRow:
        turn = self._conversations.get_turn(session, turn_id)
        if turn is None:
            raise NotFoundError(f"Turn '{turn_id}' was not found.")
        if turn.thread_id != thread_id:
            raise ValidationError("Turn does not belong to the provided thread.")
        if turn.status is not AgentTurnStatus.OPEN:
            raise ValidationError("Turn is already ended.")
        return turn

    def _touch_thread(self, session, thread: AgentThreadRow, now: datetime) -> None:
        thread.updated_at = now
        session.add(thread)
