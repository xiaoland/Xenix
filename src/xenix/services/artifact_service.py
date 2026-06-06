from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel

from ..exceptions import NotFoundError, ValidationError
from ..observability import record_counter, start_span
from .storage.models import ArtifactKind, ArtifactRow
from .storage.repositories import AgentConversationRepository, ArtifactRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RegisterArtifactInput(SQLModel):
    title: str
    absolute_path: str
    kind: ArtifactKind = ArtifactKind.OTHER
    thread_id: str | None = None
    turn_id: str | None = None
    message_id: str | None = None
    tool_call_id: str | None = None
    mime_type: str | None = None
    summary: str | None = None
    preview_payload: dict[str, Any] | None = Field(default=None)
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    ready_to_open: bool = True


class ResolvedArtifact(SQLModel):
    artifact_id: str
    title: str
    kind: ArtifactKind
    absolute_path: str
    exists: bool
    ready_to_open: bool
    mime_type: str | None = None
    summary: str | None = None
    preview_payload: dict[str, Any] | None = None
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    view: str | None = None


def build_artifact_uri(artifact_id: str, *, view: str | None = None) -> str:
    artifact_id = artifact_id.strip()
    if not artifact_id:
        raise ValidationError("Artifact id cannot be empty.")

    query = urlencode({"view": view}) if view else ""
    return urlunparse(("artifact", artifact_id, "", "", query, ""))


def build_artifact_markdown_link(row: ArtifactRow, *, label: str | None = None, view: str | None = None) -> str:
    link_label = (label or row.title).strip() or row.id
    return f"[{link_label}]({build_artifact_uri(row.id, view=view)})"


class ArtifactService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        self._artifacts = ArtifactRepository()
        self._conversations = AgentConversationRepository()

    def register_artifact(self, input_data: RegisterArtifactInput) -> ArtifactRow:
        attributes = {"artifact.kind": input_data.kind.value}
        with start_span("artifact.register", attributes):
            title = input_data.title.strip()
            if not title:
                raise ValidationError("Artifact title cannot be empty.")

            path = Path(input_data.absolute_path).expanduser()
            if not path.is_absolute():
                raise ValidationError("Artifact path must be absolute.")
            if not path.exists():
                raise ValidationError("Artifact path must exist.")

            now = _utc_now()
            row = ArtifactRow(
                thread_id=input_data.thread_id,
                turn_id=input_data.turn_id,
                message_id=input_data.message_id,
                tool_call_id=input_data.tool_call_id,
                kind=input_data.kind,
                title=title,
                absolute_path=str(path),
                mime_type=input_data.mime_type,
                summary=input_data.summary,
                preview_payload=input_data.preview_payload,
                metadata_payload=dict(input_data.metadata_payload),
                ready_to_open=input_data.ready_to_open,
                created_at=now,
            )

            with self._session_factory() as session:
                self._validate_links(session, input_data)
                self._artifacts.create(session, row)
                session.commit()
                record_counter("xenix.artifact.register.count", attributes={**attributes, "status": "succeeded"})
                return row

    def resolve_uri(self, uri: str) -> ResolvedArtifact:
        parsed = urlparse(uri)
        if parsed.scheme != "artifact":
            raise ValidationError("Artifact URI must use the artifact scheme.")

        artifact_id = parsed.netloc or parsed.path.lstrip("/").split("/", 1)[0]
        artifact_id = artifact_id.strip()
        if not artifact_id:
            raise ValidationError("Artifact URI is missing an artifact id.")
        view = parse_qs(parsed.query).get("view", [None])[0]

        with self._session_factory() as session:
            row = self._artifacts.get(session, artifact_id)
            if row is None:
                raise NotFoundError(f"Artifact '{artifact_id}' was not found.")
            path = Path(row.absolute_path)
            return ResolvedArtifact(
                artifact_id=row.id,
                title=row.title,
                kind=row.kind,
                absolute_path=row.absolute_path,
                exists=path.exists(),
                ready_to_open=row.ready_to_open,
                mime_type=row.mime_type,
                summary=row.summary,
                preview_payload=row.preview_payload,
                metadata_payload=dict(row.metadata_payload),
                view=view,
            )

    def list_thread_artifacts(self, thread_id: str) -> list[ArtifactRow]:
        with self._session_factory() as session:
            if self._conversations.get_thread(session, thread_id) is None:
                raise NotFoundError(f"Thread '{thread_id}' was not found.")
            return self._artifacts.list_by_thread(session, thread_id)

    def _validate_links(self, session, input_data: RegisterArtifactInput) -> None:
        if input_data.thread_id is not None and self._conversations.get_thread(session, input_data.thread_id) is None:
            raise NotFoundError(f"Thread '{input_data.thread_id}' was not found.")

        if input_data.turn_id is not None:
            turn = self._conversations.get_turn(session, input_data.turn_id)
            if turn is None:
                raise NotFoundError(f"Turn '{input_data.turn_id}' was not found.")
            if input_data.thread_id is not None and turn.thread_id != input_data.thread_id:
                raise ValidationError("Artifact turn does not belong to the provided thread.")

        if input_data.message_id is not None:
            message = self._conversations.get_message(session, input_data.message_id)
            if message is None:
                raise NotFoundError(f"Message '{input_data.message_id}' was not found.")
            if input_data.thread_id is not None and message.thread_id != input_data.thread_id:
                raise ValidationError("Artifact message does not belong to the provided thread.")
            if input_data.turn_id is not None and message.turn_id != input_data.turn_id:
                raise ValidationError("Artifact message does not belong to the provided turn.")

        if input_data.tool_call_id is not None:
            tool_call = self._conversations.get_tool_call(session, input_data.tool_call_id)
            if tool_call is None:
                raise NotFoundError(f"Tool call '{input_data.tool_call_id}' was not found.")
            if input_data.thread_id is not None and tool_call.thread_id != input_data.thread_id:
                raise ValidationError("Artifact tool call does not belong to the provided thread.")
            if input_data.turn_id is not None and tool_call.turn_id != input_data.turn_id:
                raise ValidationError("Artifact tool call does not belong to the provided turn.")
