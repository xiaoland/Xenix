from __future__ import annotations

from dataclasses import dataclass
import threading
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
    RenameAgentThreadInput,
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
    delta_text: str = ""
    snapshot: ThreadSnapshot | None = None
    used_steps: int = 0
    suggested_steps: int = 0
    max_total_steps: int = 0


@dataclass(frozen=True)
class StepBudgetPause:
    thread_id: str
    turn_id: str
    run_id: str
    used_steps: int
    suggested_steps: int
    max_total_steps: int
    snapshot: ThreadSnapshot


class AgentRunCancelled(Exception):
    pass


class AgentHarnessService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        provider: AgentProvider,
        tool_registry: AgentToolRegistry,
        conversation_store: ConversationStore | None = None,
        initial_step_limit: int = 16,
        step_extension_limit: int = 16,
        max_total_steps: int = 64,
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._tool_registry = tool_registry
        self._conversation_store = conversation_store or ConversationStore(session_factory)
        self._initial_step_limit = max(1, initial_step_limit)
        self._step_extension_limit = max(1, step_extension_limit)
        self._max_total_steps = max(self._initial_step_limit, max_total_steps)
        self._cancel_events: dict[str, threading.Event] = {}
        self._cancel_lock = threading.Lock()

    def create_thread(self, title: str | None = None) -> ThreadSnapshot:
        thread = self._conversation_store.create_thread(CreateAgentThreadInput(title=title))
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

    def set_provider(self, provider: AgentProvider) -> None:
        self._provider = provider

    def cancel_run(self, run_id: str) -> None:
        with self._cancel_lock:
            cancel_event = self._cancel_events.setdefault(run_id, threading.Event())
            cancel_event.set()

    def submit_user_turn(self, input_data: SubmitUserTurnInput) -> ThreadSnapshot:
        thread_id, turn_id, run_id, file_paths = self._start_user_turn(input_data)

        try:
            outcome = self._run_provider_loop(
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                file_paths=file_paths,
                step_state=self._initial_step_state(),
            )
            if isinstance(outcome, StepBudgetPause):
                return outcome.snapshot
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=run_id,
                    status=AgentRunStatus.SUCCEEDED,
                )
            )
            return outcome
        except AgentRunCancelled:
            snapshot = self._cancel_run_and_turn(thread_id, turn_id, run_id)
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
        finally:
            self._clear_cancel_event(run_id)

    def submit_user_turn_stream(self, input_data: SubmitUserTurnInput):
        thread_id, turn_id, run_id, file_paths = self._start_user_turn(input_data)
        yield AgentHarnessStreamEvent(
            kind="turn_started",
            thread_id=thread_id,
            turn_id=turn_id,
            run_id=run_id,
            snapshot=self._conversation_store.get_thread_snapshot(thread_id),
        )

        try:
            outcome = yield from self._run_provider_loop_stream(
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                file_paths=file_paths,
                step_state=self._initial_step_state(),
            )
            if isinstance(outcome, StepBudgetPause):
                yield self._step_confirmation_event(outcome)
                return
            self._conversation_store.finish_run(
                FinishAgentRunInput(
                    run_id=run_id,
                    status=AgentRunStatus.SUCCEEDED,
                )
            )
            yield AgentHarnessStreamEvent(
                kind="snapshot",
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                snapshot=outcome,
            )
        except AgentRunCancelled:
            snapshot = self._cancel_run_and_turn(thread_id, turn_id, run_id)
            yield AgentHarnessStreamEvent(
                kind="snapshot",
                thread_id=thread_id,
                turn_id=turn_id,
                run_id=run_id,
                snapshot=snapshot,
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
        granted_steps = self._requested_step_extension(input_data.additional_steps, step_state)
        step_state["granted_steps"] += granted_steps
        self._conversation_store.resume_run_after_confirmation(input_data.run_id, self._usage_payload(step_state))
        self._register_cancel_event(input_data.run_id)
        snapshot = self._conversation_store.get_thread_snapshot(input_data.thread_id)
        file_paths = self._attached_files_for_turn(snapshot, input_data.turn_id)
        yield AgentHarnessStreamEvent(
            kind="turn_resumed",
            thread_id=input_data.thread_id,
            turn_id=input_data.turn_id,
            run_id=input_data.run_id,
            snapshot=snapshot,
        )

        try:
            outcome = yield from self._run_provider_loop_stream(
                thread_id=input_data.thread_id,
                turn_id=input_data.turn_id,
                run_id=input_data.run_id,
                file_paths=file_paths,
                step_state=step_state,
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
            )
        except AgentRunCancelled:
            snapshot = self._cancel_run_and_turn(input_data.thread_id, input_data.turn_id, input_data.run_id)
            yield AgentHarnessStreamEvent(
                kind="snapshot",
                thread_id=input_data.thread_id,
                turn_id=input_data.turn_id,
                run_id=input_data.run_id,
                snapshot=snapshot,
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
                usage_payload=self._usage_payload(self._initial_step_state()),
            )
        )
        self._register_cancel_event(run.id)
        return thread_id, turn.id, run.id, list(input_data.file_paths)


    def _run_provider_loop(
        self,
        *,
        thread_id: str,
        turn_id: str,
        run_id: str,
        file_paths: list[str],
        step_state: dict[str, int],
    ) -> ThreadSnapshot | StepBudgetPause:
        while step_state["used_steps"] < step_state["granted_steps"]:
            step_state["used_steps"] += 1
            self._raise_if_cancelled(run_id)
            snapshot = self._conversation_store.get_thread_snapshot(thread_id)
            provider_response = self._provider.complete(snapshot.provider_messages(), self._tool_registry.list_specs())
            self._raise_if_cancelled(run_id)
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
                self._conversation_store.end_turn(thread_id, turn_id)
                return self._conversation_store.get_thread_snapshot(thread_id)

            for tool_call in provider_response.tool_calls:
                self._raise_if_cancelled(run_id)
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
                            cancel_requested=lambda run_id=run_id: self._is_cancel_requested(run_id),
                        ),
                    )
                    status = AgentToolCallStatus.SUCCEEDED
                    error_summary = None
                except Exception as exc:
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
                        content_blocks=[
                            *result.content_blocks,
                            {"type": "tool_result_payload", "payload": result.payload},
                        ],
                        provider_payload={"tool_call_id": tool_call.provider_call_id},
                    )
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
    ):
        while step_state["used_steps"] < step_state["granted_steps"]:
            step_state["used_steps"] += 1
            self._raise_if_cancelled(run_id)
            snapshot = self._conversation_store.get_thread_snapshot(thread_id)
            provider_response: ProviderResponse | None = None
            yield AgentHarnessStreamEvent(kind="thinking_started", thread_id=thread_id, turn_id=turn_id, run_id=run_id)
            for stream_event in self._provider_stream(snapshot.provider_messages(), self._tool_registry.list_specs()):
                self._raise_if_cancelled(run_id)
                if stream_event.delta_text:
                    yield AgentHarnessStreamEvent(
                        kind="assistant_delta",
                        thread_id=thread_id,
                        delta_text=stream_event.delta_text,
                    )
                if stream_event.response is not None:
                    provider_response = stream_event.response
            yield AgentHarnessStreamEvent(kind="thinking_finished", thread_id=thread_id, turn_id=turn_id, run_id=run_id)
            self._raise_if_cancelled(run_id)

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
                self._conversation_store.end_turn(thread_id, turn_id)
                return self._conversation_store.get_thread_snapshot(thread_id)

            for tool_call in provider_response.tool_calls:
                self._raise_if_cancelled(run_id)
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
                            cancel_requested=lambda run_id=run_id: self._is_cancel_requested(run_id),
                        ),
                    )
                    status = AgentToolCallStatus.SUCCEEDED
                    error_summary = None
                except Exception as exc:
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
                        content_blocks=[
                            *result.content_blocks,
                            {"type": "tool_result_payload", "payload": result.payload},
                        ],
                        provider_payload={"tool_call_id": tool_call.provider_call_id},
                    )
                )
                if status is AgentToolCallStatus.CANCELLED:
                    raise AgentRunCancelled()
        return self._pause_for_step_confirmation(
            thread_id=thread_id,
            turn_id=turn_id,
            run_id=run_id,
            step_state=step_state,
        )

    def _initial_step_state(self) -> dict[str, int]:
        return {
            "used_steps": 0,
            "granted_steps": self._initial_step_limit,
            "extension_step_limit": self._step_extension_limit,
            "max_total_steps": self._max_total_steps,
        }

    def _usage_payload(self, step_state: dict[str, int]) -> dict[str, Any]:
        return {"step_budget": dict(step_state)}

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
        self._conversation_store.append_message(
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
        self._conversation_store.pause_run_for_confirmation(run_id, self._usage_payload(step_state))
        snapshot = self._conversation_store.get_thread_snapshot(thread_id)
        return StepBudgetPause(
            thread_id=thread_id,
            turn_id=turn_id,
            run_id=run_id,
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
            used_steps=pause.used_steps,
            suggested_steps=pause.suggested_steps,
            max_total_steps=pause.max_total_steps,
        )

    def _attached_files_for_turn(self, snapshot: ThreadSnapshot, turn_id: str) -> list[str]:
        paths: list[str] = []
        for message in snapshot.messages:
            if message.turn_id != turn_id or message.kind is not AgentMessageKind.USER:
                continue
            for block in message.content_blocks:
                if block.get("type") == "file":
                    path = str(block.get("path") or "").strip()
                    if path:
                        paths.append(path)
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
        if not text:
            return "New analysis"
        return text[:80]
