from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, col, select

from ..models import (
    AgentMessageRow,
    AgentMessageStatus,
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
)


class AgentConversationRepository:
    def create_thread(self, session: Session, row: AgentThreadRow) -> AgentThreadRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_thread(self, session: Session, thread_id: str) -> AgentThreadRow | None:
        return session.get(AgentThreadRow, thread_id)

    def list_threads(self, session: Session) -> list[AgentThreadRow]:
        statement = select(AgentThreadRow).order_by(AgentThreadRow.updated_at.desc())
        return list(session.exec(statement))

    def rename_thread(
        self,
        session: Session,
        thread_id: str,
        title: str | None,
        now: datetime,
    ) -> AgentThreadRow | None:
        row = self.get_thread(session, thread_id)
        if row is None:
            return None

        row.title = title
        row.updated_at = now
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def delete_thread(self, session: Session, thread_id: str) -> AgentThreadRow | None:
        row = self.get_thread(session, thread_id)
        if row is None:
            return None

        artifacts = session.exec(select(ArtifactRow).where(ArtifactRow.thread_id == thread_id)).all()
        for artifact in artifacts:
            session.delete(artifact)
        session.flush()

        turns = session.exec(select(AgentTurnRow).where(AgentTurnRow.thread_id == thread_id)).all()
        for turn in turns:
            turn.user_message_id = None
            session.add(turn)
        session.flush()

        provider_requests = session.exec(
            select(AgentProviderRequestRow).where(AgentProviderRequestRow.thread_id == thread_id)
        ).all()
        for provider_request in provider_requests:
            session.delete(provider_request)
        session.flush()

        tool_calls = session.exec(select(AgentToolCallRow).where(AgentToolCallRow.thread_id == thread_id)).all()
        for tool_call in tool_calls:
            session.delete(tool_call)
        session.flush()

        runs = session.exec(select(AgentRunRow).where(AgentRunRow.thread_id == thread_id)).all()
        for run in runs:
            session.delete(run)
        session.flush()

        turn_ids = [turn.id for turn in turns]
        if turn_ids:
            guard_rows = session.exec(
                select(AgentTurnCompletionGuardRow).where(
                    col(AgentTurnCompletionGuardRow.turn_id).in_(turn_ids)
                )
            ).all()
            for guard_row in guard_rows:
                session.delete(guard_row)
            session.flush()

        messages = session.exec(select(AgentMessageRow).where(AgentMessageRow.thread_id == thread_id)).all()
        for message in messages:
            session.delete(message)
        session.flush()

        for turn in turns:
            session.delete(turn)
        session.flush()

        session.delete(row)
        session.flush()
        return row

    def next_turn_sequence(self, session: Session, thread_id: str) -> int:
        statement = select(func.max(col(AgentTurnRow.sequence_index))).where(AgentTurnRow.thread_id == thread_id)
        current = session.exec(statement).one()
        return 0 if current is None else int(current) + 1

    def create_turn(self, session: Session, row: AgentTurnRow) -> AgentTurnRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_turn(self, session: Session, turn_id: str) -> AgentTurnRow | None:
        return session.get(AgentTurnRow, turn_id)

    def list_turns(self, session: Session, thread_id: str) -> list[AgentTurnRow]:
        statement = (
            select(AgentTurnRow)
            .where(AgentTurnRow.thread_id == thread_id)
            .order_by(AgentTurnRow.sequence_index)
        )
        return list(session.exec(statement))

    def set_turn_user_message(
        self,
        session: Session,
        turn_id: str,
        user_message_id: str,
        now: datetime,
    ) -> AgentTurnRow | None:
        row = self.get_turn(session, turn_id)
        if row is None:
            return None

        row.user_message_id = user_message_id
        row.updated_at = now
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def end_turn(
        self,
        session: Session,
        turn_id: str,
        now: datetime,
    ) -> AgentTurnRow | None:
        row = self.get_turn(session, turn_id)
        if row is None:
            return None

        row.status = AgentTurnStatus.ENDED
        row.ended_at = now
        row.updated_at = now
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def cancel_turn(self, session: Session, turn_id: str, now: datetime) -> AgentTurnRow | None:
        row = self.get_turn(session, turn_id)
        if row is None:
            return None

        row.status = AgentTurnStatus.CANCELLED
        row.ended_at = now
        row.updated_at = now
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def next_message_sequence(self, session: Session, thread_id: str) -> int:
        statement = select(func.max(col(AgentMessageRow.sequence_index))).where(AgentMessageRow.thread_id == thread_id)
        current = session.exec(statement).one()
        return 0 if current is None else int(current) + 1

    def append_message(self, session: Session, row: AgentMessageRow) -> AgentMessageRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_message(self, session: Session, message_id: str) -> AgentMessageRow | None:
        return session.get(AgentMessageRow, message_id)

    def list_messages(self, session: Session, thread_id: str) -> list[AgentMessageRow]:
        statement = (
            select(AgentMessageRow)
            .where(AgentMessageRow.thread_id == thread_id)
            .order_by(AgentMessageRow.sequence_index)
        )
        return list(session.exec(statement))

    def update_message(
        self,
        session: Session,
        message_id: str,
        now: datetime,
        *,
        content_blocks: list[dict] | None = None,
        provider_payload: dict | None = None,
        status: AgentMessageStatus | None = None,
        finalized_at: datetime | None = None,
    ) -> AgentMessageRow | None:
        row = self.get_message(session, message_id)
        if row is None:
            return None

        if content_blocks is not None:
            row.content_blocks = content_blocks
        if provider_payload is not None:
            row.provider_payload = provider_payload
        if status is not None:
            row.status = status
        row.updated_at = now
        if finalized_at is not None:
            row.finalized_at = finalized_at
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def create_run(self, session: Session, row: AgentRunRow) -> AgentRunRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_run(self, session: Session, run_id: str) -> AgentRunRow | None:
        return session.get(AgentRunRow, run_id)

    def update_run_status(
        self,
        session: Session,
        run_id: str,
        status: AgentRunStatus,
        *,
        usage_payload: dict | None = None,
        error_summary: str | None = None,
    ) -> AgentRunRow | None:
        row = self.get_run(session, run_id)
        if row is None:
            return None

        row.status = status
        row.usage_payload = usage_payload
        row.error_summary = error_summary
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def finish_run(
        self,
        session: Session,
        run_id: str,
        status: AgentRunStatus,
        finished_at: datetime,
        *,
        error_summary: str | None = None,
        usage_payload: dict | None = None,
    ) -> AgentRunRow | None:
        row = session.get(AgentRunRow, run_id)
        if row is None:
            return None

        row.status = status
        row.finished_at = finished_at
        row.error_summary = error_summary
        row.usage_payload = usage_payload
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def create_tool_call(self, session: Session, row: AgentToolCallRow) -> AgentToolCallRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_tool_call(self, session: Session, tool_call_id: str) -> AgentToolCallRow | None:
        return session.get(AgentToolCallRow, tool_call_id)

    def list_tool_calls(self, session: Session, turn_id: str) -> list[AgentToolCallRow]:
        statement = (
            select(AgentToolCallRow)
            .where(AgentToolCallRow.turn_id == turn_id)
            .order_by(AgentToolCallRow.created_at)
        )
        return list(session.exec(statement))

    def complete_tool_call(
        self,
        session: Session,
        tool_call_id: str,
        result_message_id: str,
        status: AgentToolCallStatus,
        now: datetime,
        *,
        result_payload: dict | None = None,
        error_summary: str | None = None,
    ) -> AgentToolCallRow | None:
        row = self.get_tool_call(session, tool_call_id)
        if row is None:
            return None

        row.result_message_id = result_message_id
        row.status = status
        row.result_payload = result_payload
        row.error_summary = error_summary
        row.updated_at = now
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def create_provider_request(self, session: Session, row: AgentProviderRequestRow) -> AgentProviderRequestRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_provider_request(self, session: Session, provider_request_id: str) -> AgentProviderRequestRow | None:
        return session.get(AgentProviderRequestRow, provider_request_id)

    def list_provider_requests(self, session: Session, thread_id: str) -> list[AgentProviderRequestRow]:
        statement = (
            select(AgentProviderRequestRow)
            .where(AgentProviderRequestRow.thread_id == thread_id)
            .order_by(AgentProviderRequestRow.created_at)
        )
        return list(session.exec(statement))

    def list_provider_requests_by_turn(self, session: Session, turn_id: str) -> list[AgentProviderRequestRow]:
        statement = (
            select(AgentProviderRequestRow)
            .where(AgentProviderRequestRow.turn_id == turn_id)
            .order_by(AgentProviderRequestRow.created_at)
        )
        return list(session.exec(statement))

    def complete_provider_request(
        self,
        session: Session,
        provider_request_id: str,
        status: AgentProviderRequestStatus,
        completed_at: datetime,
        *,
        output_message_ids: list[str] | None = None,
        usage_payload: dict | None = None,
    ) -> AgentProviderRequestRow | None:
        row = self.get_provider_request(session, provider_request_id)
        if row is None:
            return None

        row.status = status
        if output_message_ids is not None:
            row.output_message_ids = output_message_ids
        row.usage_payload = usage_payload
        row.completed_at = completed_at
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def create_turn_completion_guard(
        self,
        session: Session,
        row: AgentTurnCompletionGuardRow,
    ) -> AgentTurnCompletionGuardRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def list_turn_completion_guards(
        self,
        session: Session,
        turn_id: str,
    ) -> list[AgentTurnCompletionGuardRow]:
        statement = (
            select(AgentTurnCompletionGuardRow)
            .where(AgentTurnCompletionGuardRow.turn_id == turn_id)
            .order_by(AgentTurnCompletionGuardRow.attempt_index)
        )
        return list(session.exec(statement))
