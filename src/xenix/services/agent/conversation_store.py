from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel

from ...exceptions import NotFoundError, ValidationError
from ..storage.models import (
    AgentMessageAuthor,
    AgentMessageKind,
    AgentMessageRow,
    AgentMessageStatus,
    AgentProviderRequestKind,
    AgentProviderRequestRow,
    AgentProviderRequestStatus,
    AgentRunRow,
    AgentRunStatus,
    AgentThreadRow,
    AgentToolCallRow,
    AgentToolCallStatus,
    AgentTurnCompletionGuardRow,
    AgentTurnRow,
    AgentTurnStatus,
    ArtifactRow,
    default_agent_thread_system_prompt,
)
from ..storage.repositories import AgentConversationRepository, ArtifactRepository
from .providers import ProviderMessage, extract_reasoning_content


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CreateAgentThreadInput(SQLModel):
    title: str | None = None
    system_prompt: str | None = None
    interface_locale: str | None = None
    selected_fq_model_key: str | None = None


class RenameAgentThreadInput(SQLModel):
    thread_id: str
    title: str | None = None


class UpdateAgentThreadModelInput(SQLModel):
    thread_id: str
    selected_fq_model_key: str | None = None


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
    status: AgentMessageStatus = AgentMessageStatus.COMPLETED


class UpdateAgentMessageInput(SQLModel):
    message_id: str
    content_blocks: list[dict[str, Any]] | None = None
    provider_payload: dict[str, Any] | None = None
    status: AgentMessageStatus | None = None


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
    usage_payload: dict[str, Any] | None = None


class FinishAgentRunInput(SQLModel):
    run_id: str
    status: AgentRunStatus
    error_summary: str | None = None
    usage_payload: dict[str, Any] | None = None


class CreateProviderRequestInput(SQLModel):
    thread_id: str
    turn_id: str
    run_id: str | None = None
    provider_name: str | None = None
    model: str | None = None
    request_kind: AgentProviderRequestKind = AgentProviderRequestKind.PRIMARY
    input_message_ids: list[str] = Field(default_factory=list)


class CompleteProviderRequestInput(SQLModel):
    provider_request_id: str
    status: AgentProviderRequestStatus
    output_message_ids: list[str] = Field(default_factory=list)
    usage_payload: dict[str, Any] | None = None


class CreateTurnCompletionGuardInput(SQLModel):
    turn_id: str
    attempt_index: int
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)


class ThreadSnapshot(SQLModel):
    thread: AgentThreadRow
    turns: list[AgentTurnRow] = Field(default_factory=list)
    messages: list[AgentMessageRow] = Field(default_factory=list)
    tool_calls: list[AgentToolCallRow] = Field(default_factory=list)
    provider_requests: list[AgentProviderRequestRow] = Field(default_factory=list)
    artifacts: list[ArtifactRow] = Field(default_factory=list)

    def provider_messages(self) -> list[ProviderMessage]:
        rows: list[ProviderMessage] = []
        tool_calls_by_request_message_id = {
            tool_call.request_message_id: tool_call
            for tool_call in self.tool_calls
        }
        tool_calls_by_result_message_id = {
            tool_call.result_message_id: tool_call
            for tool_call in self.tool_calls
            if tool_call.result_message_id is not None
        }
        index = 0
        while index < len(self.messages):
            message = self.messages[index]
            if message.kind is AgentMessageKind.ASSISTANT:
                content = _content_blocks_to_text(message.content_blocks)
                payload = _assistant_provider_payload(message)
                next_index, grouped_tool_calls = _collect_following_tool_calls(
                    self.messages,
                    index + 1,
                    tool_calls_by_request_message_id,
                )
                if grouped_tool_calls:
                    payload["tool_calls"] = [
                        _provider_tool_call_item(tool_call, tool_message)
                        for tool_call, tool_message in grouped_tool_calls
                    ]
                    index = next_index
                else:
                    index += 1
                rows.append(
                    ProviderMessage(
                        role="assistant",
                        content=content,
                        content_blocks=list(message.content_blocks),
                        provider_payload=payload,
                        source_message_id=message.id,
                    )
                )
                continue
            if message.kind is AgentMessageKind.TOOL_CALL:
                next_index, grouped_tool_calls = _collect_following_tool_calls(
                    self.messages,
                    index,
                    tool_calls_by_request_message_id,
                )
                if not grouped_tool_calls:
                    index += 1
                    continue
                payload = _tool_calls_provider_payload(grouped_tool_calls)
                rows.append(
                    ProviderMessage(
                        role="assistant",
                        content="",
                        content_blocks=list(message.content_blocks),
                        provider_payload=payload,
                        source_message_id=message.id,
                    )
                )
                index = next_index
                continue
            role = _provider_role_for_message(message)
            if role is None:
                index += 1
                continue
            content = _content_blocks_to_text(message.content_blocks)
            if message.kind is AgentMessageKind.TOOL_CALL_RESULT:
                tool_call = tool_calls_by_result_message_id.get(message.id)
                if tool_call is not None:
                    content = _tool_result_to_text(tool_call)
            rows.append(
                ProviderMessage(
                    role=role,
                    content=content,
                    content_blocks=list(message.content_blocks),
                    provider_payload=dict(message.provider_payload),
                    source_message_id=message.id,
                )
            )
            index += 1
        return rows


class ConversationStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        self._conversations = AgentConversationRepository()
        self._artifacts = ArtifactRepository()

    def create_thread(self, input_data: CreateAgentThreadInput | None = None) -> AgentThreadRow:
        input_data = input_data or CreateAgentThreadInput()
        title = input_data.title.strip() if input_data.title else None
        system_prompt = (
            input_data.system_prompt.strip() if input_data.system_prompt else ""
        ) or default_agent_thread_system_prompt(input_data.interface_locale)
        selected_fq_model_key = (
            input_data.selected_fq_model_key.strip()
            if input_data.selected_fq_model_key
            else None
        )
        now = _utc_now()
        row = AgentThreadRow(
            title=title,
            system_prompt=system_prompt,
            selected_fq_model_key=selected_fq_model_key,
            created_at=now,
            updated_at=now,
        )
        with self._session_factory() as session:
            self._conversations.create_thread(session, row)
            session.commit()
            return row

    def list_threads(self) -> list[AgentThreadRow]:
        with self._session_factory() as session:
            return self._conversations.list_threads(session)

    def rename_thread(self, input_data: RenameAgentThreadInput) -> AgentThreadRow:
        title = input_data.title.strip() if input_data.title else None
        now = _utc_now()
        with self._session_factory() as session:
            row = self._conversations.rename_thread(session, input_data.thread_id, title, now)
            if row is None:
                raise NotFoundError(f"Thread '{input_data.thread_id}' was not found.")
            session.commit()
            return row

    def update_thread_model(self, input_data: UpdateAgentThreadModelInput) -> AgentThreadRow:
        selected_fq_model_key = (
            input_data.selected_fq_model_key.strip()
            if input_data.selected_fq_model_key
            else None
        )
        now = _utc_now()
        with self._session_factory() as session:
            thread = self._conversations.get_thread(session, input_data.thread_id)
            if thread is None:
                raise NotFoundError(f"Thread '{input_data.thread_id}' was not found.")
            thread.selected_fq_model_key = selected_fq_model_key
            thread.updated_at = now
            session.add(thread)
            session.commit()
            session.refresh(thread)
            return thread

    def delete_thread(self, thread_id: str) -> AgentThreadRow:
        with self._session_factory() as session:
            row = self._conversations.delete_thread(session, thread_id)
            if row is None:
                raise NotFoundError(f"Thread '{thread_id}' was not found.")
            session.commit()
            return row

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
                provider_requests=self._conversations.list_provider_requests(session, thread_id),
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
            if self._thread_system_message(session, thread.id) is None:
                system_message = AgentMessageRow(
                    thread_id=thread.id,
                    turn_id=turn.id,
                    sequence_index=self._conversations.next_message_sequence(session, thread.id),
                    kind=AgentMessageKind.SYSTEM,
                    ui_author=AgentMessageAuthor.SYSTEM,
                    content_blocks=[{"type": "text", "text": thread.system_prompt}],
                    status=AgentMessageStatus.COMPLETED,
                    created_at=now,
                    updated_at=now,
                    finalized_at=now,
                )
                self._conversations.append_message(session, system_message)
            message = AgentMessageRow(
                thread_id=thread.id,
                turn_id=turn.id,
                sequence_index=self._conversations.next_message_sequence(session, thread.id),
                kind=AgentMessageKind.USER,
                ui_author=AgentMessageAuthor.USER,
                content_blocks=list(input_data.user_content_blocks),
                provider_payload=dict(input_data.provider_payload),
                status=AgentMessageStatus.COMPLETED,
                created_at=now,
                updated_at=now,
                finalized_at=now,
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
                status=input_data.status,
                created_at=now,
                updated_at=now,
                finalized_at=_finalized_at_for_status(input_data.status, now),
            )
            self._conversations.append_message(session, message)
            self._touch_thread(session, thread, now)
            session.commit()
            return message

    def update_message(self, input_data: UpdateAgentMessageInput) -> AgentMessageRow:
        now = _utc_now()
        with self._session_factory() as session:
            message = self._conversations.get_message(session, input_data.message_id)
            if message is None:
                raise NotFoundError(f"Message '{input_data.message_id}' was not found.")
            if message.turn_id is not None:
                self._require_open_turn(session, message.thread_id, message.turn_id)
            thread = self._require_thread(session, message.thread_id)
            updated = self._conversations.update_message(
                session,
                message.id,
                now,
                content_blocks=list(input_data.content_blocks) if input_data.content_blocks is not None else None,
                provider_payload=dict(input_data.provider_payload) if input_data.provider_payload is not None else None,
                status=input_data.status,
                finalized_at=_finalized_at_for_status(input_data.status, now),
            )
            if updated is None:
                raise NotFoundError(f"Message '{message.id}' was not found.")
            self._touch_thread(session, thread, now)
            session.commit()
            return updated

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
                status=AgentMessageStatus.COMPLETED,
                created_at=now,
                updated_at=now,
                finalized_at=now,
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

            message = AgentMessageRow(
                thread_id=tool_call.thread_id,
                turn_id=tool_call.turn_id,
                sequence_index=self._conversations.next_message_sequence(session, tool_call.thread_id),
                kind=AgentMessageKind.TOOL_CALL_RESULT,
                ui_author=AgentMessageAuthor.TOOL,
                content_blocks=[],
                provider_payload=dict(input_data.provider_payload),
                status=AgentMessageStatus.COMPLETED,
                created_at=now,
                updated_at=now,
                finalized_at=now,
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

    def end_turn(self, thread_id: str, turn_id: str) -> AgentTurnRow:
        now = _utc_now()
        with self._session_factory() as session:
            self._require_thread(session, thread_id)
            turn = self._require_open_turn(session, thread_id, turn_id)
            updated = self._conversations.end_turn(session, turn.id, now)
            if updated is None:
                raise NotFoundError(f"Turn '{turn.id}' was not found.")
            thread = self._require_thread(session, thread_id)
            self._touch_thread(session, thread, now)
            session.commit()
            return updated

    def cancel_turn(self, thread_id: str, turn_id: str) -> AgentTurnRow:
        now = _utc_now()
        with self._session_factory() as session:
            self._require_thread(session, thread_id)
            turn = self._require_open_turn(session, thread_id, turn_id)
            updated = self._conversations.cancel_turn(session, turn.id, now)
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
                usage_payload=input_data.usage_payload,
            )
            self._conversations.create_run(session, row)
            session.commit()
            return row

    def get_run(self, run_id: str) -> AgentRunRow:
        with self._session_factory() as session:
            row = self._conversations.get_run(session, run_id)
            if row is None:
                raise NotFoundError(f"Agent run '{run_id}' was not found.")
            return row

    def pause_run_for_confirmation(self, run_id: str, usage_payload: dict[str, Any]) -> AgentRunRow:
        with self._session_factory() as session:
            row = self._conversations.update_run_status(
                session,
                run_id,
                AgentRunStatus.AWAITING_CONFIRMATION,
                usage_payload=usage_payload,
            )
            if row is None:
                raise NotFoundError(f"Agent run '{run_id}' was not found.")
            session.commit()
            return row

    def resume_run_after_confirmation(self, run_id: str, usage_payload: dict[str, Any]) -> AgentRunRow:
        with self._session_factory() as session:
            row = self._conversations.update_run_status(
                session,
                run_id,
                AgentRunStatus.RUNNING,
                usage_payload=usage_payload,
            )
            if row is None:
                raise NotFoundError(f"Agent run '{run_id}' was not found.")
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

    def create_provider_request(self, input_data: CreateProviderRequestInput) -> AgentProviderRequestRow:
        now = _utc_now()
        with self._session_factory() as session:
            thread = self._require_thread(session, input_data.thread_id)
            self._require_open_turn(session, thread.id, input_data.turn_id)
            row = AgentProviderRequestRow(
                thread_id=thread.id,
                turn_id=input_data.turn_id,
                run_id=input_data.run_id,
                provider_name=input_data.provider_name,
                model=input_data.model,
                request_kind=input_data.request_kind,
                status=AgentProviderRequestStatus.RUNNING,
                input_message_ids=list(input_data.input_message_ids),
                output_message_ids=[],
                created_at=now,
            )
            self._conversations.create_provider_request(session, row)
            session.commit()
            return row

    def complete_provider_request(self, input_data: CompleteProviderRequestInput) -> AgentProviderRequestRow:
        now = _utc_now()
        with self._session_factory() as session:
            row = self._conversations.get_provider_request(session, input_data.provider_request_id)
            if row is None:
                raise NotFoundError(f"Provider request '{input_data.provider_request_id}' was not found.")
            updated = self._conversations.complete_provider_request(
                session,
                row.id,
                input_data.status,
                now,
                output_message_ids=list(input_data.output_message_ids),
                usage_payload=dict(input_data.usage_payload) if input_data.usage_payload is not None else None,
            )
            if updated is None:
                raise NotFoundError(f"Provider request '{row.id}' was not found.")
            session.commit()
            return updated

    def list_provider_requests_by_turn(self, turn_id: str) -> list[AgentProviderRequestRow]:
        with self._session_factory() as session:
            return self._conversations.list_provider_requests_by_turn(session, turn_id)

    def create_turn_completion_guard(
        self,
        input_data: CreateTurnCompletionGuardInput,
    ) -> AgentTurnCompletionGuardRow:
        now = _utc_now()
        with self._session_factory() as session:
            turn = self._conversations.get_turn(session, input_data.turn_id)
            if turn is None:
                raise NotFoundError(f"Turn '{input_data.turn_id}' was not found.")
            row = AgentTurnCompletionGuardRow(
                turn_id=turn.id,
                attempt_index=input_data.attempt_index,
                input=dict(input_data.input),
                output=dict(input_data.output),
                created_at=now,
            )
            self._conversations.create_turn_completion_guard(session, row)
            session.commit()
            return row

    def list_turn_completion_guards(self, turn_id: str) -> list[AgentTurnCompletionGuardRow]:
        with self._session_factory() as session:
            return self._conversations.list_turn_completion_guards(session, turn_id)

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

    def _thread_system_message(self, session, thread_id: str) -> AgentMessageRow | None:
        for message in self._conversations.list_messages(session, thread_id):
            if message.kind is AgentMessageKind.SYSTEM:
                return message
        return None


def _provider_role_for_message(message: AgentMessageRow) -> str | None:
    if message.kind is AgentMessageKind.SYSTEM:
        return "system"
    if message.kind is AgentMessageKind.USER:
        return "user"
    if message.kind is AgentMessageKind.ASSISTANT:
        return "assistant"
    if message.kind is AgentMessageKind.TOOL_CALL_RESULT:
        return "tool"
    return None


def _content_blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type in {"text", "markdown"}:
            lines.append(str(block.get("text", "")))
        elif block_type == "file":
            lines.append("Legacy local file attachment omitted; reattach it as a dataset to use it.")
        elif block_type == "dataset":
            lines.append(_dataset_block_to_text(block))
        elif block_type == "step_confirmation":
            lines.append(str(block.get("text", "")))
        elif block_type == "tool_event_summary":
            lines.append(str(block.get("text", "")))
        else:
            lines.append(json.dumps(block, ensure_ascii=False))
    return "\n".join(line for line in lines if line)


def _dataset_block_to_text(block: dict[str, Any]) -> str:
    dataset_id = str(block.get("dataset_id") or "").strip()
    name = str(block.get("name") or "").strip()
    file_name = str(block.get("file_name") or "").strip()
    row_count = block.get("row_count")
    column_count = block.get("column_count")
    preview_columns = block.get("preview_columns")
    parts = ["Attached dataset"]
    if name:
        parts.append(name)
    if dataset_id:
        parts.append(f"dataset_id: {dataset_id}")
    if file_name:
        parts.append(f"file: {file_name}")
    if isinstance(row_count, int) and isinstance(column_count, int):
        parts.append(f"rows: {row_count}")
        parts.append(f"columns: {column_count}")
    if isinstance(preview_columns, list) and preview_columns:
        column_names = ", ".join(str(column) for column in preview_columns[:20])
        parts.append(f"column names: {column_names}")
    return parts[0] + " (" + "; ".join(parts[1:]) + ")" if len(parts) > 1 else parts[0]


def _tool_result_to_text(tool_call: AgentToolCallRow) -> str:
    payload = {
        "tool_name": tool_call.tool_name,
        "status": tool_call.status.value,
        "result": dict(tool_call.result_payload or {}),
    }
    if tool_call.error_summary:
        payload["error_summary"] = tool_call.error_summary
    return json.dumps(payload, ensure_ascii=False)


def _assistant_provider_payload(message: AgentMessageRow) -> dict[str, Any]:
    payload = dict(message.provider_payload)
    reasoning_content = extract_reasoning_content(payload)
    if reasoning_content is not None:
        payload["reasoning_content"] = reasoning_content
    return payload


def _collect_following_tool_calls(
    messages: list[AgentMessageRow],
    start_index: int,
    tool_calls_by_request_message_id: dict[str, AgentToolCallRow],
) -> tuple[int, list[tuple[AgentToolCallRow, AgentMessageRow]]]:
    index = start_index
    tool_calls: list[tuple[AgentToolCallRow, AgentMessageRow]] = []
    while index < len(messages):
        message = messages[index]
        if message.kind is not AgentMessageKind.TOOL_CALL:
            break
        tool_call = tool_calls_by_request_message_id.get(message.id)
        if tool_call is not None:
            tool_calls.append((tool_call, message))
        index += 1
    return index, tool_calls


def _tool_calls_provider_payload(
    tool_calls: list[tuple[AgentToolCallRow, AgentMessageRow]],
) -> dict[str, Any]:
    first_payload = dict(tool_calls[0][1].provider_payload)
    reasoning_content = first_payload.get("reasoning_content")
    payload: dict[str, Any] = {}
    if isinstance(reasoning_content, str):
        payload["reasoning_content"] = reasoning_content
    payload["tool_calls"] = [
        _provider_tool_call_item(tool_call, message)
        for tool_call, message in tool_calls
    ]
    return payload


def _provider_tool_call_item(
    tool_call: AgentToolCallRow,
    message: AgentMessageRow,
) -> dict[str, Any]:
    payload = dict(message.provider_payload)
    provider_call_id = str(payload.get("tool_call_id") or tool_call.id)
    provider_name = str(
        payload.get("provider_name")
        or payload.get("tool_name")
        or tool_call.tool_name.replace(".", "_")
    )
    return {
        "id": provider_call_id,
        "type": "function",
        "function": {
            "name": provider_name,
            "arguments": json.dumps(dict(tool_call.arguments_payload or {}), ensure_ascii=False),
        },
    }


def _finalized_at_for_status(status: AgentMessageStatus | None, now: datetime) -> datetime | None:
    if status in {
        AgentMessageStatus.COMPLETED,
        AgentMessageStatus.FAILED,
        AgentMessageStatus.CANCELLED,
    }:
        return now
    return None
