"""Thread title generation concern for the LLM conversation boundary.

The title methods are grouped in a mixin so ``LLMConversationService`` stays
focused on canonical conversation writes.  The mixin accesses the service's
own collaborators through ``self``; it never owns storage or locking.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ...exceptions import NotFoundError, ValidationError
from ..storage.models import ConversationMessageKind, ConversationMessageRow
from .conversation_models import (
    ConversationSnapshot,
    SubmissionClaim,
    ThreadPausedError,
    _utc_now,
)
from .messages import (
    AssistantOutputItem,
    DatasetBlock,
    MarkdownBlock,
    SourceAttachmentBlock,
    TextBlock,
    blocks_from_payload,
    blocks_to_markdown,
)
from .providers import ProviderMessage, ProviderResponse
from .service import LLMService

# Preserve the service's logger name so title warnings keep their origin.
LOGGER = logging.getLogger("xenix.services.llm.conversation")

THREAD_TITLE_MAX_LENGTH = 80
THREAD_TITLE_SYSTEM_PROMPT = (
    "You generate concise conversation titles for Xenix threads. "
    "Return exactly one title only. Use the user's language when it is clear. "
    "Do not include quotes, markdown, labels, or trailing punctuation."
)


class TitleGenerationMixin:
    """Title proposal and initial-title persistence for a conversation service."""

    def has_thread_title_model(self) -> bool:
        return self._thread_title_fq_model_key() is not None

    def generate_thread_title(self, thread_id: str) -> str:
        """Return a manual title proposal without changing the Thread."""

        if not self.has_thread_title_model():
            raise ValidationError("Thread title model is not configured.")
        title = self._model_thread_title(
            self._thread_title_snapshot_prompt(self.get_thread_snapshot(thread_id)),
            thread_id=thread_id,
        )
        if title is None:
            raise ValidationError("Thread title model returned an empty title.")
        return title

    def auto_title_initial_thread(
        self,
        *,
        claim: SubmissionClaim,
        first_user_message_id: str,
        appended_snapshot: ConversationSnapshot | None = None,
    ) -> ConversationSnapshot | None:
        """Persist metadata for a just-appended first UserMessage when eligible.

        The claim captures the pre-append eligibility from canonical state; the
        caller supplies the first Message identity from the append result.  A
        Harness may retain that append snapshot while primary sampling begins;
        using it as the preflight witness avoids a fast Assistant completion
        changing the definition of the already-eligible initial exchange.
        Provider I/O remains outside the write gate, so a manual rename never
        waits on the title model and always wins the conditional write.
        """

        thread_id = claim.thread_id
        if not claim.initial_title_eligible:
            return self.get_thread_snapshot(thread_id)
        if appended_snapshot is not None:
            if appended_snapshot.thread.id != thread_id:
                raise ValidationError("The supplied append snapshot belongs to a different Thread.")
            snapshot = appended_snapshot
            if not self._is_initial_title_target(snapshot, first_user_message_id):
                return self.get_thread_snapshot(thread_id)
        else:
            with self._gate(thread_id):
                snapshot = self.get_thread_snapshot(thread_id)
                if not self._is_initial_title_target(snapshot, first_user_message_id):
                    return snapshot

        try:
            title = self._automatic_initial_thread_title(snapshot)
        except ThreadPausedError:
            return None
        with self._pending_lock:
            with self._gate(thread_id):
                if self._thread_control_locked(thread_id).paused:
                    return None
                with self._session_factory() as session:
                    row = self._repository.set_initial_title_if_blank(
                        session,
                        thread_id=thread_id,
                        title=title,
                        now=_utc_now(),
                    )
                    if row is None:
                        raise NotFoundError(f"Conversation Thread '{thread_id}' was not found.")
                    messages = self._repository.list_messages(session, thread_id)
                    session.commit()
                    return ConversationSnapshot(thread=row, messages=messages)

    def is_initial_title_eligible(self, snapshot: ConversationSnapshot) -> bool:
        """Whether an append may establish this Thread's initial title."""

        final_messages = [
            message
            for message in snapshot.messages
            if message.kind is not ConversationMessageKind.PENDING_LLM_SAMPLING
        ]
        return _is_blank_thread_title(snapshot.thread.title) and not final_messages

    def _automatic_initial_thread_title(self, snapshot: ConversationSnapshot) -> str:
        fallback = self._fallback_initial_thread_title(snapshot)
        if not self.has_thread_title_model():
            return fallback
        try:
            title = self._model_thread_title(
                self._initial_thread_title_prompt(snapshot),
                thread_id=snapshot.thread.id,
            )
            if title is None:
                raise ValidationError("Thread title model returned an empty title.")
            return title
        except ThreadPausedError:
            raise
        except Exception as exc:
            LOGGER.warning("Initial Thread title model failed; using deterministic fallback: %s", exc)
            return fallback

    def _model_thread_title(self, prompt: str, *, thread_id: str) -> str | None:
        response = self._complete_thread_title(
            [
                ProviderMessage(role="system", content=THREAD_TITLE_SYSTEM_PROMPT),
                ProviderMessage(role="user", content=prompt),
            ],
            thread_id=thread_id,
        )
        return _sanitize_thread_title(_assistant_response_text(response))

    def _complete_thread_title(
        self,
        messages: list[ProviderMessage],
        *,
        thread_id: str,
    ) -> ProviderResponse:
        fq_model_key = self._thread_title_fq_model_key()
        if fq_model_key is None:
            raise ValidationError("Thread title model is not configured.")
        gateway = self._require_llm_service()
        if isinstance(gateway, LLMService):
            response = gateway.complete(
                fq_model_key=fq_model_key,
                messages=messages,
                tools=[],
                before_provider_request=lambda: self._admit_auxiliary_provider_request(thread_id),
            )
        else:
            # Tests and third-party in-process gateways predating the
            # per-attempt admission hook retain their narrow ``complete``
            # signature.  They still receive one admission before I/O; the
            # production LLMService performs it before every retry attempt.
            self._admit_auxiliary_provider_request(thread_id)
            response = gateway.complete(
                fq_model_key=fq_model_key,
                messages=messages,
                tools=[],
            )
        self._record_auxiliary_usage(
            operation="thread_title",
            thread_id=thread_id,
            usage_payload=response.usage_payload,
            fq_model_key=fq_model_key,
        )
        # Usage records the completed provider request even when a Thread
        # pause won while it was in flight.  Its response, however, may not
        # produce a title proposal or canonical metadata mutation afterward.
        self._accept_auxiliary_provider_response(thread_id)
        return response

    def _thread_title_fq_model_key(self) -> str | None:
        if self._llm_service is None:
            return None
        value = self._llm_service.thread_title_fq_model_key()
        if not isinstance(value, str):
            return None
        return value.strip() or None

    @staticmethod
    def _is_initial_title_target(snapshot: ConversationSnapshot, first_user_message_id: str) -> bool:
        final_messages = [
            message
            for message in snapshot.messages
            if message.kind is not ConversationMessageKind.PENDING_LLM_SAMPLING
        ]
        return (
            _is_blank_thread_title(snapshot.thread.title)
            and len(final_messages) == 1
            and final_messages[0].id == first_user_message_id
            and final_messages[0].kind is ConversationMessageKind.USER
        )

    @staticmethod
    def _initial_thread_title_prompt(snapshot: ConversationSnapshot) -> str:
        first_message = next(
            (
                message
                for message in snapshot.messages
                if message.kind is ConversationMessageKind.USER
            ),
            None,
        )
        content = (
            blocks_to_markdown(blocks_from_payload(first_message.content_payload))
            if first_message is not None
            else ""
        )
        return "Create a short title for this first user message.\n\nMessage:\n" + content

    @staticmethod
    def _thread_title_snapshot_prompt(snapshot: ConversationSnapshot) -> str:
        messages = [
            {
                "kind": message.kind.value,
                "text": _thread_title_message_text(message),
            }
            for message in snapshot.messages
            if message.kind is not ConversationMessageKind.PENDING_LLM_SAMPLING
        ]
        payload = {
            "thread_id": snapshot.thread.id,
            "current_title": snapshot.thread.title,
            "messages": messages,
        }
        return (
            "Create a short title for this full conversation thread. "
            "Use all persisted messages in the JSON payload.\n\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

    @staticmethod
    def _fallback_initial_thread_title(snapshot: ConversationSnapshot) -> str:
        first_message = next(
            (
                message
                for message in snapshot.messages
                if message.kind is ConversationMessageKind.USER
            ),
            None,
        )
        if first_message is None:
            return "New analysis"
        for block in blocks_from_payload(first_message.content_payload):
            if isinstance(block, (TextBlock, MarkdownBlock)):
                title = _sanitize_thread_title(block.text)
            elif isinstance(block, DatasetBlock):
                title = _sanitize_thread_title(block.name)
            elif isinstance(block, SourceAttachmentBlock):
                title = _sanitize_thread_title(_file_stem(block.file_name))
            else:
                title = None
            if title is not None:
                return title
        return "New analysis"


def _assistant_response_text(response: ProviderResponse) -> str:
    return "\n".join(
        item.text.strip()
        for item in response.output_items
        if isinstance(item, AssistantOutputItem) and item.text and item.text.strip()
    )


def _thread_title_message_text(message: ConversationMessageRow) -> str:
    if message.kind in {ConversationMessageKind.USER, ConversationMessageKind.CLIENT_CONTROL}:
        return blocks_to_markdown(blocks_from_payload(message.content_payload))
    if message.kind is ConversationMessageKind.ASSISTANT:
        return "\n".join(value for value in (message.text, message.refusal) if value)
    if message.kind is ConversationMessageKind.TOOL_CALL:
        return f"Tool call: {message.tool_id or ''}".strip()
    if message.kind is ConversationMessageKind.TOOL_RESULT:
        return message.error_summary or "Tool result"
    return ""


def _file_stem(file_name: str | None) -> str:
    return Path(file_name).stem if file_name else ""


def _is_blank_thread_title(value: str | None) -> bool:
    return not value or not value.strip()


def _sanitize_thread_title(raw: str) -> str | None:
    title = re.sub(r"\s+", " ", raw).strip().lstrip("#-*• ").strip()
    for prefix in ("Title:", "title:", "标题：", "标题:"):
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
            break
    title = title.strip("\"'`“”‘’").rstrip(".。!！?？").strip()
    return (title[:THREAD_TITLE_MAX_LENGTH].rstrip() or None) if title else None


__all__ = ["TitleGenerationMixin"]
