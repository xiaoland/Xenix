# Chatbot Activity Event Boundary

## Objective & Hypothesis

Redesign the Chatbot streaming/activity boundary so Chatbot UI owns the interpretation of conversation events, while Agent Harness remains an upstream projector of append-only Chatbot events rather than an imperative controller of UI widgets.

This task will also fix the observed missing-thinking gap during multi-step tool-call conversations.

Current hypothesis:

- The missing-thinking gap is a symptom of the wrong boundary, not just a local timing bug.
- Current Harness code emits `THINKING` start/terminal events and tracks `thinking_active`, which effectively makes Harness manage Chatbot UI transient widget lifetime.
- A naive fix that emits `THINKING IN_PROGRESS` before each provider loop would restore the visible indicator, but would deepen the same coupling.
- Exposing provider request start/resolved events to Chatbot UI is also wrong because it leaks Harness orchestration internals across the Chatbot event boundary.
- The desired boundary is a Chatbot-level semantic event stream. Chatbot UI should reduce that stream into transient visual state such as a thinking indicator.

## Guardrails Touched

- `AGENTS.md`: ask explicit user start before product code mutation; task packets may be updated during exploration/solidification.
- `docs/00-meta/implementation-taste.md`: preserve single authority and classify boundary values by provenance before reshaping event flow.
- `docs/30-unit-tdd/chatbot-ui.md`: current streaming contract is likely stale because it says transient thinking state is owned by Agent Harness events.
- `src/xenix/services/agent/harness_service.py`: currently owns `thinking_active` and emits `THINKING` lifecycle events.
- `src/xenix/services/agent/chatbot_events.py`: currently models `ChatbotEventKind.THINKING` as an event kind.
- `src/xenix/ui/chatbot.py`: currently special-cases `THINKING` events by inserting/removing a temporary bubble.
- `src/xenix/ui/main_window.py`: applies Harness stream events to ThreadDetailView.

## Current Understanding

- Chatbot UI should see a sequence of append-only Chatbot events with stable UI semantics.
- Event schema and continuous interpretation belong to Chatbot UI, not to Agent Harness widget-control logic.
- Harness internals such as provider requests, step-loop iterations, retries, and tool execution scheduling must not become Chatbot UI concepts.
- Tool calls are user-visible only after they are projected into Chatbot tool events; raw streamed tool-call arguments should not be shown as normal assistant text.
- In the latest completed DB run, several provider waits lasted 18-27 seconds after prior tool events had already hidden the initial thinking indicator.
- The existing implementation emits one initial thinking event at turn start, hides it on assistant text or visible tool event, and never re-establishes it for later model-work windows in the same turn.
- Therefore network latency explains the duration of the blank periods, but not the absence of a progress indicator.
- A prior icon crash involving `icon_key="connection"` and invalid `ph.plugs-connected` could also prevent UI updates in older stuck runs, but the multi-step missing-thinking gap is a separate event-boundary defect.
- Confirmed topology:
  - `AgentHarnessService` owns orchestration and persistence.
  - Chatbot event projection owns Chatbot-domain event shape.
  - `MainWindow` routes stream events and snapshots without interpreting activity.
  - `ThreadDetailView` owns Chatbot event reduction and transient visual state.

## Decisions

- Do not fix this by adding more `thinking_active` branches in `AgentHarnessService`.
- Do not expose provider request start/resolved events to Chatbot UI.
- Do not make Chatbot UI understand Harness orchestration internals.
- Treat thinking as a transient Chatbot UI projection, not as a Harness-owned widget lifecycle command.
- The Chatbot event boundary should express UI-domain conversation semantics, not backend execution structure.
- This task owns the redesign needed to make the missing-thinking fix follow that boundary.
- Use `ChatbotEventKind.ACTIVITY` for the semantic progress fact.
- Keep legacy `THINKING` handling in `ThreadDetailView` as a compatibility path, but remove Harness-owned `THINKING` lifecycle from the streaming contract.

## Design Direction

Candidate shape:

- Replace Harness-owned `THINKING` lifecycle control with a Chatbot-level semantic activity signal whose name does not expose provider internals.
- The signal should mean: the assistant turn is still advancing and no new user-visible assistant/tool content is available at this instant.
- Chatbot UI should reduce activity and visible content events into transient visual state:
  - show an activity/thinking indicator while assistant activity is active and no assistant text/tool event has superseded it
  - hide or replace it when a visible assistant text event or visible tool event arrives
  - allow activity to become active again later in the same turn after tool results, because the assistant may be computing the next visible output
- Event ids and statuses must support append-only event interpretation without requiring UI to mutate service-owned entities.
- The exact schema name is still open; avoid names like `provider_request` or anything tied to Harness internals.

## Implementation

- `ChatbotEventKind.ACTIVITY` added as a Chatbot-domain semantic event.
- `build_activity_chatbot_event(...)` emits an assistant `IN_PROGRESS` activity event with no thinking content blocks and no provider request identity.
- `AgentHarnessService._run_provider_loop_stream(...)` now emits activity at the start of each assistant work window.
- Harness no longer accepts or mutates `thinking_active` and no longer emits `THINKING` terminal events to control UI widget lifetime.
- `ThreadDetailView` interprets `ACTIVITY` as a local transient thinking indicator.
- `ThreadDetailView` clears the derived thinking indicator when visible assistant text, tool, connection, usage, snapshot, stop, or error state supersedes it.
- Existing EventList free-scroll behavior is preserved because activity indicator insertion uses the same conditional auto-follow path.
- `docs/30-unit-tdd/chatbot-ui.md` and `docs/30-unit-tdd/agent-harness.md` now document the activity boundary instead of Harness-owned thinking.

## Verification Plan

- Add a streaming regression where:
  - the first assistant step creates a visible tool event
  - the tool completes
  - the next assistant activity window blocks before visible output
  - Chatbot UI shows the derived thinking/activity indicator during that second wait
- Preserve existing behavior where assistant text streaming replaces the indicator with visible text.
- Preserve behavior where raw tool-call argument streaming does not render raw JSON as assistant content.
- Preserve EventList free-scroll behavior while activity events arrive.
- Run focused Harness/LLM streaming tests plus Qt Chatbot boundary tests.

Verification so far:

- `pdm run pytest tests/test_agent_harness_streaming.py::test_agent_harness_streams_assistant_as_message_events tests/test_agent_harness_streaming.py::test_agent_harness_keeps_thinking_during_tool_call_delta_stream tests/test_agent_harness_streaming.py::test_agent_harness_emits_activity_again_after_visible_tool_result -q`
- `pdm run pytest tests/test_main.py::test_thread_detail_view_activity_event_is_bottom_temporary_message tests/test_main.py::test_main_window_keeps_thinking_indicator_during_non_final_snapshot tests/test_main.py::test_main_window_stop_cancels_active_agent_run -q`
- `pdm run pytest tests/test_i18n.py -q`
- `pdm run pytest tests/test_agent_harness_streaming.py -q`
- `pdm run pytest tests/test_llm_service_retry.py -q`
- `pdm run pytest tests/test_main.py::test_thread_detail_view_activity_event_is_bottom_temporary_message tests/test_main.py::test_main_window_keeps_thinking_indicator_during_non_final_snapshot tests/test_main.py::test_thread_detail_view_preserves_user_scroll_during_streaming_update tests/test_main.py::test_thread_detail_view_scrolls_to_latest_message_after_append tests/test_main.py::test_tool_icon_semantic_names_resolve_to_pixmaps -q`
- `pdm run pytest tests/test_main.py -q`
- `pdm run python -m compileall -q src/xenix/services/agent/chatbot_events.py src/xenix/services/agent/harness_service.py src/xenix/ui/chatbot.py tests/test_agent_harness_streaming.py tests/test_main.py tests/test_i18n.py`
- `git diff --check`

## Next Step

Ready for user review. Commit only after explicit user command.
