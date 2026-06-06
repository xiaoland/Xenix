from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
import threading
from time import perf_counter
from typing import Any, Iterator

from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel

from ...exceptions import ValidationError
from ...observability import record_counter, record_histogram, stable_hash, start_span
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
    TurnCompletionGuardVerdict,
)
from .chatbot_events import (
    ChatbotEvent,
    ChatbotEventStatus,
    build_thinking_chatbot_event,
    project_chatbot_events,
    project_text_message_event,
    project_tool_chatbot_event,
)
from .providers import (
    AgentProvider,
    AgentToolSpec,
    ProviderMessage,
    ProviderResponse,
    ProviderStreamEvent,
    ProviderToolCall,
)
from .tools import (
    AgentToolRegistry,
    ToolExecutionContext,
    tool_presentation_for_name,
)
from ..llm import LLMModelOption, LLMService


class SubmitUserTurnInput(SQLModel):
    thread_id: str | None = None
    text: str
    file_paths: list[str] = Field(default_factory=list)
    fq_model_key: str | None = None


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
    attached_files: tuple[str, ...] = ()
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
        turn_completion_guard_provider: AgentProvider | None = None,
        thread_title_provider: AgentProvider | None = None,
        conversation_store: ConversationStore | None = None,
        initial_step_limit: int = 16,
        step_extension_limit: int = 16,
        max_total_steps: int = 64,
    ) -> None:
        if provider is None and llm_service is None:
            raise ValidationError("Agent Harness requires a provider or an LLM service.")
        self._session_factory = session_factory
        self._provider = provider
        self._llm_service = llm_service
        self._turn_completion_guard = (
            TurnCompletionGuard(turn_completion_guard_provider)
            if turn_completion_guard_provider is not None
            else None
        )
        self._thread_title_provider = thread_title_provider
        self._tool_registry = tool_registry
        self._conversation_store = conversation_store or ConversationStore(session_factory)
        self._initial_step_limit = max(1, initial_step_limit)
        self._step_extension_limit = max(1, step_extension_limit)
        self._max_total_steps = max(self._initial_step_limit, max_total_steps)
        self._cancel_events: dict[str, threading.Event] = {}
        self._cancel_lock = threading.Lock()

    def create_thread(self, title: str | None = None, fq_model_key: str | None = None) -> ThreadSnapshot:
        selected_fq_model_key = self._resolve_fq_model_key(fq_model_key, None)
        thread = self._conversation_store.create_thread(
            CreateAgentThreadInput(
                title=title,
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
        return self._thread_title_provider is not None

    def generate_thread_title(self, thread_id: str) -> str:
        if self._thread_title_provider is None:
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
        with start_span("agent.turn"):
            thread_id, turn_id, run_id, file_paths, provider = self._start_user_turn(input_data)

            try:
                outcome = self._run_provider_loop(
                    thread_id=thread_id,
                    turn_id=turn_id,
                    run_id=run_id,
                    file_paths=file_paths,
                    step_state=self._initial_step_state(),
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
        with start_span("agent.turn"):
            thread_id, turn_id, run_id, file_paths, provider = self._start_user_turn(input_data)
            yield from self._submit_user_turn_stream_started(thread_id, turn_id, run_id, file_paths, provider)

    def _submit_user_turn_stream_started(
        self,
        thread_id: str,
        turn_id: str,
        run_id: str,
        file_paths: list[str],
        provider: AgentProvider,
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
                file_paths=file_paths,
                step_state=self._initial_step_state(),
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
        file_paths = self._attached_files_for_thread(snapshot)
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
                file_paths=file_paths,
                step_state=step_state,
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

    def _start_user_turn(self, input_data: SubmitUserTurnInput) -> tuple[str, str, str, list[str], AgentProvider]:
        text = input_data.text.strip()
        if not text and not input_data.file_paths:
            raise ValidationError("A turn needs a user message or at least one file.")

        thread_id = input_data.thread_id
        should_auto_title_existing_thread = False
        if thread_id is None:
            selected_fq_model_key = self._resolve_fq_model_key(input_data.fq_model_key, None)
            thread_id = self._conversation_store.create_thread(
                CreateAgentThreadInput(
                    title=self._title_from_first_message(text, input_data.file_paths),
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
        provider = self._provider_for_fq_model_key(selected_fq_model_key)

        content_blocks = self._user_content_blocks(text, input_data.file_paths)
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
                    title=self._title_from_first_message(text, input_data.file_paths),
                )
            )
        run = self._conversation_store.start_run(
            StartAgentRunInput(
                thread_id=thread_id,
                turn_id=turn.id,
                provider_name=self._provider_name(provider),
                usage_payload=self._usage_payload(
                    self._initial_step_state(),
                    fq_model_key=selected_fq_model_key,
                ),
            )
        )
        self._register_cancel_event(run.id)
        return thread_id, turn.id, run.id, list(input_data.file_paths), provider


    def _run_provider_loop(
        self,
        *,
        thread_id: str,
        turn_id: str,
        run_id: str,
        file_paths: list[str],
        step_state: dict[str, int],
        provider: AgentProvider,
    ) -> ThreadSnapshot | StepBudgetPause:
        while step_state["used_steps"] < step_state["granted_steps"]:
            step_state["used_steps"] += 1
            self._raise_if_cancelled(run_id)
            snapshot = self._conversation_store.get_thread_snapshot(thread_id)
            provider_messages = snapshot.provider_messages()
            attached_files = self._attached_files_for_thread(snapshot) or list(file_paths)
            provider_request = self._create_provider_request(
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                provider=provider,
                request_kind=AgentProviderRequestKind.PRIMARY,
                input_message_ids=self._provider_input_message_ids(provider_messages),
            )
            tool_specs = self._tool_specs_for_context(snapshot=snapshot, attached_files=attached_files)
            available_tool_names = {tool.name for tool in tool_specs}
            try:
                with start_span("agent.provider_request", self._provider_request_attributes(provider_request)):
                    provider_response = provider.complete(
                        provider_messages,
                        tool_specs,
                    )
                    self._raise_if_cancelled(run_id)
                    self._validate_provider_tool_calls(provider_response.tool_calls, available_tool_names)
            except AgentRunCancelled:
                self._complete_provider_request(
                    provider_request,
                    status=AgentProviderRequestStatus.CANCELLED,
                )
                raise
            except Exception:
                self._complete_provider_request(
                    provider_request,
                    status=AgentProviderRequestStatus.FAILED,
                )
                raise
            try:
                self._raise_if_cancelled(run_id)
            except AgentRunCancelled:
                self._complete_provider_request(
                    provider_request,
                    status=AgentProviderRequestStatus.CANCELLED,
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
                        provider_payload={"tool_call_id": tool_call.provider_call_id},
                    )
                )
                provider_output_message_ids.append(request_message.id)
                persisted_tool_calls.append((tool_call, arguments, persisted_tool_call))

            self._complete_provider_request(
                provider_request,
                status=AgentProviderRequestStatus.SUCCEEDED,
                output_message_ids=provider_output_message_ids,
                usage_payload=provider_response.usage_payload,
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
                    with start_span("agent.tool_call", self._tool_call_attributes(persisted_tool_call)):
                        result = self._tool_registry.execute(
                            tool_call.tool_name,
                            arguments,
                            ToolExecutionContext(
                                thread_id=thread_id,
                                turn_id=turn_id,
                                tool_call_id=persisted_tool_call.id,
                                attached_files=attached_files,
                                cancel_requested=lambda run_id=run_id: self._is_cancel_requested(run_id),
                            ),
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
        file_paths: list[str],
        step_state: dict[str, int],
        provider: AgentProvider,
    ):
        while step_state["used_steps"] < step_state["granted_steps"]:
            step_state["used_steps"] += 1
            self._raise_if_cancelled(run_id)
            snapshot = self._conversation_store.get_thread_snapshot(thread_id)
            provider_messages = snapshot.provider_messages()
            attached_files = self._attached_files_for_thread(snapshot) or list(file_paths)
            provider_request = self._create_provider_request(
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                provider=provider,
                request_kind=AgentProviderRequestKind.PRIMARY,
                input_message_ids=self._provider_input_message_ids(provider_messages),
            )
            provider_response: ProviderResponse | None = None
            assistant_message: AgentMessageRow | None = None
            assistant_text = ""
            provider_output_message_ids: list[str] = []
            thinking_in_progress = True
            tool_specs = self._tool_specs_for_context(snapshot=snapshot, attached_files=attached_files)
            available_tool_names = {tool.name for tool in tool_specs}
            yield self._thinking_event(
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                status=ChatbotEventStatus.IN_PROGRESS,
            )
            try:
                with start_span("agent.provider_request", self._provider_request_attributes(provider_request)):
                    for stream_event in self._provider_stream(
                        provider,
                        provider_messages,
                        tool_specs,
                    ):
                        self._raise_if_cancelled(run_id)
                        if thinking_in_progress:
                            thinking_in_progress = False
                            yield self._thinking_event(
                                thread_id=thread_id,
                                turn_id=turn_id,
                                run_id=run_id,
                                status=ChatbotEventStatus.COMPLETED,
                            )
                        if stream_event.delta_text:
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
                self._raise_if_cancelled(run_id)
            except AgentRunCancelled:
                self._complete_provider_request(
                    provider_request,
                    status=AgentProviderRequestStatus.CANCELLED,
                )
                if thinking_in_progress:
                    yield self._thinking_event(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        run_id=run_id,
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
                )
                if thinking_in_progress:
                    yield self._thinking_event(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        run_id=run_id,
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
            if thinking_in_progress:
                thinking_in_progress = False
                yield self._thinking_event(
                    thread_id=thread_id,
                    turn_id=turn_id,
                    run_id=run_id,
                    status=ChatbotEventStatus.COMPLETED,
                )

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
            try:
                self._validate_provider_tool_calls(provider_response.tool_calls, available_tool_names)
            except Exception:
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
                raise

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
                        provider_payload={"tool_call_id": tool_call.provider_call_id},
                    )
                )
                provider_output_message_ids.append(request_message.id)
                persisted_tool_calls.append((tool_call, arguments, request_message, persisted_tool_call))
                yield self._tool_event(
                    "message_created",
                    request_message,
                    run_id,
                    tool_call=persisted_tool_call,
                    request_message=request_message,
                )

            self._complete_provider_request(
                provider_request,
                status=AgentProviderRequestStatus.SUCCEEDED,
                output_message_ids=provider_output_message_ids,
                usage_payload=provider_response.usage_payload,
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
                    with start_span("agent.tool_call", self._tool_call_attributes(persisted_tool_call)):
                        result = self._tool_registry.execute(
                            tool_call.tool_name,
                            arguments,
                            ToolExecutionContext(
                                thread_id=thread_id,
                                turn_id=turn_id,
                                tool_call_id=persisted_tool_call.id,
                                attached_files=attached_files,
                                cancel_requested=lambda run_id=run_id: self._is_cancel_requested(run_id),
                            ),
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
        provider: AgentProvider,
        request_kind: AgentProviderRequestKind,
        input_message_ids: list[str],
    ) -> AgentProviderRequestRow:
        return self._conversation_store.create_provider_request(
            CreateProviderRequestInput(
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                provider_name=self._provider_name(provider),
                model=self._provider_model(provider),
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
        attributes: dict[str, Any] = {
            "agent.provider.name": provider_request.provider_name or "unknown",
            "agent.provider_request.kind": provider_request.request_kind.value,
        }
        if provider_request.model:
            attributes["agent.model.hash"] = stable_hash(provider_request.model)
        return attributes

    def _tool_call_attributes(self, tool_call: AgentToolCallRow) -> dict[str, Any]:
        return {"agent.tool.name": tool_call.tool_name}

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

    def _record_tool_call(self, tool_call: AgentToolCallRow, duration_ms: float, error: BaseException | None = None) -> None:
        attributes = self._tool_call_attributes(tool_call)
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
        if self._llm_service is not None:
            return self._llm_service.build_provider(fq_model_key)
        if self._provider is None:
            raise ValidationError("Agent provider is not configured.")
        return self._provider

    def _provider_for_run(self, run) -> AgentProvider:
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

    def _thinking_event(
        self,
        *,
        thread_id: str,
        turn_id: str,
        run_id: str,
        status: ChatbotEventStatus,
    ) -> AgentHarnessStreamEvent:
        return AgentHarnessStreamEvent(
            kind="chatbot_event",
            thread_id=thread_id,
            turn_id=turn_id,
            run_id=run_id,
            chatbot_event=build_thinking_chatbot_event(
                run_id=run_id,
                turn_id=turn_id,
                status=status,
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
        if self._turn_completion_guard is None:
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
            provider=self._turn_completion_guard.provider,
            request_kind=AgentProviderRequestKind.GUARD,
            input_message_ids=list(source_message_ids),
        )
        result = self._turn_completion_guard.evaluate(last_assistant_text)
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
            usage_payload=result.usage_payload,
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

    def _tool_specs_for_context(self, *, snapshot: ThreadSnapshot, attached_files: list[str]) -> list[AgentToolSpec]:
        context = _ToolAvailabilityContext(
            attached_files=tuple(attached_files),
            has_dataset=self._snapshot_has_dataset(snapshot),
            has_selection=self._snapshot_has_payload_key(snapshot, "binding_id"),
            has_trained_model=self._snapshot_has_trained_model(snapshot),
        )
        return [
            spec
            for spec in self._tool_registry.list_specs()
            if self._tool_available_for_context(spec.name, context)
        ]

    def _tool_available_for_context(self, tool_name: str, context: _ToolAvailabilityContext) -> bool:
        if tool_name == "data.peek":
            return bool(context.attached_files) or context.has_dataset
        if tool_name == "data.integrate":
            return bool(context.attached_files)
        if tool_name.startswith("data."):
            return context.has_dataset
        if tool_name.startswith("analysis."):
            return context.has_dataset
        if tool_name in {"model.train", "model.hyper_train"}:
            return context.has_selection
        if tool_name == "model.apply":
            return context.has_trained_model
        return True

    def _snapshot_has_dataset(self, snapshot: ThreadSnapshot) -> bool:
        for payload in self._snapshot_tool_payloads(snapshot):
            value = payload.get("dataset_id")
            if isinstance(value, str) and value.strip():
                return True
            values = payload.get("input_dataset_ids")
            if isinstance(values, list) and any(isinstance(item, str) and item.strip() for item in values):
                return True
        return False

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

    def _attached_files_for_thread(self, snapshot: ThreadSnapshot) -> list[str]:
        paths: list[str] = []
        seen: set[str] = set()
        for message in snapshot.messages:
            if message.kind is not AgentMessageKind.USER:
                continue
            for block in message.content_blocks:
                if block.get("type") != "file":
                    continue
                path = str(block.get("path") or "").strip()
                if path and path not in seen:
                    paths.append(path)
                    seen.add(path)
        return paths

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

    def _provider_stream(
        self,
        provider: AgentProvider,
        messages: list[Any],
        tools: list[Any],
    ):
        stream = getattr(provider, "stream", None)
        if callable(stream):
            yield from stream(messages, tools)
            return
        yield ProviderStreamEvent(response=provider.complete(messages, tools))

    def _tool_error_result(self, exc: Exception):
        from .tools import ToolExecutionResult

        return ToolExecutionResult(
            payload={"error": str(exc)},
            content_blocks=[{"type": "markdown", "text": f"Tool failed: {exc}"}],
        )

    def _tool_cancelled_result(self):
        from .tools import ToolExecutionResult

        return ToolExecutionResult(
            payload={"cancelled": True},
            content_blocks=[{"type": "tool_call_result", "status": "cancelled", "error_summary": "Cancelled by user."}],
        )

    def _user_content_blocks(self, text: str, file_paths: list[str]) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        if text:
            blocks.append({"type": "text", "text": text})
        for file_path in file_paths:
            blocks.append({"type": "file", "path": file_path})
        return blocks

    def _title_from_text(self, text: str) -> str | None:
        return self._fallback_thread_title(text, [])

    def _title_from_first_message(self, text: str, file_paths: list[str]) -> str:
        if self._thread_title_provider is not None:
            try:
                generated = self._llm_thread_title(text, file_paths)
                if generated is not None:
                    return generated
            except Exception as exc:
                LOGGER.warning("Thread title model failed; using deterministic fallback: %s", exc)
        return self._fallback_thread_title(text, file_paths)

    def _llm_thread_title(self, text: str, file_paths: list[str]) -> str | None:
        response = self._thread_title_provider.complete(
            [
                ProviderMessage(role="system", content=THREAD_TITLE_SYSTEM_PROMPT),
                ProviderMessage(role="user", content=self._thread_title_prompt(text, file_paths)),
            ],
            [],
        )
        return _sanitize_thread_title(_assistant_text(response.assistant_content_blocks))

    def _llm_thread_title_from_snapshot(self, snapshot: ThreadSnapshot) -> str | None:
        response = self._thread_title_provider.complete(
            [
                ProviderMessage(role="system", content=THREAD_TITLE_SYSTEM_PROMPT),
                ProviderMessage(role="user", content=self._thread_title_snapshot_prompt(snapshot)),
            ],
            [],
        )
        return _sanitize_thread_title(_assistant_text(response.assistant_content_blocks))

    def _thread_title_prompt(self, text: str, file_paths: list[str]) -> str:
        lines = ["Create a short title for this first user message."]
        if text:
            lines.extend(["", "Message:", text])
        if file_paths:
            file_names = ", ".join(Path(file_path).name for file_path in file_paths if str(file_path).strip())
            if file_names:
                lines.extend(["", "Attached files:", file_names])
        return "\n".join(lines)

    def _thread_title_snapshot_prompt(self, snapshot: ThreadSnapshot) -> str:
        messages = [
            {
                "id": message.id,
                "turn_id": message.turn_id,
                "sequence_index": message.sequence_index,
                "kind": message.kind.value,
                "ui_author": message.ui_author.value,
                "content_blocks": message.content_blocks,
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

    def _fallback_thread_title(self, text: str, file_paths: list[str]) -> str:
        title = _sanitize_thread_title(text)
        if title is not None:
            return title
        for file_path in file_paths:
            path = Path(file_path)
            title = _sanitize_thread_title(path.stem or path.name)
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
