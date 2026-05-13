from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, col, select

from ..models import (
    AgentMessageRow,
    AgentRunRow,
    AgentRunStatus,
    AgentThreadRow,
    AgentToolCallRow,
    AgentToolCallStatus,
    AgentTurnRow,
    AgentTurnStatus,
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
        end_message_id: str,
        now: datetime,
    ) -> AgentTurnRow | None:
        row = self.get_turn(session, turn_id)
        if row is None:
            return None

        row.status = AgentTurnStatus.ENDED
        row.end_message_id = end_message_id
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

    def create_run(self, session: Session, row: AgentRunRow) -> AgentRunRow:
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
