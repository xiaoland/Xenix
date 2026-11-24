"""Canonical Conversation authority owned by the LLM boundary.

The service is intentionally the only production holder of the writer
capability.  It accepts immutable commands, keeps incomplete model output in
memory, and commits a complete LLM emission (including every Tool Result) or
nothing at all.

Data models live in ``conversation_models`` and title generation in
``conversation_titles`` so this module stays the narrow canonical writer.
"""

from __future__ import annotations

import copy
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from ...exceptions import NotFoundError, ValidationError, report_exception
from ...observability import (
    LLMTokenUsage,
    LLMUsageObservability,
    LLMUsageObservation,
    NullLLMUsageObservability,
)
from ..storage.identity import reserve_ids
from ..storage.models import (
    ConversationMessageKind,
    ConversationMessageRow,
    ConversationThreadRow,
    default_agent_thread_system_prompt,
)
from ..storage.repositories import ConversationRepository
from .conversation_messages import (
    build_final_message_rows,
    build_provider_messages,
    validate_exchange_result_budget,
    validate_user_append_messages,
)
from .conversation_models import (
    AppendUserMessageInput,
    ConversationLiveEvent,
    ConversationSnapshot,
    ConversationUsageOverview,
    CreateConversationThreadInput,
    PendingSampling,
    SubmissionClaim,
    ThreadPausedError,
    _PendingExchange,
    _ThreadControl,
    _utc_now,
)
from .conversation_titles import TitleGenerationMixin
from .conversation_usage import primary_usage_root, query_usage_overviews
from .messages import (
    AssistantOutputItem,
    ProviderOutputItem,
    SourceAttachmentBlock,
    ToolCallOutputItem,
    blocks_to_json,
    normalize_message_blocks,
)
from .providers import (
    AgentProvider,
    LLMRetryEvent,
    ProviderMessage,
    ProviderResponse,
    ProviderStreamEvent,
)
from .service import LLMModelOption, LLMService
from .tool_protocol import (
    StagedToolCall,
    ToolExecutionContext,
    ToolScope,
    scope_fingerprint,
    terminal_tool_result,
    tool_failure_from_exception,
)
from .tool_registry import (
    AgentToolRegistry,
)

LOGGER = logging.getLogger(__name__)


class LLMConversationService(TitleGenerationMixin):
    """Deep Conversation facade and sole canonical writer.

    Provider and Tool I/O deliberately run outside a Thread gate.  Every
    callback re-enters through the pending-message compare-and-swap below.
    """

    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        llm_service: LLMService | None = None,
        tool_registry: AgentToolRegistry | None = None,
        context_messages_provider: Callable[[ConversationSnapshot], list[ProviderMessage]] | None = None,
        usage_observability: LLMUsageObservability | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._llm_service = llm_service
        self._tool_registry = tool_registry or AgentToolRegistry()
        self._context_messages_provider = context_messages_provider
        self._usage_observability = usage_observability or NullLLMUsageObservability()
        self._repository = ConversationRepository()
        self._gates_lock = threading.Lock()
        self._thread_gates: dict[int, threading.RLock] = {}
        self._claims: set[tuple[int, str]] = set()
        self._claims_lock = threading.Lock()
        self._pending: dict[int, _PendingExchange] = {}
        self._pending_lock = threading.RLock()
        self._thread_controls: dict[int, _ThreadControl] = {}

    @property
    def tool_registry(self) -> AgentToolRegistry:
        return self._tool_registry

    def model_options(self) -> list[LLMModelOption]:
        return self._require_llm_service().model_options()

    def default_fq_model_key(self) -> str:
        return self._require_llm_service().default_fq_model_key()

    def validate_fq_model_key(self, fq_model_key: str) -> str:
        return self._require_llm_service().validate_fq_model_key(fq_model_key)

    def create_thread(self, input_data: CreateConversationThreadInput | None = None) -> ConversationSnapshot:
        input_data = input_data or CreateConversationThreadInput()
        title = input_data.title.strip() if input_data.title else None
        system_prompt = (input_data.system_prompt or "").strip() or default_agent_thread_system_prompt(
            input_data.interface_locale
        )
        model_key = (input_data.selected_fq_model_key or "").strip() or None
        now = _utc_now()
        row = ConversationThreadRow(
            title=title,
            system_prompt=system_prompt,
            selected_fq_model_key=model_key,
            created_at=now,
            updated_at=now,
        )
        with self._session_factory() as session:
            self._repository.create_thread(session, row)
            session.commit()
        return ConversationSnapshot(thread=row, messages=[])

    def list_threads(self) -> list[ConversationThreadRow]:
        with self._session_factory() as session:
            return self._repository.list_threads(session)

    def get_thread_snapshot(self, thread_id: int) -> ConversationSnapshot:
        with self._session_factory() as session:
            thread = self._repository.get_thread(session, thread_id)
            if thread is None:
                raise NotFoundError(f"Conversation Thread '{thread_id}' was not found.")
            return ConversationSnapshot(thread=thread, messages=self._repository.list_messages(session, thread_id))

    def usage_overviews(self, snapshot: ConversationSnapshot) -> tuple[ConversationUsageOverview, ...]:
        """Read safe token totals for completed User-to-LLM interactions."""

        return query_usage_overviews(snapshot, self._usage_observability)

    def rename_thread(self, thread_id: int, title: str | None) -> ConversationSnapshot:
        with self._gate(thread_id):
            with self._session_factory() as session:
                row = self._repository.rename_thread(session, thread_id, title.strip() if title else None, _utc_now())
                if row is None:
                    raise NotFoundError(f"Conversation Thread '{thread_id}' was not found.")
                session.commit()
            return self.get_thread_snapshot(thread_id)

    def set_thread_model(self, thread_id: int, fq_model_key: str) -> ConversationSnapshot:
        selected = self.validate_fq_model_key(fq_model_key)
        with self._gate(thread_id):
            with self._session_factory() as session:
                thread = self._repository.get_thread(session, thread_id)
                if thread is None:
                    raise NotFoundError(f"Conversation Thread '{thread_id}' was not found.")
                if self._repository.list_pending(session, thread_id):
                    raise ValidationError("Cannot change the model while LLM sampling is pending.")
                thread.selected_fq_model_key = selected
                thread.updated_at = _utc_now()
                session.add(thread)
                session.commit()
            return self.get_thread_snapshot(thread_id)

    def delete_thread(self, thread_id: int) -> None:
        with self._pending_lock:
            with self._gate(thread_id):
                with self._session_factory() as session:
                    if self._repository.list_pending(session, thread_id):
                        raise ValidationError("Cannot delete a Thread while LLM sampling is pending.")
                    row = self._repository.delete_thread(session, thread_id)
                    if row is None:
                        raise NotFoundError(f"Conversation Thread '{thread_id}' was not found.")
                    session.commit()
                self._thread_controls.pop(thread_id, None)

    def pause_thread(self, thread_id: int) -> None:
        """Pause new LLM provider sends for one Thread in this process only."""

        with self._pending_lock:
            with self._gate(thread_id):
                with self._session_factory() as session:
                    if self._repository.get_thread(session, thread_id) is None:
                        raise NotFoundError(f"Conversation Thread '{thread_id}' was not found.")
                control = self._thread_control_locked(thread_id)
                if not control.paused:
                    control.paused = True

    def is_thread_paused(self, thread_id: int) -> bool:
        """Return only runtime pause state; it is intentionally not durable."""

        with self._pending_lock:
            return self._thread_control_locked(thread_id).paused

    def claim_user_submission(
        self,
        *,
        thread_id: int | None,
        expected_frontier_id: int | None,
        client_submission_id: str,
    ) -> SubmissionClaim:
        normalized_id = client_submission_id.strip()
        if not normalized_id:
            raise ValidationError("Client submission ID cannot be empty.")
        if thread_id is None:
            return SubmissionClaim(thread_id=None, expected_frontier_id=None, client_submission_id=normalized_id)
        with self._pending_lock:
            with self._gate(thread_id):
                snapshot = self.get_thread_snapshot(thread_id)
                duplicate = next(
                    (message for message in snapshot.messages if message.client_submission_id == normalized_id),
                    None,
                )
                if duplicate is not None:
                    return SubmissionClaim(
                        thread_id=thread_id,
                        expected_frontier_id=expected_frontier_id,
                        client_submission_id=normalized_id,
                        existing_message_id=duplicate.id,
                    )
                validate_user_append_messages(
                    snapshot.messages,
                    expected_frontier_id,
                    allow_paused_frontier=self._thread_control_locked(thread_id).paused,
                )
                key = (thread_id, normalized_id)
                with self._claims_lock:
                    if key in self._claims:
                        raise ValidationError("This submission is already being prepared.")
                    self._claims.add(key)
                return SubmissionClaim(
                    thread_id=thread_id,
                    expected_frontier_id=expected_frontier_id,
                    client_submission_id=normalized_id,
                    initial_title_eligible=self.is_initial_title_eligible(snapshot),
                )

    def release_user_submission_claim(self, claim: SubmissionClaim) -> None:
        if not claim.thread_id:
            return
        with self._claims_lock:
            self._claims.discard((claim.thread_id, claim.client_submission_id))

    def append_user_message(
        self,
        input_data: AppendUserMessageInput,
        *,
        expected_frontier_id: int | None = None,
    ) -> ConversationSnapshot:
        client_submission_id = input_data.client_submission_id.strip()
        if not client_submission_id:
            raise ValidationError("Client submission ID cannot be empty.")
        with self._pending_lock:
            with self._gate(input_data.thread_id):
                control = self._thread_control_locked(input_data.thread_id)
                with self._session_factory() as session:
                    thread = self._repository.get_thread(session, input_data.thread_id)
                    if thread is None:
                        raise NotFoundError(f"Conversation Thread '{input_data.thread_id}' was not found.")
                    messages = self._repository.list_messages(session, input_data.thread_id)
                    duplicate = next(
                        (row for row in messages if row.client_submission_id == client_submission_id),
                        None,
                    )
                    if duplicate is None:
                        validate_user_append_messages(
                            messages,
                            expected_frontier_id,
                            allow_paused_frontier=control.paused,
                        )
                        canonical_blocks = normalize_message_blocks(input_data.content_blocks)
                        if any(isinstance(block, SourceAttachmentBlock) for block in canonical_blocks):
                            raise ValidationError(
                                "SourceAttachmentBlock is a legacy presentation block and cannot be written to a new User Message."
                            )
                        row = ConversationMessageRow(
                            thread_id=input_data.thread_id,
                            sequence_index=len(messages),
                            kind=ConversationMessageKind.USER,
                            client_submission_id=client_submission_id,
                            content_payload={"blocks": blocks_to_json(canonical_blocks)},
                            created_at=_utc_now(),
                        )
                        self._repository.append_message(session, row)
                        thread.updated_at = _utc_now()
                        session.add(thread)
                        session.commit()
                        # A new explicit User Message is the only re-entry
                        # command.  It never automatically replays the paused
                        # ToolResult frontier.
                        if control.paused:
                            control.paused = False
                    return ConversationSnapshot(
                        thread=thread,
                        messages=self._repository.list_messages(session, input_data.thread_id),
                    )

    def sample_existing_frontier(
        self,
        *,
        thread_id: int,
        expected_frontier_id: int,
        tool_scope: ToolScope | None = None,
        fq_model_key: str | None = None,
        provider: AgentProvider | None = None,
        retry_callback: Callable[[LLMRetryEvent], None] | None = None,
    ) -> PendingSampling:
        pending = self.begin_sampling(
            thread_id=thread_id,
            expected_frontier_id=expected_frontier_id,
            tool_scope=tool_scope or ToolScope(),
        )
        return self.complete_pending_sampling(
            pending_message_id=pending.pending_message_id,
            provider=provider,
            fq_model_key=fq_model_key,
            retry_callback=retry_callback,
        )

    def begin_sampling(
        self,
        *,
        thread_id: int,
        expected_frontier_id: int,
        tool_scope: ToolScope | None = None,
    ) -> PendingSampling:
        """Persist the pre-I/O placeholder and grant a live sampling capability."""

        return self._begin_sampling(
            thread_id=thread_id,
            expected_frontier_id=expected_frontier_id,
            tool_scope=tool_scope or ToolScope(),
        )

    def complete_pending_sampling(
        self,
        *,
        pending_message_id: int,
        provider: AgentProvider | None = None,
        fq_model_key: str | None = None,
        retry_callback: Callable[[LLMRetryEvent], None] | None = None,
    ) -> PendingSampling:
        """Perform provider I/O for an already-created pending placeholder."""

        try:
            with self._pending_lock:
                exchange = self._current_exchange(pending_message_id)
                scope = exchange.scope
                thread_id = exchange.thread_id
            snapshot = self.get_thread_snapshot(thread_id)
            selected_model_key = fq_model_key or snapshot.thread.selected_fq_model_key
            response = self._complete(
                provider=provider,
                fq_model_key=selected_model_key,
                messages=self._provider_messages(snapshot),
                tool_scope=scope,
                retry_callback=retry_callback,
                before_provider_request=lambda: self._admit_provider_request(pending_message_id),
            )
            return self._stage_provider_response(
                pending_message_id,
                response,
                fq_model_key=selected_model_key,
            )
        except Exception:
            self.cancel_sampling(pending_message_id)
            raise

    def sample_existing_frontier_stream(
        self,
        *,
        thread_id: int,
        expected_frontier_id: int,
        tool_scope: ToolScope | None = None,
        fq_model_key: str | None = None,
    ) -> Iterator[ConversationLiveEvent | PendingSampling]:
        effective_scope = tool_scope or ToolScope()
        pending = self.begin_sampling(
            thread_id=thread_id,
            expected_frontier_id=expected_frontier_id,
            tool_scope=effective_scope,
        )
        handed_off = False
        try:
            yield ConversationLiveEvent(kind="sampling_started", pending_message_id=pending.pending_message_id)
            snapshot = self.get_thread_snapshot(thread_id)
            service = self._require_llm_service()
            selected_model_key = fq_model_key or snapshot.thread.selected_fq_model_key
            final_response: ProviderResponse | None = None
            stream_arguments = {
                "fq_model_key": selected_model_key,
                "messages": self._provider_messages(snapshot),
                "tools": self._tool_registry.list_specs(effective_scope),
                "before_provider_request": lambda: self._admit_provider_request(pending.pending_message_id),
            }
            for event in service.stream(**stream_arguments):
                if isinstance(event, LLMRetryEvent):
                    yield ConversationLiveEvent(kind="retry", pending_message_id=pending.pending_message_id, retry=event)
                elif isinstance(event, ProviderStreamEvent):
                    if event.is_tool_call_delta:
                        yield ConversationLiveEvent(kind="tool_progress", pending_message_id=pending.pending_message_id)
                    if event.response is not None:
                        final_response = event.response
            if final_response is None:
                raise ValidationError("LLM stream completed without a normalized response.")
            staged = self._stage_provider_response(
                pending.pending_message_id,
                final_response,
                fq_model_key=selected_model_key,
            )
            # Once the staged capability is delivered, the caller owns the
            # next explicit action: finalize it or cancel it.  Before that
            # handoff, generator abandonment must revoke the placeholder.
            handed_off = True
            yield staged
        finally:
            if not handed_off:
                self.cancel_sampling(pending.pending_message_id)

    def list_staged_tool_calls(self, pending_message_id: int) -> tuple[StagedToolCall, ...]:
        with self._pending_lock:
            exchange = self._pending.get(pending_message_id)
            if exchange is None or exchange.cancelled:
                raise ValidationError("The pending LLM exchange is no longer current.")
            return tuple(exchange.calls.values())

    def finalize_pending_assistant(self, pending_message_id: int) -> ConversationSnapshot:
        with self._pending_lock:
            exchange = self._current_exchange(pending_message_id)
            if exchange.calls:
                raise ValidationError("A tool-calling exchange can finalize only after all Tool Results exist.")
            with self._gate(exchange.thread_id):
                if self._exchange_is_paused_locked(exchange):
                    self._discard_pending_locked(exchange.thread_id, expected_pending_id=pending_message_id)
                    raise ThreadPausedError(exchange.thread_id)
        return self._finalize_exchange(pending_message_id)

    def invoke_staged_tool(
        self,
        *,
        pending_message_id: int,
        staged_call_message_id: int,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> ConversationSnapshot | None:
        cancel_requested = cancel_requested or (lambda: False)
        with self._pending_lock:
            exchange = self._pending.get(pending_message_id)
            if exchange is None or exchange.cancelled:
                # A provider/tool callback can arrive after cancellation has
                # revoked its live capability.  It is not an invalid command
                # and must not resurrect or poison the Thread.
                return None
            call = exchange.calls.get(staged_call_message_id)
            if call is None:
                raise ValidationError("The staged Tool Call is not part of this pending exchange.")
            if staged_call_message_id in exchange.results:
                raise ValidationError("The staged Tool Call already has a terminal result.")
            with self._gate(exchange.thread_id):
                # Once one Tool in an admitted exchange has crossed this
                # boundary, its complete result set may still converge after
                # a pause.  Before that boundary, Stop wins without starting
                # a fresh domain-side effect.
                if not exchange.tool_execution_started and self._exchange_is_paused_locked(exchange):
                    self._discard_pending_locked(exchange.thread_id, expected_pending_id=pending_message_id)
                    raise ThreadPausedError(exchange.thread_id)
                exchange.tool_execution_started = True

        if cancel_requested():
            self.cancel_sampling(pending_message_id)
            return None
        try:
            outcome = self._tool_registry.invoke(
                tool_name=call.tool_name,
                arguments=call.arguments,
                context=ToolExecutionContext(
                    thread_id=exchange.thread_id,
                    tool_call_message_id=staged_call_message_id,
                    dataset_ids=exchange.scope.dataset_ids,
                    cancel_requested=cancel_requested,
                ),
            )
            terminal = terminal_tool_result(outcome)
        except Exception as exc:
            logging.getLogger(__name__).exception("Operation failed: %s", exc)
            # Project the failure once into the same canonical value consumed
            # by the provider and Chatbot.  The concrete exception message is
            # preserved so the agent sees what actually failed.
            terminal = terminal_tool_result(tool_failure_from_exception(exc))

        if cancel_requested():
            self.cancel_sampling(pending_message_id)
            return None

        try:
            with self._pending_lock:
                exchange = self._pending.get(pending_message_id)
                if exchange is None or exchange.cancelled:
                    return None
                if staged_call_message_id not in exchange.calls:
                    raise ValidationError("The staged Tool Call is not part of this pending exchange.")
                if staged_call_message_id in exchange.results:
                    raise ValidationError("The staged Tool Call already has a terminal result.")
                exchange.results[staged_call_message_id] = terminal
                if len(exchange.results) != len(exchange.calls):
                    return None
        except Exception:
            # A complete result set that cannot be committed is no longer a
            # valid live exchange.  Discard its placeholder instead of leaving
            # a hidden pending tombstone that blocks future client messages.
            self.cancel_sampling(pending_message_id)
            raise
        return self._finalize_exchange(pending_message_id)

    def cancel_sampling(self, pending_message_id: int) -> None:
        with self._pending_lock:
            exchange = self._pending.get(pending_message_id)
            if exchange is None:
                return
            with self._gate(exchange.thread_id):
                self._discard_pending_locked(exchange.thread_id, expected_pending_id=pending_message_id)

    def discard_stale_pending_messages(self) -> int:
        """Main-writer startup barrier only; workers must never call this."""

        removed = 0
        with self._session_factory() as session:
            stale = session.exec(
                select(ConversationMessageRow).where(
                    ConversationMessageRow.kind == ConversationMessageKind.PENDING_LLM_SAMPLING
                )
            ).all()
            for row in stale:
                session.delete(row)
                removed += 1
            session.commit()
        with self._pending_lock:
            self._pending.clear()
        return removed

    def _begin_sampling(
        self,
        *,
        thread_id: int,
        expected_frontier_id: int,
        tool_scope: ToolScope,
    ) -> PendingSampling:
        # Tool definitions are part of the pre-I/O sampling capability.  Fully
        # validate their fingerprint before durable state changes so an invalid
        # registry cannot leave a placeholder tombstone behind.
        advertised_scope_fingerprint = scope_fingerprint(
            tool_scope, self._tool_registry.list_specs(tool_scope)
        )
        # Every path that both observes and mutates a pending capability takes
        # the locks in this order.  It prevents a begin/cancel inversion while
        # keeping provider and tool I/O outside both locks.
        with self._pending_lock:
            with self._gate(thread_id):
                control = self._thread_control_locked(thread_id)
                if control.paused:
                    raise ThreadPausedError(thread_id)
                with self._session_factory() as session:
                    thread = self._repository.get_thread(session, thread_id)
                    if thread is None:
                        raise NotFoundError(f"Conversation Thread '{thread_id}' was not found.")
                    messages = self._repository.list_messages(session, thread_id)
                    if any(row.kind is ConversationMessageKind.PENDING_LLM_SAMPLING for row in messages):
                        raise ValidationError("LLM sampling is already pending for this Thread.")
                    if not messages or messages[-1].id != expected_frontier_id:
                        raise ValidationError("The requested LLM frontier is stale.")
                    if messages[-1].kind not in {
                        ConversationMessageKind.USER,
                        ConversationMessageKind.CLIENT_CONTROL,
                        ConversationMessageKind.TOOL_RESULT,
                    }:
                        raise ValidationError("The Thread frontier is not eligible for LLM sampling.")
                    row = ConversationMessageRow(
                        thread_id=thread_id,
                        sequence_index=len(messages),
                        kind=ConversationMessageKind.PENDING_LLM_SAMPLING,
                        created_at=_utc_now(),
                    )
                    self._repository.append_message(session, row)
                    session.commit()
                exchange = _PendingExchange(
                    pending_message_id=row.id,
                    thread_id=thread_id,
                    sequence_index=row.sequence_index,
                    frontier_message_id=expected_frontier_id,
                    root_user_message_id=primary_usage_root(messages),
                    scope=tool_scope,
                    scope_fingerprint=advertised_scope_fingerprint,
                )
                self._pending[row.id] = exchange
                return PendingSampling(
                    pending_message_id=row.id,
                    thread_id=thread_id,
                )

    def _stage_provider_response(
        self,
        pending_message_id: int,
        response: ProviderResponse,
        *,
        fq_model_key: str | None,
    ) -> PendingSampling:
        observation = self._primary_usage_observation(
            pending_message_id=pending_message_id,
            usage_payload=response.usage_payload,
            fq_model_key=fq_model_key,
        )
        if observation is not None:
            # The provider has already spent these tokens even if later
            # canonical-output validation rejects the response.  The journal
            # preserves that fact; only a closed canonical interaction makes
            # it eligible for a Chatbot overview.
            self._record_usage_observation(observation)
        self._accept_provider_response(pending_message_id)
        pending = self._stage_provider_output(pending_message_id, response.output_items)
        return pending

    def _stage_provider_output(
        self,
        pending_message_id: int,
        output_items: list[ProviderOutputItem],
    ) -> PendingSampling:
        if not output_items:
            raise ValidationError("LLM output is empty.")
        with self._pending_lock:
            exchange = self._current_exchange(pending_message_id)
            calls: dict[int, StagedToolCall] = {}
            assistant_seen = False
            for item in output_items:
                if isinstance(item, AssistantOutputItem):
                    if assistant_seen or item.is_empty:
                        raise ValidationError("LLM Assistant output is malformed.")
                    assistant_seen = True
                    continue
                if not isinstance(item, ToolCallOutputItem):
                    raise ValidationError("LLM output item is unsupported.")
                # Resolve against all registrations, independently of advertised
                # definitions. Unknown names survive to invocation as ToolFailures.
                requested_name = item.provider_name or item.tool_name
                call_id = reserve_ids(self._session_factory)[0]
                calls[call_id] = StagedToolCall(
                    pending_message_id=pending_message_id,
                    staged_call_id=call_id,
                    provider_call_id=item.provider_call_id,
                    tool_name=self._tool_registry.resolve_name(requested_name),
                    provider_name=requested_name,
                    arguments=copy.deepcopy(item.arguments),
                    scope_fingerprint=exchange.scope_fingerprint,
                )
            exchange.output_items = tuple(output_items)
            exchange.calls = calls
            return PendingSampling(
                pending_message_id=pending_message_id,
                thread_id=exchange.thread_id,
                staged_calls=tuple(calls.values()),
                has_assistant_output=assistant_seen,
            )

    def _finalize_exchange(self, pending_message_id: int) -> ConversationSnapshot:
        with self._pending_lock:
            exchange = self._current_exchange(pending_message_id)
            if exchange.calls and len(exchange.calls) != len(exchange.results):
                raise ValidationError("The complete terminal Tool Result set is required before finalization.")
        try:
            with self._pending_lock:
                exchange = self._current_exchange(pending_message_id)
                validate_exchange_result_budget(exchange)
                with self._gate(exchange.thread_id):
                    if not exchange.tool_execution_started and self._exchange_is_paused_locked(exchange):
                        self._discard_pending_locked(exchange.thread_id, expected_pending_id=pending_message_id)
                        raise ThreadPausedError(exchange.thread_id)
                    with self._session_factory() as session:
                        pending = self._repository.get_message(session, pending_message_id)
                        if pending is None or pending.kind is not ConversationMessageKind.PENDING_LLM_SAMPLING:
                            raise ValidationError("The pending LLM exchange is no longer current.")
                        if pending.thread_id != exchange.thread_id:
                            raise ValidationError("The pending LLM exchange has an invalid Thread.")
                        session.delete(pending)
                        # The final Message reuses the placeholder's sequence slot.
                        # SQLite unique checks run per statement, so force the delete
                        # before staging its immutable replacements.
                        session.flush()
                        sequence = exchange.sequence_index
                        inserted = build_final_message_rows(exchange, sequence)
                        for row in inserted:
                            session.add(row)
                        thread = self._repository.get_thread(session, exchange.thread_id)
                        if thread is None:
                            raise NotFoundError(f"Conversation Thread '{exchange.thread_id}' was not found.")
                        thread.updated_at = _utc_now()
                        session.add(thread)
                        session.commit()
                        snapshot = ConversationSnapshot(
                            thread=thread,
                            messages=self._repository.list_messages(session, exchange.thread_id),
                        )
                    self._pending.pop(pending_message_id, None)
                    return snapshot
        except Exception:
            # Any failure after the exchange passed its public preconditions
            # must leave neither a durable placeholder nor an in-memory writer
            # capability.  Canonical state therefore returns to its client
            # frontier rather than retaining a recoverable pseudo-run.
            self.cancel_sampling(pending_message_id)
            raise

    def _complete(
        self,
        *,
        provider: AgentProvider | None,
        fq_model_key: str | None,
        messages: list[ProviderMessage],
        tool_scope: ToolScope,
        retry_callback: Callable[[LLMRetryEvent], None] | None,
        before_provider_request: Callable[[], None] | None = None,
    ) -> ProviderResponse:
        specs = self._tool_registry.list_specs(tool_scope)
        if provider is not None:
            if before_provider_request is not None:
                before_provider_request()
            return provider.complete(messages, specs)
        arguments = {
            "fq_model_key": fq_model_key,
            "messages": messages,
            "tools": specs,
            "retry_callback": retry_callback,
            "before_provider_request": before_provider_request,
        }
        return self._require_llm_service().complete(**arguments)

    def _provider_messages(self, snapshot: ConversationSnapshot) -> list[ProviderMessage]:
        return build_provider_messages(
            snapshot,
            tool_registry=self._tool_registry,
            context_messages_provider=self._context_messages_provider,
        )

    def _primary_usage_observation(
        self,
        *,
        pending_message_id: int,
        usage_payload: dict[str, Any] | None,
        fq_model_key: str | None,
    ) -> LLMUsageObservation | None:
        usage = LLMTokenUsage.from_payload(usage_payload)
        if usage is None:
            return None
        with self._pending_lock:
            exchange = self._pending.get(pending_message_id)
            if exchange is None:
                return None
            return LLMUsageObservation(
                operation="primary",
                usage=usage,
                thread_id=exchange.thread_id,
                root_user_message_id=exchange.root_user_message_id,
                frontier_message_id=exchange.frontier_message_id,
                pending_message_id=exchange.pending_message_id,
                fq_model_key=fq_model_key,
            )

    def _record_auxiliary_usage(
        self,
        *,
        operation: str,
        thread_id: int,
        usage_payload: dict[str, Any] | None,
        fq_model_key: str | None,
    ) -> None:
        usage = LLMTokenUsage.from_payload(usage_payload)
        if usage is None:
            return
        self._record_usage_observation(
            LLMUsageObservation(
                operation=operation,
                usage=usage,
                thread_id=thread_id,
                fq_model_key=fq_model_key,
            )
        )

    def _record_usage_observation(self, observation: LLMUsageObservation) -> None:
        try:
            self._usage_observability.record_llm_usage(observation)
        except Exception as exc:
            report_exception(exc)
            LOGGER.warning("LLM usage observability write failed: %s", exc.__class__.__name__)

    def _admit_provider_request(self, pending_message_id: int) -> None:
        """Linearize one provider attempt against the runtime Thread pause."""

        with self._pending_lock:
            exchange = self._current_exchange(pending_message_id)
            with self._gate(exchange.thread_id):
                if self._exchange_is_paused_locked(exchange):
                    self._discard_pending_locked(exchange.thread_id, expected_pending_id=pending_message_id)
                    raise ThreadPausedError(exchange.thread_id)

    def _accept_provider_response(self, pending_message_id: int) -> None:
        """Discard a response that returned after a Thread pause won."""

        with self._pending_lock:
            exchange = self._current_exchange(pending_message_id)
            with self._gate(exchange.thread_id):
                if self._exchange_is_paused_locked(exchange):
                    self._discard_pending_locked(exchange.thread_id, expected_pending_id=pending_message_id)
                    raise ThreadPausedError(exchange.thread_id)

    def _accept_auxiliary_provider_response(self, thread_id: int) -> None:
        """Reject metadata-provider output returned after a Thread pause."""

        with self._pending_lock:
            with self._gate(thread_id):
                if self._thread_control_locked(thread_id).paused:
                    raise ThreadPausedError(thread_id)

    def _admit_auxiliary_provider_request(self, thread_id: int) -> None:
        """Give metadata LLM work the same Thread-pause admission rule."""

        with self._pending_lock:
            with self._gate(thread_id):
                if self._thread_control_locked(thread_id).paused:
                    raise ThreadPausedError(thread_id)

    def _exchange_is_paused_locked(self, exchange: _PendingExchange) -> bool:
        return self._thread_control_locked(exchange.thread_id).paused

    def _thread_control_locked(self, thread_id: int) -> _ThreadControl:
        """Return a Thread control while ``_pending_lock`` is held."""

        return self._thread_controls.setdefault(thread_id, _ThreadControl())

    def _discard_pending_locked(self, thread_id: int, expected_pending_id: int | None) -> None:
        matching_ids = {
            pending_id
            for pending_id, exchange in self._pending.items()
            if exchange.thread_id == thread_id
            and (expected_pending_id is None or pending_id == expected_pending_id)
        }
        committed = False
        try:
            with self._session_factory() as session:
                pending_rows = self._repository.list_pending(session, thread_id)
                for row in pending_rows:
                    if expected_pending_id is not None and row.id != expected_pending_id:
                        continue
                    matching_ids.add(row.id)
                    session.delete(row)
                session.commit()
                committed = True
        finally:
            if committed:
                # A finalization can commit before reading the final snapshot
                # fails; there is then no DB placeholder left to discover, but
                # the memory capability must still be revoked exactly once.
                # Conversely, a failed deletion transaction retains the live
                # capability so the caller sees the database failure instead
                # of being left with an unreachable durable placeholder.
                for pending_id in matching_ids:
                    exchange = self._pending.pop(pending_id, None)
                    if exchange is not None:
                        exchange.cancelled = True

    def _current_exchange(self, pending_message_id: int) -> _PendingExchange:
        exchange = self._pending.get(pending_message_id)
        if exchange is None or exchange.cancelled:
            raise ValidationError("The pending LLM exchange is no longer current.")
        return exchange

    def _gate_for(self, thread_id: int) -> threading.RLock:
        with self._gates_lock:
            return self._thread_gates.setdefault(thread_id, threading.RLock())

    @contextmanager
    def _gate(self, thread_id: int):
        gate = self._gate_for(thread_id)
        with gate:
            yield

    def _require_llm_service(self) -> LLMService:
        if self._llm_service is None:
            raise ValidationError("LLM Conversation Service has no model gateway.")
        return self._llm_service


__all__ = [
    "AppendUserMessageInput",
    "ConversationLiveEvent",
    "ConversationSnapshot",
    "ConversationUsageOverview",
    "CreateConversationThreadInput",
    "LLMConversationService",
    "PendingSampling",
    "SubmissionClaim",
    "ThreadPausedError",
]
