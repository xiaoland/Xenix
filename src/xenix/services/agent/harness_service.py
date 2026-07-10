from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
import threading
from time import perf_counter
from typing import TYPE_CHECKING, Any, Iterator

from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel

from ...exceptions import ValidationError
from ...observability import record_counter, record_histogram, set_span_attributes, start_span
from ..storage.models import (
    AgentMessageAuthor,
    AgentMessageKind,
    AgentMessageRow,
    AgentMessageStatus,
    AgentProviderRequestKind,
    AgentProviderRequestRow,
    AgentProviderRequestStatus,
    AgentRunStatus,
    AgentToolCallStatus,
)
from .conversation_store import (
    AppendAgentMessageInput,
    CompleteToolCallInput,
    CompleteProviderRequestInput,
    ConversationStore,
    CreateAgentThreadInput,
    CreateProviderRequestInput,
    CreateTurnCompletionGuardInput,
    CreateToolCallInput,
    FinishAgentRunInput,
    RenameAgentThreadInput,
    StartAgentRunInput,
    StartTurnInput,
    ThreadSnapshot,
    UpdateAgentThreadModelInput,
    UpdateAgentMessageInput,
)
from .completion_guard import (
    TURN_COMPLETION_GUARD_REMINDER,
    TurnCompletionGuard,
    TurnCompletionGuardResult,
    TurnCompletionGuardVerdict,
    _GUARD_SYSTEM_PROMPT,
    _parse_guard_output,
)
from .chatbot_events import (
    ChatbotEvent,
    ChatbotEventStatus,
    build_activity_chatbot_event,
    build_thinking_chatbot_event,
    build_llm_connection_chatbot_event,
    project_chatbot_events,
    project_text_message_event,
    project_tool_chatbot_event,
    should_project_agent_skill_tools,
)
from ..artifact_service import ArtifactService, build_artifact_uri
from ..dataset_service import DatasetService, RegisterDatasetInput
from ..llm import (
    AgentProvider,
    AgentToolSpec,
    LLMRetryEvent,
    ProviderMessage,
    ProviderResponse,
    ProviderStreamEvent,
    ProviderToolCall,
    extract_reasoning_content,
)
from .skill_catalog import (
    AGENT_SKILL_ACTIVATE_TOOL_NAME,
    AGENT_SKILL_READ_ASSET_TOOL_NAME,
    AGENT_SKILL_READ_REFERENCE_TOOL_NAME,
    AgentSkillCatalog,
    is_agent_skill_tool,
)
from . import observability as ai_observability
from .tool_presentations import tool_presentation_for_name
from ..llm import LLMModelOption, LLMService

if TYPE_CHECKING:
    from .tools import AgentToolRegistry, ToolExecutionContext


class DatasetAttachmentInput(SQLModel):
    dataset_id: str
    name: str
    file_name: str
    source_format: str
    row_count: int
    column_count: int
    preview_columns: list[str] = Field(default_factory=list)


class SourceAttachmentInput(SQLModel):
    artifact_id: str
    file_name: str
    source_format: str


class SubmitUserTurnInput(SQLModel):
    thread_id: str | None = None
    text: str
    dataset_attachments: list[DatasetAttachmentInput] = Field(default_factory=list)
    source_attachments: list[SourceAttachmentInput] = Field(default_factory=list)
    fq_model_key: str | None = None
    interface_locale: str | None = None


class ContinueStepBudgetInput(SQLModel):
    thread_id: str
    turn_id: str
    run_id: str
    additional_steps: int | None = None


@dataclass(frozen=True)
class AgentHarnessStreamEvent:
    kind: str
    thread_id: str | None = None
    turn_id: str | None = None
    run_id: str | None = None
    message_id: str | None = None
    message: AgentMessageRow | None = None
    chatbot_event: ChatbotEvent | None = None
    chatbot_events: list[ChatbotEvent] | None = None
    snapshot: ThreadSnapshot | None = None
    is_final: bool = False
    used_steps: int = 0
    suggested_steps: int = 0
    max_total_steps: int = 0


@dataclass(frozen=True)
class _ToolAvailabilityContext:
    dataset_ids: tuple[str, ...] = ()
    has_dataset: bool = False
    has_selection: bool = False
    has_trained_model: bool = False


@dataclass(frozen=True)
class StepBudgetPause:
    thread_id: str
    turn_id: str
    run_id: str
    message: AgentMessageRow
    used_steps: int
    suggested_steps: int
    max_total_steps: int
    snapshot: ThreadSnapshot


class AgentRunCancelled(Exception):
    pass


LOGGER = logging.getLogger(__name__)
THREAD_TITLE_MAX_LENGTH = 80
THREAD_TITLE_SYSTEM_PROMPT = (
    "You generate concise conversation titles for Xenix threads. "
    "Return exactly one title only. Use the user's language when it is clear. "
    "Do not include quotes, markdown, labels, or trailing punctuation."
)


class AgentHarnessService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        tool_registry: AgentToolRegistry,
        provider: AgentProvider | None = None,
        llm_service: LLMService | None = None,
        dataset_service: DatasetService | None = None,
        artifact_service: ArtifactService | None = None,
        turn_completion_guard_provider: AgentProvider | None = None,
        thread_title_provider: AgentProvider | None = None,
        conversation_store: ConversationStore | None = None,
        skill_catalog: AgentSkillCatalog | None = None,
        initial_step_limit: int = 16,
        step_extension_limit: int = 16,
        max_total_steps: int = 64,
    ) -> None:
        if provider is None and llm_service is None:
            raise ValidationError("Agent Harness requires a provider or an LLM service.")
        self._session_factory = session_factory
        self._provider = provider
        self._llm_service = llm_service
        self._dataset_service = dataset_service
        self._artifact_service = artifact_service
        self._turn_completion_guard = (
            TurnCompletionGuard(turn_completion_guard_provider)
            if turn_completion_guard_provider is not None
            else None
        )
        self._thread_title_provider = thread_title_provider
        self._tool_registry = tool_registry
        self._skill_catalog = skill_catalog
        self._conversation_store = conversation_store or ConversationStore(session_factory)
        self._initial_step_limit = max(1, initial_step_limit)
        self._step_extension_limit = max(1, step_extension_limit)
        self._max_total_steps = max(self._initial_step_limit, max_total_steps)
        self._cancel_events: dict[str, threading.Event] = {}
        self._cancel_lock = threading.Lock()

    def create_thread(
        self,
        title: str | None = None,
        fq_model_key: str | None = None,
        interface_locale: str | None = None,
    ) -> ThreadSnapshot:
        selected_fq_model_key = self._resolve_fq_model_key(fq_model_key, None)
        thread = self._conversation_store.create_thread(
            CreateAgentThreadInput(
                title=title,
                interface_locale=interface_locale,
                selected_fq_model_key=selected_fq_model_key,
            )
        )
        return self._conversation_store.get_thread_snapshot(thread.id)

    def list_threads(self):
        return self._conversation_store.list_threads()

    def rename_thread(self, thread_id: str, title: str | None) -> ThreadSnapshot:
        thread = self._conversation_store.rename_thread(RenameAgentThreadInput(thread_id=thread_id, title=title))
        return self._conversation_store.get_thread_snapshot(thread.id)

    def delete_thread(self, thread_id: str) -> None:
        self._conversation_store.delete_thread(thread_id)

    def get_thread_snapshot(self, thread_id: str) -> ThreadSnapshot:
        return self._conversation_store.get_thread_snapshot(thread_id)

    def list_llm_model_options(self) -> list[LLMModelOption]:
        if self._llm_service is None:
            return []
        return self._llm_service.model_options()

    def default_fq_model_key(self) -> str | None:
        if self._llm_service is None:
            return None
        return self._llm_service.default_fq_model_key()

    def set_thread_model(self, thread_id: str, fq_model_key: str) -> ThreadSnapshot:
        selected_fq_model_key = self._validate_fq_model_key(fq_model_key)
        thread = self._conversation_store.update_thread_model(
            UpdateAgentThreadModelInput(
                thread_id=thread_id,
                selected_fq_model_key=selected_fq_model_key,
            )
        )
        return self._conversation_store.get_thread_snapshot(thread.id)

    def has_thread_title_provider(self) -> bool:
        return self._thread_title_provider is not None or (
            self._llm_service is not None
            and self._llm_service.thread_title_fq_model_key() is not None
        )

    def generate_thread_title(self, thread_id: str) -> str:
        if not self.has_thread_title_provider():
            raise ValidationError("Thread title model is not configured.")
        snapshot = self._conversation_store.get_thread_snapshot(thread_id)
        title = self._llm_thread_title_from_snapshot(snapshot)
        if title is None:
            raise ValidationError("Thread title model returned an empty title.")
        return title

    def project_chatbot_events(self, snapshot: ThreadSnapshot) -> list[ChatbotEvent]:
        return project_chatbot_events(
            snapshot,
            tool_presentation_lookup=self._tool_presentation,
        )

    def _tool_presentation(self, tool_name: str):
        lookup = getattr(self._tool_registry, "tool_presentation", None)
        if callable(lookup):
            return lookup(tool_name)
        return tool_presentation_for_name(tool_name)

    def set_provider(self, provider: AgentProvider) -> None:
        self._provider = provider

    def set_turn_completion_guard_provider(self, provider: AgentProvider | None) -> None:
        self._turn_completion_guard = TurnCompletionGuard(provider) if provider is not None else None

    def set_thread_title_provider(self, provider: AgentProvider | None) -> None:
        self._thread_title_provider = provider

    def cancel_run(self, run_id: str) -> None:
        with self._cancel_lock:
            cancel_event = self._cancel_events.setdefault(run_id, threading.Event())
            cancel_event.set()

    def submit_user_turn(self, input_data: SubmitUserTurnInput) -> ThreadSnapshot:
        with start_span("agent.turn") as span:
            self._validate_turn_submission_before_materialization(input_data)
            imported_source_attachments = self._materialize_source_attachments(input_data)
            thread_id, turn_id, fq_model_key, provider = self._start_user_turn(
                input_data,
                imported_source_attachments=imported_source_attachments,
            )
            run_id = self._start_agent_run(thread_id, turn_id, fq_model_key=fq_model_key, provider=provider)
            set_span_attributes(span, ai_observability.turn_span_attributes(thread_id=thread_id, turn_id=turn_id, run_id=run_id))

            try:
                outcome = self._run_provider_loop(
                    thread_id=thread_id,
                    turn_id=turn_id,
                    run_id=run_id,
                    step_state=self._initial_step_state(),
                    fq_model_key=fq_model_key,
                    provider=provider,
                )
                if isinstance(outcome, StepBudgetPause):
                    self._record_agent_turn("awaiting_confirmation")
                    return outcome.snapshot
                self._conversation_store.finish_run(
                    FinishAgentRunInput(
                        run_id=run_id,
                        status=AgentRunStatus.SUCCEEDED,
                    )
                )
                self._record_agent_turn(AgentRunStatus.SUCCEEDED.value)
                return outcome
            except AgentRunCancelled:
                snapshot = self._cancel_run_and_turn(thread_id, turn_id, run_id)
                self._record_agent_turn(AgentRunStatus.CANCELLED.value)
                return snapshot
            except Exception as exc:
                self._conversation_store.finish_run(
                    FinishAgentRunInput(
                        run_id=run_id,
                        status=AgentRunStatus.FAILED,
                        error_summary=str(exc),
                    )
                )
                self._record_agent_turn(AgentRunStatus.FAILED.value, exc)
                raise
            finally:
                self._clear_cancel_event(run_id)

    def submit_user_turn_stream(self, input_data: SubmitUserTurnInput):
        with start_span("agent.turn") as span:
            self._validate_turn_submission_before_materialization(input_data)
            imported_source_attachments = self._materialize_source_attachments(input_data)
            thread_id, turn_id, fq_model_key, provider = self._start_user_turn(
                input_data,
                imported_source_attachments=imported_source_attachments,
            )
            run_id = self._start_agent_run(thread_id, turn_id, fq_model_key=fq_model_key, provider=provider)
            set_span_attributes(span, ai_observability.turn_span_attributes(thread_id=thread_id, turn_id=turn_id, run_id=run_id))
            yield from self._submit_user_turn_stream_started(thread_id, turn_id, run_id, fq_model_key, provider)

    def _submit_user_turn_stream_started(
        self,
        thread_id: str,
        turn_id: str,
        run_id: str,
        fq_model_key: str | None,
        provider: AgentProvider | None,
    ):
        snapshot = self._conversation_store.get_thread_snapshot(thread_id)
        yield AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id=thread_id,
            turn_id=turn_id,
            run_id=run_id,
            snapshot=snapshot,
            chatbot_events=self.project_chatbot_events(snapshot),
            is_final=False,
        )
        try:
            outcome = yield from self._run_provider_loop_stream(
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                step_state=self._initial_step_state(),
                fq_model_key=fq_model_key,
                provider=provider,
            )
            if isinstance(outcome, StepBudgetPause):
                self._record_agent_turn("awaiting_confirmation")
                yield self._step_confirmation_event(outcome)
                return
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=run_id,
                    status=AgentRunStatus.SUCCEEDED,
                )
            )
            self._record_agent_turn(AgentRunStatus.SUCCEEDED.value)
            yield AgentHarnessStreamEvent(
                kind="snapshot",
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                snapshot=outcome,
                chatbot_events=self.project_chatbot_events(outcome),
                is_final=True,
            )
        except AgentRunCancelled:
            snapshot = self._cancel_run_and_turn(thread_id, turn_id, run_id)
            self._record_agent_turn(AgentRunStatus.CANCELLED.value)
            yield AgentHarnessStreamEvent(
                kind="snapshot",
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                snapshot=snapshot,
                chatbot_events=self.project_chatbot_events(snapshot),
                is_final=True,
            )
            return
        except Exception as exc:
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=run_id,
                    status=AgentRunStatus.FAILED,
                    error_summary=str(exc),
                )
            )
            self._record_agent_turn(AgentRunStatus.FAILED.value, exc)
            raise
        finally:
            self._clear_cancel_event(run_id)

    def continue_step_budget_stream(self, input_data: ContinueStepBudgetInput):
        run = self._conversation_store.get_run(input_data.run_id)
        if run.status is not AgentRunStatus.AWAITING_CONFIRMATION:
            raise ValidationError("Agent run is not waiting for step confirmation.")
        if run.thread_id != input_data.thread_id or run.turn_id != input_data.turn_id:
            raise ValidationError("Step confirmation does not belong to the provided thread and turn.")

        step_state = self._step_state_from_payload(run.usage_payload)
        fq_model_key = self._fq_model_key_from_run_payload(run.usage_payload)
        provider = self._provider_for_run(run)
        granted_steps = self._requested_step_extension(input_data.additional_steps, step_state)
        step_state["granted_steps"] += granted_steps
        self._conversation_store.resume_run_after_confirmation(
            input_data.run_id,
            self._usage_payload(
                step_state,
                fq_model_key=self._fq_model_key_from_run_payload(run.usage_payload),
            ),
        )
        self._register_cancel_event(input_data.run_id)
        snapshot = self._conversation_store.get_thread_snapshot(input_data.thread_id)
        yield AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id=input_data.thread_id,
            turn_id=input_data.turn_id,
            run_id=input_data.run_id,
            snapshot=snapshot,
            chatbot_events=self.project_chatbot_events(snapshot),
            is_final=False,
        )
        try:
            outcome = yield from self._run_provider_loop_stream(
                thread_id=input_data.thread_id,
                turn_id=input_data.turn_id,
                run_id=input_data.run_id,
                step_state=step_state,
                fq_model_key=fq_model_key,
                provider=provider,
            )
            if isinstance(outcome, StepBudgetPause):
                yield self._step_confirmation_event(outcome)
                return
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=input_data.run_id,
                    status=AgentRunStatus.SUCCEEDED,
                )
            )
            yield AgentHarnessStreamEvent(
                kind="snapshot",
                thread_id=input_data.thread_id,
                turn_id=input_data.turn_id,
                run_id=input_data.run_id,
                snapshot=outcome,
                chatbot_events=self.project_chatbot_events(outcome),
                is_final=True,
            )
        except AgentRunCancelled:
            snapshot = self._cancel_run_and_turn(input_data.thread_id, input_data.turn_id, input_data.run_id)
            yield AgentHarnessStreamEvent(
                kind="snapshot",
                thread_id=input_data.thread_id,
                turn_id=input_data.turn_id,
                run_id=input_data.run_id,
                snapshot=snapshot,
                chatbot_events=self.project_chatbot_events(snapshot),
                is_final=True,
            )
            return
        except Exception as exc:
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=input_data.run_id,
                    status=AgentRunStatus.FAILED,
                    error_summary=str(exc),
                )
            )
            raise
        finally:
            self._clear_cancel_event(input_data.run_id)

    def stop_step_budget_confirmation(self, input_data: ContinueStepBudgetInput) -> ThreadSnapshot:
        run = self._conversation_store.get_run(input_data.run_id)
        if run.status is not AgentRunStatus.AWAITING_CONFIRMATION:
            raise ValidationError("Agent run is not waiting for step confirmation.")
        if run.thread_id != input_data.thread_id or run.turn_id != input_data.turn_id:
            raise ValidationError("Step confirmation does not belong to the provided thread and turn.")
        self._conversation_store.append_message(
            AppendAgentMessageInput(
                thread_id=input_data.thread_id,
                turn_id=input_data.turn_id,
                kind=AgentMessageKind.SYSTEM,
                ui_author=AgentMessageAuthor.SYSTEM,
                content_blocks=[
                    {
                        "type": "markdown",
                        "text": "The run was stopped after the step budget was exhausted.",
                    }
                ],
            )
        )
        self._conversation_store.cancel_turn(input_data.thread_id, input_data.turn_id)
        self._conversation_store.finish_run(
            FinishAgentRunInput(
                run_id=input_data.run_id,
                status=AgentRunStatus.CANCELLED,
                error_summary="User stopped the run after step budget exhaustion.",
            )
        )
        return self._conversation_store.get_thread_snapshot(input_data.thread_id)

    def _validate_turn_submission_before_materialization(self, input_data: SubmitUserTurnInput) -> None:
        text = input_data.text.strip()
        if not text and not input_data.dataset_attachments and not input_data.source_attachments:
            raise ValidationError("A turn needs a user message or at least one attachment.")
        if input_data.thread_id is None:
            self._resolve_fq_model_key(input_data.fq_model_key, None)
            return
        snapshot = self._conversation_store.get_thread_snapshot(input_data.thread_id)
        self._resolve_fq_model_key(input_data.fq_model_key, snapshot.thread.selected_fq_model_key)

    def _start_user_turn(
        self,
        input_data: SubmitUserTurnInput,
        *,
        imported_source_attachments: list[DatasetAttachmentInput] | None = None,
    ) -> tuple[str, str, str | None, AgentProvider | None]:
        text = input_data.text.strip()
        dataset_attachments = list(input_data.dataset_attachments)
        source_attachments = list(input_data.source_attachments)
        if not text and not dataset_attachments and not source_attachments:
            raise ValidationError("A turn needs a user message or at least one attachment.")

        thread_id = input_data.thread_id
        should_auto_title_existing_thread = False
        if thread_id is None:
            selected_fq_model_key = self._resolve_fq_model_key(input_data.fq_model_key, None)
            thread_id = self._conversation_store.create_thread(
                CreateAgentThreadInput(
                    title=self._title_from_first_message(text, dataset_attachments, source_attachments),
                    interface_locale=input_data.interface_locale,
                    selected_fq_model_key=selected_fq_model_key,
                )
            ).id
        else:
            snapshot = self._conversation_store.get_thread_snapshot(thread_id)
            should_auto_title_existing_thread = self._should_auto_title_thread(snapshot)
            selected_fq_model_key = self._resolve_fq_model_key(
                input_data.fq_model_key,
                snapshot.thread.selected_fq_model_key,
            )
            if selected_fq_model_key != snapshot.thread.selected_fq_model_key:
                self._conversation_store.update_thread_model(
                    UpdateAgentThreadModelInput(
                        thread_id=thread_id,
                        selected_fq_model_key=selected_fq_model_key,
                    )
                )
        provider = self._provider_for_fq_model_key(selected_fq_model_key) if self._llm_service is None else None

        content_blocks = self._user_content_blocks(text, dataset_attachments)
        content_blocks.extend(self._source_attachment_blocks(source_attachments))
        content_blocks.extend(self._hidden_dataset_blocks(imported_source_attachments or []))
        turn, _user_message = self._conversation_store.start_turn(
            StartTurnInput(
                thread_id=thread_id,
                user_content_blocks=content_blocks,
            )
        )
        if should_auto_title_existing_thread:
            self._conversation_store.rename_thread(
                RenameAgentThreadInput(
                    thread_id=thread_id,
                    title=self._title_from_first_message(text, dataset_attachments, source_attachments),
                )
            )
        return thread_id, turn.id, selected_fq_model_key, provider

    def _start_agent_run(
        self,
        thread_id: str,
        turn_id: str,
        *,
        fq_model_key: str | None,
        provider: AgentProvider | None,
    ) -> str:
        run = self._conversation_store.start_run(
            StartAgentRunInput(
                thread_id=thread_id,
                turn_id=turn_id,
                provider_name=self._target_provider_name(provider=provider, fq_model_key=fq_model_key),
                usage_payload=self._usage_payload(
                    self._initial_step_state(),
                    fq_model_key=fq_model_key,
                ),
            )
        )
        self._register_cancel_event(run.id)
        return run.id

    def _run_provider_loop(
        self,
        *,
        thread_id: str,
        turn_id: str,
        run_id: str,
        step_state: dict[str, int],
        fq_model_key: str | None,
        provider: AgentProvider | None,
    ) -> ThreadSnapshot | StepBudgetPause:
        while step_state["used_steps"] < step_state["granted_steps"]:
            step_state["used_steps"] += 1
            self._raise_if_cancelled(run_id)
            snapshot = self._conversation_store.get_thread_snapshot(thread_id)
            provider_messages = self._provider_messages_for_request(snapshot)
            dataset_ids = self._dataset_ids_for_thread(snapshot)
            provider_request = self._create_provider_request(
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                provider=provider,
                fq_model_key=fq_model_key,
                request_kind=AgentProviderRequestKind.PRIMARY,
                input_message_ids=self._provider_input_message_ids(provider_messages),
            )
            tool_specs = self._tool_specs_for_context(snapshot=snapshot, dataset_ids=dataset_ids)
            available_tool_names = {tool.name for tool in tool_specs}
            provider_span_attributes = ai_observability.provider_request_span_attributes(
                provider_request,
                provider_messages=provider_messages,
                tool_specs=tool_specs,
                loop_step_index=step_state["used_steps"],
                stream=False,
            )
            retry_events: list[dict[str, Any]] = []
            try:
                with start_span("agent.provider_request", provider_span_attributes) as provider_span:
                    provider_response = self._complete_provider_target(
                        provider=provider,
                        fq_model_key=fq_model_key,
                        messages=provider_messages,
                        tools=tool_specs,
                        retry_events=retry_events,
                    )
                    self._raise_if_cancelled(run_id)
                    set_span_attributes(provider_span, ai_observability.provider_response_shape_attributes(provider_response))
                    invalid_tool_attributes = ai_observability.invalid_tool_call_attributes(
                        provider_response.tool_calls,
                        available_tool_names,
                    )
                    if invalid_tool_attributes:
                        set_span_attributes(provider_span, invalid_tool_attributes)
                        set_span_attributes(provider_span, {"xenix.ai.provider_request.status": AgentProviderRequestStatus.FAILED.value})
                    self._validate_provider_tool_calls(provider_response.tool_calls, available_tool_names)
                    set_span_attributes(
                        provider_span,
                        ai_observability.provider_usage_payload_attributes(
                            provider_request,
                            provider_response.usage_payload,
                        ),
                    )
                    set_span_attributes(provider_span, {"xenix.ai.provider_request.status": AgentProviderRequestStatus.SUCCEEDED.value})
            except AgentRunCancelled:
                self._complete_provider_request(
                    provider_request,
                    status=AgentProviderRequestStatus.CANCELLED,
                    usage_payload=self._provider_request_usage_payload(None, retry_events),
                )
                raise
            except Exception:
                self._complete_provider_request(
                    provider_request,
                    status=AgentProviderRequestStatus.FAILED,
                    usage_payload=self._provider_request_usage_payload(None, retry_events),
                )
                raise
            try:
                self._raise_if_cancelled(run_id)
            except AgentRunCancelled:
                self._complete_provider_request(
                    provider_request,
                    status=AgentProviderRequestStatus.CANCELLED,
                    usage_payload=self._provider_request_usage_payload(None, retry_events),
                )
                raise
            provider_output_message_ids: list[str] = []
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
                provider_output_message_ids.append(assistant_message.id)

            persisted_tool_calls = []
            for tool_call in provider_response.tool_calls:
                self._raise_if_cancelled(run_id)
                arguments = self._tool_call_arguments(tool_call.tool_name, tool_call.arguments)
                request_message, persisted_tool_call = self._conversation_store.create_tool_call(
                    CreateToolCallInput(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        tool_name=tool_call.tool_name,
                        arguments_payload=arguments,
                        provider_payload=self._tool_call_provider_payload(
                            tool_call,
                            provider_response,
                        ),
                    )
                )
                provider_output_message_ids.append(request_message.id)
                persisted_tool_calls.append((tool_call, arguments, persisted_tool_call))

            self._complete_provider_request(
                provider_request,
                status=AgentProviderRequestStatus.SUCCEEDED,
                output_message_ids=provider_output_message_ids,
                usage_payload=self._provider_request_usage_payload(
                    provider_response.usage_payload,
                    retry_events,
                ),
            )

            if not provider_response.tool_calls:
                guard_action = self._guard_turn_completion(
                    thread_id=thread_id,
                    turn_id=turn_id,
                    provider_response=provider_response,
                    source_message_ids=provider_output_message_ids,
                    run_id=run_id,
                )
                if guard_action is not None:
                    continue
                self._conversation_store.end_turn(thread_id, turn_id)
                return self._conversation_store.get_thread_snapshot(thread_id)

            for tool_call, arguments, persisted_tool_call in persisted_tool_calls:
                self._raise_if_cancelled(run_id)
                tool_started_at = perf_counter()
                tool_error: BaseException | None = None
                try:
                    with start_span(
                        "agent.tool_call",
                        self._tool_call_attributes(
                            persisted_tool_call,
                            provider_request=provider_request,
                            loop_step_index=step_state["used_steps"],
                        ),
                    ):
                        result = self._execute_tool_call(
                            tool_name=tool_call.tool_name,
                            arguments=arguments,
                            thread_id=thread_id,
                            turn_id=turn_id,
                            tool_call_id=persisted_tool_call.id,
                            dataset_ids=dataset_ids,
                            run_id=run_id,
                        )
                    status = AgentToolCallStatus.SUCCEEDED
                    error_summary = None
                except Exception as exc:
                    tool_error = exc
                    if self._is_cancel_requested(run_id):
                        result = self._tool_cancelled_result()
                        status = AgentToolCallStatus.CANCELLED
                        error_summary = "Agent run was cancelled."
                    else:
                        result = self._tool_error_result(exc)
                        status = AgentToolCallStatus.FAILED
                        error_summary = str(exc)

                _result_message, _completed = self._conversation_store.complete_tool_call(
                    CompleteToolCallInput(
                        tool_call_id=persisted_tool_call.id,
                        status=status,
                        result_payload=result.payload,
                        error_summary=error_summary,
                        provider_payload={"tool_call_id": tool_call.provider_call_id},
                    )
                )
                self._record_tool_call(
                    _completed,
                    (perf_counter() - tool_started_at) * 1000,
                    tool_error,
                )
                if status is AgentToolCallStatus.CANCELLED:
                    raise AgentRunCancelled()
        return self._pause_for_step_confirmation(
            thread_id=thread_id,
            turn_id=turn_id,
            run_id=run_id,
            step_state=step_state,
        )

    def _run_provider_loop_stream(
        self,
        *,
        thread_id: str,
        turn_id: str,
        run_id: str,
        step_state: dict[str, int],
        fq_model_key: str | None,
        provider: AgentProvider | None,
    ):
        while step_state["used_steps"] < step_state["granted_steps"]:
            step_state["used_steps"] += 1
            self._raise_if_cancelled(run_id)
            yield self._activity_event(
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                sequence_index=step_state["used_steps"],
            )
            snapshot = self._conversation_store.get_thread_snapshot(thread_id)
            provider_messages = self._provider_messages_for_request(snapshot)
            dataset_ids = self._dataset_ids_for_thread(snapshot)
            provider_request = self._create_provider_request(
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                provider=provider,
                fq_model_key=fq_model_key,
                request_kind=AgentProviderRequestKind.PRIMARY,
                input_message_ids=self._provider_input_message_ids(provider_messages),
            )
            provider_response: ProviderResponse | None = None
            assistant_message: AgentMessageRow | None = None
            assistant_text = ""
            provider_output_message_ids: list[str] = []
            tool_specs = self._tool_specs_for_context(snapshot=snapshot, dataset_ids=dataset_ids)
            available_tool_names = {tool.name for tool in tool_specs}
            provider_span_attributes = ai_observability.provider_request_span_attributes(
                provider_request,
                provider_messages=provider_messages,
                tool_specs=tool_specs,
                loop_step_index=step_state["used_steps"],
                stream=True,
            )
            retry_events: list[dict[str, Any]] = []
            try:
                provider_started_at = perf_counter()
                first_event_ms: float | None = None
                first_text_ms: float | None = None
                with start_span("agent.provider_request", provider_span_attributes) as provider_span:
                    for stream_event in self._provider_stream(
                        provider=provider,
                        fq_model_key=fq_model_key,
                        messages=provider_messages,
                        tools=tool_specs,
                    ):
                        if isinstance(stream_event, LLMRetryEvent):
                            retry_events.append(stream_event.to_payload())
                            yield self._llm_connection_event(
                                provider_request=provider_request,
                                retry_events=retry_events,
                            )
                            continue
                        elapsed_ms = (perf_counter() - provider_started_at) * 1000
                        if first_event_ms is None:
                            first_event_ms = elapsed_ms
                        self._raise_if_cancelled(run_id)
                        if stream_event.delta_text:
                            if first_text_ms is None:
                                first_text_ms = elapsed_ms
                            assistant_text += stream_event.delta_text
                            assistant_blocks = [{"type": "markdown", "text": assistant_text}]
                            if assistant_message is None:
                                assistant_message = self._conversation_store.append_message(
                                    AppendAgentMessageInput(
                                        thread_id=thread_id,
                                        turn_id=turn_id,
                                        kind=AgentMessageKind.ASSISTANT,
                                        ui_author=AgentMessageAuthor.ASSISTANT,
                                        content_blocks=assistant_blocks,
                                        status=AgentMessageStatus.IN_PROGRESS,
                                    )
                                )
                                yield self._message_event("message_created", assistant_message, run_id)
                            else:
                                assistant_message = self._conversation_store.update_message(
                                    UpdateAgentMessageInput(
                                        message_id=assistant_message.id,
                                        content_blocks=assistant_blocks,
                                        status=AgentMessageStatus.IN_PROGRESS,
                                    )
                                )
                                yield self._message_event("message_updated", assistant_message, run_id)
                        if stream_event.response is not None:
                            provider_response = stream_event.response
                    set_span_attributes(
                        provider_span,
                        ai_observability.streaming_timing_attributes(
                            first_event_ms=first_event_ms,
                            first_text_ms=first_text_ms,
                        ),
                    )
                    if provider_response is not None:
                        set_span_attributes(provider_span, ai_observability.provider_response_shape_attributes(provider_response))
                        invalid_tool_attributes = ai_observability.invalid_tool_call_attributes(
                            provider_response.tool_calls,
                            available_tool_names,
                        )
                        if invalid_tool_attributes:
                            set_span_attributes(provider_span, invalid_tool_attributes)
                            set_span_attributes(provider_span, {"xenix.ai.provider_request.status": AgentProviderRequestStatus.FAILED.value})
                        self._validate_provider_tool_calls(provider_response.tool_calls, available_tool_names)
                        set_span_attributes(
                            provider_span,
                            ai_observability.provider_usage_payload_attributes(
                                provider_request,
                                provider_response.usage_payload,
                            ),
                        )
                        set_span_attributes(provider_span, {"xenix.ai.provider_request.status": AgentProviderRequestStatus.SUCCEEDED.value})
                    if retry_events:
                        yield self._llm_connection_event(
                            provider_request=provider_request,
                            retry_events=retry_events,
                            status=ChatbotEventStatus.COMPLETED,
                        )
                self._raise_if_cancelled(run_id)
            except AgentRunCancelled:
                self._complete_provider_request(
                    provider_request,
                    status=AgentProviderRequestStatus.CANCELLED,
                    usage_payload=self._provider_request_usage_payload(None, retry_events),
                )
                if retry_events:
                    yield self._llm_connection_event(
                        provider_request=provider_request,
                        retry_events=retry_events,
                        status=ChatbotEventStatus.CANCELLED,
                    )
                if assistant_message is not None:
                    assistant_message = self._conversation_store.update_message(
                        UpdateAgentMessageInput(
                            message_id=assistant_message.id,
                            status=AgentMessageStatus.CANCELLED,
                        )
                    )
                    yield self._message_event("message_finalized", assistant_message, run_id)
                raise
            except Exception:
                self._complete_provider_request(
                    provider_request,
                    status=AgentProviderRequestStatus.FAILED,
                    usage_payload=self._provider_request_usage_payload(None, retry_events),
                )
                if retry_events:
                    yield self._llm_connection_event(
                        provider_request=provider_request,
                        retry_events=retry_events,
                        status=ChatbotEventStatus.FAILED,
                    )
                if assistant_message is not None:
                    assistant_message = self._conversation_store.update_message(
                        UpdateAgentMessageInput(
                            message_id=assistant_message.id,
                            status=AgentMessageStatus.FAILED,
                        )
                    )
                    yield self._message_event("message_finalized", assistant_message, run_id)
                raise

            if provider_response is None:
                if assistant_message is not None:
                    assistant_message = self._conversation_store.update_message(
                        UpdateAgentMessageInput(
                            message_id=assistant_message.id,
                            status=AgentMessageStatus.FAILED,
                        )
                    )
                    yield self._message_event("message_finalized", assistant_message, run_id)
                self._complete_provider_request(
                    provider_request,
                    status=AgentProviderRequestStatus.FAILED,
                )
                raise ValidationError("Provider stream ended without a completed response.")

            final_assistant_blocks = provider_response.assistant_content_blocks
            if assistant_message is not None and not final_assistant_blocks:
                final_assistant_blocks = list(assistant_message.content_blocks)
            if final_assistant_blocks:
                if assistant_message is None:
                    assistant_message = self._conversation_store.append_message(
                        AppendAgentMessageInput(
                            thread_id=thread_id,
                            turn_id=turn_id,
                            kind=AgentMessageKind.ASSISTANT,
                            ui_author=AgentMessageAuthor.ASSISTANT,
                            content_blocks=final_assistant_blocks,
                            provider_payload=provider_response.raw_payload,
                        )
                    )
                    yield self._message_event("message_created", assistant_message, run_id)
                else:
                    assistant_message = self._conversation_store.update_message(
                        UpdateAgentMessageInput(
                            message_id=assistant_message.id,
                            content_blocks=final_assistant_blocks,
                            provider_payload=provider_response.raw_payload,
                            status=AgentMessageStatus.COMPLETED,
                        )
                    )
                    yield self._message_event("message_finalized", assistant_message, run_id)
                if assistant_message.id not in provider_output_message_ids:
                    provider_output_message_ids.append(assistant_message.id)

            persisted_tool_calls = []
            for tool_call in provider_response.tool_calls:
                self._raise_if_cancelled(run_id)
                arguments = self._tool_call_arguments(tool_call.tool_name, tool_call.arguments)
                request_message, persisted_tool_call = self._conversation_store.create_tool_call(
                    CreateToolCallInput(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        tool_name=tool_call.tool_name,
                        arguments_payload=arguments,
                        provider_payload=self._tool_call_provider_payload(
                            tool_call,
                            provider_response,
                        ),
                    )
                )
                provider_output_message_ids.append(request_message.id)
                persisted_tool_calls.append((tool_call, arguments, request_message, persisted_tool_call))
                tool_event = self._tool_event(
                    "message_created",
                    request_message,
                    run_id,
                    tool_call=persisted_tool_call,
                    request_message=request_message,
                )
                yield tool_event

            self._complete_provider_request(
                provider_request,
                status=AgentProviderRequestStatus.SUCCEEDED,
                output_message_ids=provider_output_message_ids,
                usage_payload=self._provider_request_usage_payload(
                    provider_response.usage_payload,
                    retry_events,
                ),
            )

            if not provider_response.tool_calls:
                guard_action = self._guard_turn_completion(
                    thread_id=thread_id,
                    turn_id=turn_id,
                    provider_response=provider_response,
                    source_message_ids=provider_output_message_ids,
                    run_id=run_id,
                )
                if guard_action is not None:
                    yield self._message_event("message_created", guard_action, run_id)
                    continue
                self._conversation_store.end_turn(thread_id, turn_id)
                return self._conversation_store.get_thread_snapshot(thread_id)

            for tool_call, arguments, request_message, persisted_tool_call in persisted_tool_calls:
                self._raise_if_cancelled(run_id)
                tool_started_at = perf_counter()
                tool_error: BaseException | None = None
                try:
                    with start_span(
                        "agent.tool_call",
                        self._tool_call_attributes(
                            persisted_tool_call,
                            provider_request=provider_request,
                            loop_step_index=step_state["used_steps"],
                        ),
                    ):
                        result = self._execute_tool_call(
                            tool_name=tool_call.tool_name,
                            arguments=arguments,
                            thread_id=thread_id,
                            turn_id=turn_id,
                            tool_call_id=persisted_tool_call.id,
                            dataset_ids=dataset_ids,
                            run_id=run_id,
                        )
                    status = AgentToolCallStatus.SUCCEEDED
                    error_summary = None
                except Exception as exc:
                    tool_error = exc
                    if self._is_cancel_requested(run_id):
                        result = self._tool_cancelled_result()
                        status = AgentToolCallStatus.CANCELLED
                        error_summary = "Agent run was cancelled."
                    else:
                        result = self._tool_error_result(exc)
                        status = AgentToolCallStatus.FAILED
                        error_summary = str(exc)

                result_message, completed_tool_call = self._conversation_store.complete_tool_call(
                    CompleteToolCallInput(
                        tool_call_id=persisted_tool_call.id,
                        status=status,
                        result_payload=result.payload,
                        error_summary=error_summary,
                        provider_payload={"tool_call_id": tool_call.provider_call_id},
                    )
                )
                self._record_tool_call(
                    completed_tool_call,
                    (perf_counter() - tool_started_at) * 1000,
                    tool_error,
                )
                yield self._tool_event(
                    "message_created",
                    result_message,
                    run_id,
                    tool_call=completed_tool_call,
                    request_message=request_message,
                    result_message=result_message,
                )
                if status is AgentToolCallStatus.CANCELLED:
                    raise AgentRunCancelled()
        pause = self._pause_for_step_confirmation(
            thread_id=thread_id,
            turn_id=turn_id,
            run_id=run_id,
            step_state=step_state,
        )
        yield self._message_event("message_created", pause.message, run_id)
        return pause

    def _initial_step_state(self) -> dict[str, int]:
        return {
            "used_steps": 0,
            "granted_steps": self._initial_step_limit,
            "extension_step_limit": self._step_extension_limit,
            "max_total_steps": self._max_total_steps,
        }

    def _create_provider_request(
        self,
        *,
        thread_id: str,
        turn_id: str,
        run_id: str | None,
        provider: AgentProvider | None,
        fq_model_key: str | None = None,
        request_kind: AgentProviderRequestKind,
        input_message_ids: list[str],
    ) -> AgentProviderRequestRow:
        return self._conversation_store.create_provider_request(
            CreateProviderRequestInput(
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                provider_name=self._target_provider_name(provider=provider, fq_model_key=fq_model_key),
                model=self._target_provider_model(provider=provider, fq_model_key=fq_model_key),
                request_kind=request_kind,
                input_message_ids=input_message_ids,
            )
        )

    def _complete_provider_request(
        self,
        provider_request: AgentProviderRequestRow,
        *,
        status: AgentProviderRequestStatus,
        output_message_ids: list[str] | None = None,
        usage_payload: dict[str, Any] | None = None,
    ) -> AgentProviderRequestRow:
        updated = self._conversation_store.complete_provider_request(
            CompleteProviderRequestInput(
                provider_request_id=provider_request.id,
                status=status,
                output_message_ids=list(output_message_ids or []),
                usage_payload=usage_payload,
            )
        )
        self._record_provider_request(updated)
        return updated

    def _provider_request_attributes(self, provider_request: AgentProviderRequestRow) -> dict[str, Any]:
        return ai_observability.provider_metric_attributes(provider_request)

    def _tool_call_attributes(
        self,
        tool_call: AgentToolCallRow,
        *,
        provider_request: AgentProviderRequestRow | None = None,
        loop_step_index: int | None = None,
    ) -> dict[str, Any]:
        return ai_observability.tool_call_span_attributes(
            tool_call,
            provider_request=provider_request,
            loop_step_index=loop_step_index,
        )

    def _record_provider_request(self, provider_request: AgentProviderRequestRow) -> None:
        attributes = self._provider_request_attributes(provider_request)
        attributes["status"] = provider_request.status.value
        record_counter("xenix.agent.provider_request.count", attributes=attributes)
        if provider_request.completed_at is not None:
            record_histogram(
                "xenix.agent.provider_request.duration",
                max(0.0, (provider_request.completed_at - provider_request.created_at).total_seconds() * 1000),
                attributes=attributes,
                unit="ms",
            )
        for _token_type, token_count, token_attributes in ai_observability.token_metric_measurements(provider_request):
            token_attributes["status"] = provider_request.status.value
            record_histogram(
                "gen_ai.client.token.usage",
                token_count,
                attributes=token_attributes,
                unit="{token}",
            )

    def _record_tool_call(self, tool_call: AgentToolCallRow, duration_ms: float, error: BaseException | None = None) -> None:
        attributes = ai_observability.tool_call_metric_attributes(tool_call)
        attributes["status"] = tool_call.status.value
        if error is not None:
            attributes["error.type"] = error.__class__.__name__
        record_counter("xenix.agent.tool_call.count", attributes=attributes)
        record_histogram("xenix.agent.tool_call.duration", duration_ms, attributes=attributes, unit="ms")

    def _record_agent_turn(self, status: str, error: BaseException | None = None) -> None:
        attributes: dict[str, Any] = {"status": status}
        if error is not None:
            attributes["error.type"] = error.__class__.__name__
        record_counter("xenix.agent.turn.count", attributes=attributes)

    def _provider_model(self, provider: AgentProvider) -> str | None:
        model = getattr(provider, "model", None)
        if isinstance(model, str) and model.strip():
            return model
        model = getattr(provider, "_model", None)
        if isinstance(model, str) and model.strip():
            return model
        return None

    def _provider_name(self, provider: AgentProvider) -> str:
        provider_key = getattr(provider, "provider_key", None)
        if isinstance(provider_key, str) and provider_key.strip():
            return provider_key.strip()
        provider_key = getattr(provider, "_provider_key", None)
        if isinstance(provider_key, str) and provider_key.strip():
            return provider_key.strip()
        return type(provider).__name__

    def _target_provider_model(self, *, provider: AgentProvider | None, fq_model_key: str | None) -> str | None:
        if self._llm_service is not None:
            return self._llm_service.request_metadata(fq_model_key).model
        if provider is None:
            return None
        return self._provider_model(provider)

    def _target_provider_name(self, *, provider: AgentProvider | None, fq_model_key: str | None) -> str:
        if self._llm_service is not None:
            return self._llm_service.request_metadata(fq_model_key).provider_name
        if provider is None:
            return "unknown"
        return self._provider_name(provider)

    def _resolve_fq_model_key(
        self,
        requested_fq_model_key: str | None,
        thread_fq_model_key: str | None,
    ) -> str | None:
        selected = (requested_fq_model_key or thread_fq_model_key or "").strip()
        if selected:
            return self._validate_fq_model_key(selected)
        if self._llm_service is None:
            return None
        return self._llm_service.default_fq_model_key()

    def _validate_fq_model_key(self, fq_model_key: str) -> str:
        if self._llm_service is None:
            return fq_model_key.strip()
        return self._llm_service.validate_fq_model_key(fq_model_key)

    def _provider_for_fq_model_key(self, fq_model_key: str | None) -> AgentProvider:
        if self._provider is None:
            raise ValidationError("Agent provider is not configured.")
        return self._provider

    def _provider_for_run(self, run) -> AgentProvider | None:
        if self._llm_service is not None:
            return None
        return self._provider_for_fq_model_key(self._fq_model_key_from_run_payload(run.usage_payload))

    def _fq_model_key_from_run_payload(self, payload: dict[str, Any] | None) -> str | None:
        value = (payload or {}).get("fq_model_key")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _provider_input_message_ids(self, messages) -> list[str]:
        ids: list[str] = []
        for message in messages:
            source_id = getattr(message, "source_message_id", None)
            if isinstance(source_id, str) and source_id:
                ids.append(source_id)
        return ids

    def _usage_payload(
        self,
        step_state: dict[str, int],
        *,
        fq_model_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"step_budget": dict(step_state)}
        if fq_model_key:
            payload["fq_model_key"] = fq_model_key
        return payload

    def _step_state_from_payload(self, payload: dict[str, Any] | None) -> dict[str, int]:
        raw_state = (payload or {}).get("step_budget")
        if not isinstance(raw_state, dict):
            return self._initial_step_state()
        state = self._initial_step_state()
        for key in state:
            value = raw_state.get(key)
            if isinstance(value, int):
                state[key] = value
        state["granted_steps"] = max(state["used_steps"], state["granted_steps"])
        state["max_total_steps"] = max(self._initial_step_limit, state["max_total_steps"])
        return state

    def _requested_step_extension(self, requested_steps: int | None, step_state: dict[str, int]) -> int:
        requested = requested_steps if requested_steps is not None else step_state["extension_step_limit"]
        requested = max(1, requested)
        remaining = step_state["max_total_steps"] - step_state["granted_steps"]
        if remaining <= 0:
            raise ValidationError("The maximum step budget has already been reached.")
        return min(requested, step_state["extension_step_limit"], remaining)

    def _pause_for_step_confirmation(
        self,
        *,
        thread_id: str,
        turn_id: str,
        run_id: str,
        step_state: dict[str, int],
    ) -> StepBudgetPause:
        remaining = step_state["max_total_steps"] - step_state["granted_steps"]
        if remaining <= 0:
            raise ValidationError("Provider exceeded the maximum total tool-calling steps.")
        suggested_steps = min(step_state["extension_step_limit"], remaining)
        message = self._conversation_store.append_message(
            AppendAgentMessageInput(
                thread_id=thread_id,
                turn_id=turn_id,
                kind=AgentMessageKind.SYSTEM,
                ui_author=AgentMessageAuthor.SYSTEM,
                content_blocks=[
                    {
                        "type": "step_confirmation",
                        "text": (
                            f"The current step budget is exhausted after {step_state['used_steps']} steps. "
                            f"Ask the user whether to continue with up to {suggested_steps} more steps."
                        ),
                        "used_steps": step_state["used_steps"],
                        "suggested_steps": suggested_steps,
                        "max_total_steps": step_state["max_total_steps"],
                    }
                ],
            )
        )
        run = self._conversation_store.get_run(run_id)
        self._conversation_store.pause_run_for_confirmation(
            run_id,
            self._usage_payload(
                step_state,
                fq_model_key=self._fq_model_key_from_run_payload(run.usage_payload),
            ),
        )
        snapshot = self._conversation_store.get_thread_snapshot(thread_id)
        return StepBudgetPause(
            thread_id=thread_id,
            turn_id=turn_id,
            run_id=run_id,
            message=message,
            used_steps=step_state["used_steps"],
            suggested_steps=suggested_steps,
            max_total_steps=step_state["max_total_steps"],
            snapshot=snapshot,
        )

    def _step_confirmation_event(self, pause: StepBudgetPause) -> AgentHarnessStreamEvent:
        return AgentHarnessStreamEvent(
            kind="step_confirmation_required",
            thread_id=pause.thread_id,
            turn_id=pause.turn_id,
            run_id=pause.run_id,
            snapshot=pause.snapshot,
            chatbot_events=self.project_chatbot_events(pause.snapshot),
            used_steps=pause.used_steps,
            suggested_steps=pause.suggested_steps,
            max_total_steps=pause.max_total_steps,
        )

    def _message_event(self, kind: str, message: AgentMessageRow, run_id: str) -> AgentHarnessStreamEvent:
        chatbot_event = None
        if message.kind in {AgentMessageKind.USER, AgentMessageKind.ASSISTANT}:
            chatbot_event = project_text_message_event(message)
        return AgentHarnessStreamEvent(
            kind=kind,
            thread_id=message.thread_id,
            turn_id=message.turn_id,
            run_id=run_id,
            message_id=message.id,
            message=message,
            chatbot_event=chatbot_event,
        )

    def _activity_event(
        self,
        *,
        thread_id: str,
        turn_id: str,
        run_id: str,
        sequence_index: int,
    ) -> AgentHarnessStreamEvent:
        return AgentHarnessStreamEvent(
            kind="chatbot_event",
            thread_id=thread_id,
            turn_id=turn_id,
            run_id=run_id,
            chatbot_event=build_activity_chatbot_event(
                run_id=run_id,
                turn_id=turn_id,
                sequence_index=sequence_index,
            ),
        )

    def _tool_event(
        self,
        kind: str,
        message: AgentMessageRow,
        run_id: str,
        *,
        tool_call,
        request_message: AgentMessageRow,
        result_message: AgentMessageRow | None = None,
    ) -> AgentHarnessStreamEvent:
        if is_agent_skill_tool(tool_call.tool_name) and not should_project_agent_skill_tools():
            return AgentHarnessStreamEvent(
                kind=kind,
                thread_id=message.thread_id,
                turn_id=message.turn_id,
                run_id=run_id,
                message_id=message.id,
                message=message,
            )
        return AgentHarnessStreamEvent(
            kind=kind,
            thread_id=message.thread_id,
            turn_id=message.turn_id,
            run_id=run_id,
            message_id=message.id,
            message=message,
            chatbot_event=project_tool_chatbot_event(
                tool_call,
                request_message=request_message,
                result_message=result_message,
                tool_presentation_lookup=self._tool_presentation,
            ),
        )

    def _guard_turn_completion(
        self,
        *,
        thread_id: str,
        turn_id: str,
        provider_response: ProviderResponse,
        source_message_ids: list[str],
        run_id: str | None,
    ) -> AgentMessageRow | None:
        guard_fq_model_key = self._turn_completion_guard_fq_model_key()
        if self._turn_completion_guard is None and guard_fq_model_key is None:
            return None

        last_assistant_text = _assistant_text(provider_response.assistant_content_blocks)
        if not last_assistant_text:
            return None

        guard_rows = self._conversation_store.list_turn_completion_guards(turn_id)
        continue_attempts = [
            row
            for row in guard_rows
            if isinstance(row.output, dict) and row.output.get("verdict") == TurnCompletionGuardVerdict.CONTINUE.value
        ]
        if len(continue_attempts) >= 2:
            return None
        attempt_index = len(guard_rows)

        provider_request = self._create_provider_request(
            thread_id=thread_id,
            turn_id=turn_id,
            run_id=run_id,
            provider=self._turn_completion_guard.provider if self._turn_completion_guard is not None else None,
            fq_model_key=guard_fq_model_key,
            request_kind=AgentProviderRequestKind.GUARD,
            input_message_ids=list(source_message_ids),
        )
        result = self._evaluate_turn_completion_guard(
            last_assistant_text,
            guard_fq_model_key=guard_fq_model_key,
        )
        guard_action: AgentMessageRow | None = None
        if result.verdict is TurnCompletionGuardVerdict.CONTINUE:
            guard_action = self._conversation_store.append_message(
                AppendAgentMessageInput(
                    thread_id=thread_id,
                    turn_id=turn_id,
                    kind=AgentMessageKind.SYSTEM,
                    ui_author=AgentMessageAuthor.SYSTEM,
                    content_blocks=[{"type": "markdown", "text": TURN_COMPLETION_GUARD_REMINDER}],
                )
            )
        self._complete_provider_request(
            provider_request,
            status=(
                AgentProviderRequestStatus.FAILED
                if result.provider_failed
                else AgentProviderRequestStatus.SUCCEEDED
            ),
            output_message_ids=[guard_action.id] if guard_action is not None else [],
            usage_payload=self._provider_request_usage_payload(
                result.usage_payload,
                result.retry_events,
            ),
        )
        self._conversation_store.create_turn_completion_guard(
            CreateTurnCompletionGuardInput(
                turn_id=turn_id,
                attempt_index=attempt_index,
                input={"last_assistant_text": last_assistant_text},
                output={
                    "verdict": result.verdict.value,
                    "reason": result.reason,
                },
            )
        )
        return guard_action

    def _turn_completion_guard_fq_model_key(self) -> str | None:
        if self._llm_service is None:
            return None
        return self._llm_service.turn_completion_guard_fq_model_key()

    def _evaluate_turn_completion_guard(
        self,
        last_assistant_text: str,
        *,
        guard_fq_model_key: str | None,
    ) -> TurnCompletionGuardResult:
        if self._turn_completion_guard is not None:
            return self._turn_completion_guard.evaluate(last_assistant_text)
        if self._llm_service is None or guard_fq_model_key is None:
            return TurnCompletionGuardResult(
                verdict=TurnCompletionGuardVerdict.COMPLETE,
                reason="Turn completion guard is not configured.",
            )
        retry_events: list[dict[str, Any]] = []
        try:
            response = self._llm_service.complete(
                fq_model_key=guard_fq_model_key,
                messages=[
                    ProviderMessage(role="system", content=_GUARD_SYSTEM_PROMPT),
                    ProviderMessage(
                        role="user",
                        content=json.dumps(
                            {"last_assistant_text": last_assistant_text},
                            ensure_ascii=False,
                        ),
                    ),
                ],
                tools=[],
                retry_callback=lambda event: retry_events.append(event.to_payload()),
            )
            result = _parse_guard_output(_assistant_text(response.assistant_content_blocks))
            result.usage_payload = response.usage_payload
            result.retry_events = retry_events
            return result
        except Exception as exc:
            return TurnCompletionGuardResult(
                verdict=TurnCompletionGuardVerdict.COMPLETE,
                reason=f"Guard failed closed: {exc}",
                retry_events=retry_events,
                provider_failed=True,
            )

    def _tool_specs_for_context(self, *, snapshot: ThreadSnapshot, dataset_ids: list[str]) -> list[AgentToolSpec]:
        context = _ToolAvailabilityContext(
            dataset_ids=tuple(dataset_ids),
            has_dataset=bool(dataset_ids),
            has_selection=self._snapshot_has_payload_key(snapshot, "binding_id"),
            has_trained_model=self._snapshot_has_trained_model(snapshot),
        )
        specs = [
            spec
            for spec in self._tool_registry.list_specs()
            if self._tool_available_for_context(spec.name, context)
        ]
        skill_spec = self._skill_activation_tool_spec(snapshot)
        if skill_spec is not None:
            specs.append(skill_spec)
        specs.extend(self._skill_resource_tool_specs(snapshot))
        return specs

    def _skill_activation_tool_spec(self, snapshot: ThreadSnapshot) -> AgentToolSpec | None:
        if self._skill_catalog is None:
            return None
        return self._skill_catalog.activation_tool_spec(
            activated_skill_names=self._activated_skill_names(snapshot),
        )

    def _skill_resource_tool_specs(self, snapshot: ThreadSnapshot) -> list[AgentToolSpec]:
        if self._skill_catalog is None:
            return []
        return self._skill_catalog.resource_tool_specs(
            activated_skill_names=self._activated_skill_names(snapshot),
        )

    def _provider_messages_for_request(self, snapshot: ThreadSnapshot) -> list[ProviderMessage]:
        provider_messages = snapshot.provider_messages()
        if self._skill_catalog is None:
            return provider_messages
        catalog_message = self._skill_catalog.catalog_provider_message(
            activated_skill_names=self._activated_skill_names(snapshot),
        )
        if catalog_message is None:
            return provider_messages
        insertion_index = 0
        for index, message in enumerate(provider_messages):
            if message.role == "system":
                insertion_index = index + 1
                break
        return [*provider_messages[:insertion_index], catalog_message, *provider_messages[insertion_index:]]

    def _activated_skill_names(self, snapshot: ThreadSnapshot) -> set[str]:
        activated: set[str] = set()
        for payload in self._snapshot_tool_payloads(snapshot):
            skill_name = payload.get("skill_name")
            if isinstance(skill_name, str) and skill_name.strip():
                activated.add(skill_name.strip())
        return activated

    def _execute_tool_call(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        thread_id: str,
        turn_id: str,
        tool_call_id: str,
        dataset_ids: list[str],
        run_id: str,
    ):
        if is_agent_skill_tool(tool_name):
            return self._execute_agent_skill_tool(tool_name, arguments)
        return self._tool_registry.execute(
            tool_name,
            arguments,
            _tool_execution_context(
                thread_id=thread_id,
                turn_id=turn_id,
                tool_call_id=tool_call_id,
                dataset_ids=dataset_ids,
                cancel_requested=lambda run_id=run_id: self._is_cancel_requested(run_id),
            ),
        )

    def _execute_agent_skill_tool(self, tool_name: str, arguments: dict[str, Any]):
        if tool_name == AGENT_SKILL_ACTIVATE_TOOL_NAME:
            return self._execute_skill_activation(arguments)
        if tool_name == AGENT_SKILL_READ_REFERENCE_TOOL_NAME:
            return self._execute_skill_resource_read(tool_name, arguments, resource_kind="reference")
        if tool_name == AGENT_SKILL_READ_ASSET_TOOL_NAME:
            return self._execute_skill_resource_read(tool_name, arguments, resource_kind="asset")
        raise ValidationError(f"Unknown Agent Skill tool: {tool_name}")

    def _execute_skill_activation(self, arguments: dict[str, Any]):
        if self._skill_catalog is None:
            raise ValidationError("Agent Skill catalog is not configured.")
        from .tools import ToolExecutionResult

        skill_name = str(arguments.get("name") or "").strip()
        if not skill_name:
            raise ValidationError("Agent Skill activation requires a skill name.")
        payload = self._skill_catalog.activate(skill_name)
        return ToolExecutionResult(
            payload=payload,
        )

    def _execute_skill_resource_read(self, tool_name: str, arguments: dict[str, Any], *, resource_kind: str):
        if self._skill_catalog is None:
            raise ValidationError("Agent Skill catalog is not configured.")
        from .tools import ToolExecutionResult

        skill_name = str(arguments.get("skill_name") or "").strip()
        path = str(arguments.get("path") or "").strip()
        if not skill_name:
            raise ValidationError("Agent Skill resource read requires a skill name.")
        if not path:
            raise ValidationError("Agent Skill resource read requires a resource path.")
        if tool_name == AGENT_SKILL_READ_REFERENCE_TOOL_NAME:
            payload = self._skill_catalog.read_reference(skill_name=skill_name, path=path)
        elif tool_name == AGENT_SKILL_READ_ASSET_TOOL_NAME:
            payload = self._skill_catalog.read_asset(skill_name=skill_name, path=path)
        else:
            raise ValidationError(f"Unknown Agent Skill resource tool: {tool_name}")
        return ToolExecutionResult(
            payload=payload,
        )

    def _tool_available_for_context(self, tool_name: str, context: _ToolAvailabilityContext) -> bool:
        if tool_name == "data.integrate":
            return len(context.dataset_ids) >= 2
        if tool_name.startswith("data."):
            return context.has_dataset
        if tool_name.startswith("analysis."):
            return context.has_dataset
        if tool_name in {"model.train", "model.hyper_train"}:
            return context.has_selection
        if tool_name == "model.apply":
            return context.has_trained_model
        return True

    def _dataset_ids_for_thread(self, snapshot: ThreadSnapshot) -> list[str]:
        dataset_ids: list[str] = []
        seen: set[str] = set()
        for message in snapshot.messages:
            for block in message.content_blocks:
                if block.get("type") != "dataset":
                    continue
                dataset_id = str(block.get("dataset_id") or "").strip()
                if dataset_id and dataset_id not in seen:
                    dataset_ids.append(dataset_id)
                    seen.add(dataset_id)
        for payload in self._snapshot_tool_payloads(snapshot):
            value = payload.get("dataset_id")
            if isinstance(value, str) and value.strip() and value not in seen:
                dataset_ids.append(value)
                seen.add(value)
            values = payload.get("input_dataset_ids")
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, str) and item.strip() and item not in seen:
                        dataset_ids.append(item)
                        seen.add(item)
        return dataset_ids

    def _validate_provider_tool_calls(
        self,
        tool_calls: list[ProviderToolCall],
        available_tool_names: set[str],
    ) -> None:
        unavailable_tool_names = sorted({
            tool_call.tool_name
            for tool_call in tool_calls
            if tool_call.tool_name not in available_tool_names
        })
        if unavailable_tool_names:
            raise ValidationError(
                "Provider requested tools that were not attached to this request: "
                + ", ".join(unavailable_tool_names)
            )

    def _tool_call_provider_payload(
        self,
        tool_call: ProviderToolCall,
        provider_response: ProviderResponse,
    ) -> dict[str, str]:
        payload = {"tool_call_id": tool_call.provider_call_id}
        if tool_call.provider_name:
            payload["provider_name"] = tool_call.provider_name
        reasoning_content = extract_reasoning_content(provider_response.raw_payload)
        if reasoning_content is not None:
            payload["reasoning_content"] = reasoning_content
        return payload

    def _snapshot_has_payload_key(self, snapshot: ThreadSnapshot, key: str) -> bool:
        for payload in self._snapshot_tool_payloads(snapshot):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return True
        return False

    def _snapshot_has_trained_model(self, snapshot: ThreadSnapshot) -> bool:
        for payload in self._snapshot_tool_payloads(snapshot):
            value = payload.get("trained_model_id")
            if isinstance(value, str) and value.strip():
                return True
            trained_models = payload.get("trained_models")
            if not isinstance(trained_models, list):
                continue
            for model in trained_models:
                if isinstance(model, dict) and isinstance(model.get("trained_model_id"), str):
                    if model["trained_model_id"].strip():
                        return True
        return False

    def _snapshot_tool_payloads(self, snapshot: ThreadSnapshot) -> Iterator[dict[str, Any]]:
        for tool_call in snapshot.tool_calls:
            if isinstance(tool_call.result_payload, dict):
                yield tool_call.result_payload

    def _register_cancel_event(self, run_id: str) -> None:
        with self._cancel_lock:
            self._cancel_events[run_id] = threading.Event()

    def _clear_cancel_event(self, run_id: str) -> None:
        with self._cancel_lock:
            self._cancel_events.pop(run_id, None)

    def _is_cancel_requested(self, run_id: str) -> bool:
        with self._cancel_lock:
            cancel_event = self._cancel_events.get(run_id)
        return cancel_event.is_set() if cancel_event is not None else False

    def _raise_if_cancelled(self, run_id: str) -> None:
        if self._is_cancel_requested(run_id):
            raise AgentRunCancelled()

    def _cancel_run_and_turn(self, thread_id: str, turn_id: str, run_id: str) -> ThreadSnapshot:
        self._conversation_store.append_message(
            AppendAgentMessageInput(
                thread_id=thread_id,
                turn_id=turn_id,
                kind=AgentMessageKind.SYSTEM,
                ui_author=AgentMessageAuthor.SYSTEM,
                content_blocks=[{"type": "markdown", "text": "Run stopped by user."}],
            )
        )
        try:
            self._conversation_store.cancel_turn(thread_id, turn_id)
        except Exception:
            pass
        self._conversation_store.finish_run(
            FinishAgentRunInput(
                run_id=run_id,
                status=AgentRunStatus.CANCELLED,
                error_summary="User stopped the run.",
            )
        )
        return self._conversation_store.get_thread_snapshot(thread_id)

    def _tool_call_arguments(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return arguments

    def _complete_provider_target(
        self,
        *,
        provider: AgentProvider | None,
        fq_model_key: str | None,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
        retry_events: list[dict[str, Any]],
    ) -> ProviderResponse:
        if self._llm_service is not None:
            return self._llm_service.complete(
                fq_model_key=fq_model_key,
                messages=messages,
                tools=tools,
                retry_callback=lambda event: retry_events.append(event.to_payload()),
            )
        if provider is None:
            raise ValidationError("Agent provider is not configured.")
        return provider.complete(messages, tools)

    def _provider_stream(
        self,
        *,
        provider: AgentProvider | None,
        fq_model_key: str | None,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
    ):
        if self._llm_service is not None:
            yield from self._llm_service.stream(
                fq_model_key=fq_model_key,
                messages=messages,
                tools=tools,
            )
            return
        if provider is None:
            raise ValidationError("Agent provider is not configured.")
        stream = getattr(provider, "stream", None)
        if callable(stream):
            yield from stream(messages, tools)
            return
        yield ProviderStreamEvent(response=provider.complete(messages, tools))

    def _provider_request_usage_payload(
        self,
        usage_payload: dict[str, Any] | None,
        retry_events: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not retry_events:
            return usage_payload
        payload = dict(usage_payload or {})
        payload["retry_events"] = [dict(event) for event in retry_events]
        return payload

    def _llm_connection_event(
        self,
        *,
        provider_request: AgentProviderRequestRow,
        retry_events: list[dict[str, Any]],
        status: ChatbotEventStatus = ChatbotEventStatus.IN_PROGRESS,
    ) -> AgentHarnessStreamEvent:
        return AgentHarnessStreamEvent(
            kind="chatbot_event",
            thread_id=provider_request.thread_id,
            turn_id=provider_request.turn_id,
            run_id=provider_request.run_id,
            chatbot_event=build_llm_connection_chatbot_event(
                provider_request_id=provider_request.id,
                turn_id=provider_request.turn_id,
                retry_events=retry_events,
                status=status,
            ),
        )

    def _tool_error_result(self, exc: Exception):
        from .tools import ToolExecutionResult

        payload: dict[str, Any] = {"error": str(exc)}
        error_code = getattr(exc, "error_code", None)
        if isinstance(error_code, str) and error_code.strip():
            payload["error_code"] = error_code.strip()
        error_details = getattr(exc, "error_details", None)
        if isinstance(error_details, dict) and error_details:
            payload["error_details"] = error_details
        repair_hints = getattr(exc, "repair_hints", None)
        if isinstance(repair_hints, list) and repair_hints:
            payload["repair_hints"] = [str(hint) for hint in repair_hints if str(hint).strip()]
        retryable = getattr(exc, "retryable", None)
        if isinstance(retryable, bool):
            payload["retryable"] = retryable

        return ToolExecutionResult(
            payload=payload,
        )

    def _tool_cancelled_result(self):
        from .tools import ToolExecutionResult

        return ToolExecutionResult(
            payload={"cancelled": True},
        )

    def _materialize_source_attachments(self, input_data: SubmitUserTurnInput) -> list[DatasetAttachmentInput]:
        source_attachments = list(input_data.source_attachments)
        if not source_attachments:
            return []
        return self._import_source_attachments(source_attachments)

    def _import_source_attachments(self, source_attachments: list[SourceAttachmentInput]) -> list[DatasetAttachmentInput]:
        if self._dataset_service is None or self._artifact_service is None:
            raise ValidationError("Source attachment import requires dataset and artifact services.")

        imported: list[DatasetAttachmentInput] = []
        for source in source_attachments:
            artifact = self._artifact_service.resolve_uri(build_artifact_uri(source.artifact_id))
            if not artifact.ready_to_open:
                raise ValidationError(f"Attachment '{source.file_name}' is not ready to open.")
            if not artifact.exists:
                raise ValidationError(f"Attachment file is missing: {source.file_name}")
            source_path = Path(artifact.absolute_path).expanduser().resolve()
            registered = self._dataset_service.register_dataset_attachment(
                RegisterDatasetInput(
                    source_path=str(source_path),
                    name=source_path.stem,
                )
            )
            imported.extend(
                DatasetAttachmentInput(
                    dataset_id=item.dataset_id,
                    name=item.name,
                    file_name=item.file_name,
                    source_format=item.source_format,
                    row_count=item.row_count,
                    column_count=item.column_count,
                    preview_columns=list(item.preview_columns),
                )
                for item in registered.datasets
            )
        return imported

    def _user_content_blocks(
        self,
        text: str,
        dataset_attachments: list[DatasetAttachmentInput],
    ) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        if text:
            blocks.append({"type": "text", "text": text})
        for attachment in dataset_attachments:
            blocks.append({"type": "dataset", **attachment.model_dump(mode="json")})
        return blocks

    def _source_attachment_blocks(self, source_attachments: list[SourceAttachmentInput]) -> list[dict[str, Any]]:
        return [
            {"type": "source_attachment", **attachment.model_dump(mode="json")}
            for attachment in source_attachments
        ]

    def _hidden_dataset_blocks(self, dataset_attachments: list[DatasetAttachmentInput]) -> list[dict[str, Any]]:
        return [
            {"type": "dataset", "visible": False, **attachment.model_dump(mode="json")}
            for attachment in dataset_attachments
        ]

    def _title_from_text(self, text: str) -> str | None:
        return self._fallback_thread_title(text, [])

    def _title_from_first_message(
        self,
        text: str,
        dataset_attachments: list[DatasetAttachmentInput],
        source_attachments: list[SourceAttachmentInput] | None = None,
    ) -> str:
        if self.has_thread_title_provider():
            try:
                generated = self._llm_thread_title(text, dataset_attachments, source_attachments or [])
                if generated is not None:
                    return generated
            except Exception as exc:
                LOGGER.warning("Thread title model failed; using deterministic fallback: %s", exc)
        return self._fallback_thread_title(text, dataset_attachments, source_attachments or [])

    def _llm_thread_title(
        self,
        text: str,
        dataset_attachments: list[DatasetAttachmentInput],
        source_attachments: list[SourceAttachmentInput],
    ) -> str | None:
        response = self._complete_thread_title(
            messages=[
                ProviderMessage(role="system", content=THREAD_TITLE_SYSTEM_PROMPT),
                ProviderMessage(role="user", content=self._thread_title_prompt(text, dataset_attachments, source_attachments)),
            ]
        )
        return _sanitize_thread_title(_assistant_text(response.assistant_content_blocks))

    def _llm_thread_title_from_snapshot(self, snapshot: ThreadSnapshot) -> str | None:
        response = self._complete_thread_title(
            messages=[
                ProviderMessage(role="system", content=THREAD_TITLE_SYSTEM_PROMPT),
                ProviderMessage(role="user", content=self._thread_title_snapshot_prompt(snapshot)),
            ]
        )
        return _sanitize_thread_title(_assistant_text(response.assistant_content_blocks))

    def _complete_thread_title(self, *, messages: list[ProviderMessage]) -> ProviderResponse:
        if self._thread_title_provider is not None:
            return self._thread_title_provider.complete(messages, [])
        if self._llm_service is None:
            raise ValidationError("Thread title model is not configured.")
        fq_model_key = self._llm_service.thread_title_fq_model_key()
        if fq_model_key is None:
            raise ValidationError("Thread title model is not configured.")
        return self._llm_service.complete(
            fq_model_key=fq_model_key,
            messages=messages,
            tools=[],
        )

    def _thread_title_prompt(
        self,
        text: str,
        dataset_attachments: list[DatasetAttachmentInput],
        source_attachments: list[SourceAttachmentInput] | None = None,
    ) -> str:
        lines = ["Create a short title for this first user message."]
        if text:
            lines.extend(["", "Message:", text])
        dataset_names = [
            attachment.name.strip() or attachment.file_name.strip()
            for attachment in dataset_attachments
            if attachment.name.strip() or attachment.file_name.strip()
        ]
        if dataset_names:
            lines.extend(["", "Attached datasets:", ", ".join(dataset_names)])
        source_names = [
            attachment.file_name.strip()
            for attachment in (source_attachments or [])
            if attachment.file_name.strip()
        ]
        if source_names:
            lines.extend(["", "Attached files:", ", ".join(source_names)])
        return "\n".join(lines)

    def _thread_title_snapshot_prompt(self, snapshot: ThreadSnapshot) -> str:
        messages = [
            {
                "id": message.id,
                "turn_id": message.turn_id,
                "sequence_index": message.sequence_index,
                "kind": message.kind.value,
                "ui_author": message.ui_author.value,
                "content_blocks": [_provider_safe_content_block(block) for block in message.content_blocks],
                "status": message.status.value,
            }
            for message in snapshot.messages
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

    def _fallback_thread_title(
        self,
        text: str,
        dataset_attachments: list[DatasetAttachmentInput],
        source_attachments: list[SourceAttachmentInput] | None = None,
    ) -> str:
        title = _sanitize_thread_title(text)
        if title is not None:
            return title
        for attachment in dataset_attachments:
            title = _sanitize_thread_title(attachment.name or Path(attachment.file_name).stem or attachment.file_name)
            if title is not None:
                return title
        for attachment in source_attachments or []:
            title = _sanitize_thread_title(Path(attachment.file_name).stem or attachment.file_name)
            if title is not None:
                return title
        return "New analysis"

    def _should_auto_title_thread(self, snapshot: ThreadSnapshot) -> bool:
        return _sanitize_thread_title(snapshot.thread.title or "") is None and not snapshot.turns


def _assistant_text(blocks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for block in blocks:
        if block.get("type") in {"text", "markdown"}:
            text = str(block.get("text") or "").strip()
            if text:
                lines.append(text)
    return "\n".join(lines).strip()


def _provider_safe_content_block(block: dict[str, Any]) -> dict[str, Any]:
    if block.get("type") == "source_attachment":
        return {
            "type": "source_attachment",
            "file_name": block.get("file_name"),
            "source_format": block.get("source_format"),
        }
    if block.get("type") != "file":
        return dict(block)
    return {
        "type": "legacy_file_attachment_omitted",
    }


def _tool_execution_context(
    *,
    thread_id: str,
    turn_id: str,
    tool_call_id: str,
    dataset_ids: list[str],
    cancel_requested,
) -> "ToolExecutionContext":
    from .tools import ToolExecutionContext

    return ToolExecutionContext(
        thread_id=thread_id,
        turn_id=turn_id,
        tool_call_id=tool_call_id,
        dataset_ids=dataset_ids,
        cancel_requested=cancel_requested,
    )


def _sanitize_thread_title(raw: str) -> str | None:
    title = re.sub(r"\s+", " ", raw).strip()
    title = title.lstrip("#-*• ").strip()
    for prefix in ("Title:", "title:", "标题：", "标题:"):
        if title.startswith(prefix):
            title = title[len(prefix) :].strip()
            break
    title = title.strip("\"'`“”‘’")
    title = title.rstrip(".。!！?？").strip()
    if not title:
        return None
    if len(title) > THREAD_TITLE_MAX_LENGTH:
        title = title[:THREAD_TITLE_MAX_LENGTH].rstrip()
    return title or None
