# Chatbot EventList Exploration

## Objective & Hypothesis

- Objective: redesign the Chatbot message timeline model so UI renders user-facing Chatbot Events, not one widget per persisted Agent Message.
- Hypothesis: keeping Agent Harness persistence message-centric while having Agent Harness project paired tool-call messages into Chatbot Events will make the UI clearer without weakening replay, audit, LLM context, or provider semantics.

## Prompt

- User wants Chatbot MessageList implementation updated so a tool-call message and its corresponding tool-call result message render as one item.
- The combined item should be a compact row, not a bubble: tool-type icon, summary text, and chevron.
- Chevron expands or collapses result content.
- If only the tool-call message exists and the result message has not arrived yet, the tool-call item should still render.
- User further suggests renaming or reframing MessageList as Chatbot EventList, where every visible list item is a Chatbot Event.
- User does not want ambiguity handled by stacked fallback heuristics when a durable invariant or projection boundary can solve it.
- User agrees the more fundamental fix is for Chatbot UI to consume Chatbot Events instead of storage rows, and suggests Agent Harness should own this projection.
- User expects tool-call success/failure descriptive text to remain in Agent Harness because it can also be part of what returns to the LLM.

## Guardrails Touched

- `docs/30-unit-tdd/chatbot-ui.md`: Chatbot timeline rendering contract.
- `docs/30-unit-tdd/agent-harness.md`: Agent Harness message and tool-call persistence contract.
- `src/xenix/ui/chat_box.py`: current Qt widget implementation for the Chatbot timeline.
- `src/xenix/services/agent/conversation_store.py`: creates persisted tool-call and tool-call-result messages.
- `src/xenix/services/storage/models.py`: defines Agent Message and Tool Call storage rows.
- `tests/test_main.py`: current UI boundary coverage for tool-call rendering.

## Current Facts

- Agent Harness persists tool call request and result as separate `AgentMessageRow` records:
  - `AgentMessageKind.TOOL_CALL`
  - `AgentMessageKind.TOOL_CALL_RESULT`
- `AgentToolCallRow` links the request and result messages via:
  - `request_message_id`
  - `result_message_id`
- Current Chatbot UI renders persisted messages directly through `ChatMessageBubble`.
- Current unit TDD already says tool-call and tool-result messages render as compact tool rows, so bubble-style rendering is already inconsistent with the stated direction.
- Assistant text is the only currently meaningful streaming content path; tool-call and tool-result messages are created atomically.

## Design Direction

- Treat Chatbot timeline rendering as an Agent Harness-owned projection:
  - persisted Agent Messages and Tool Call rows are inputs
  - visible Chatbot Events are outputs
- Introduce an EventList concept in Chatbot UI rather than continuing a strict MessageList mental model.
- Chatbot UI should render Chatbot Events and avoid inspecting storage rows for message pairing or tool semantics.
- Tool execution should project to one Chatbot Tool Event:
  - request-only state: visible pending/running row
  - request plus result state: visible final row with Harness-provided summary and expandable result detail
- Do not merge persisted storage rows just to match UI shape.
- Avoid multi-level fallback matching. Prefer one explicit pairing contract per input mode.
- Tool event summary text, status language, and result detail content should be produced by Agent Harness, not reconstructed by Chatbot widgets.

## Pairing Contract Candidate

- Snapshot projection:
  - use `AgentToolCallRow.request_message_id` and `AgentToolCallRow.result_message_id` as the authoritative pairing source.
- Incremental projection:
  - create or update Chatbot Events by persisted message kind.
  - for `TOOL_CALL`, create a pending tool event.
  - for `TOOL_CALL_RESULT`, complete the matching tool event according to the Agent Harness ordering invariant or explicit tool-call link.
  - This relies on the invariant that a tool-call result is emitted after its corresponding tool-call message and before another unrelated result in that turn.
- If this invariant is too implicit, promote it into Agent Harness TDD before implementation rather than adding heuristic fallback logic.

## Naming And Boundary Notes

- `AgentToolCallRow` is a storage row for Agent Harness domain state, not UI state.
- The larger boundary smell is not the word `Agent`; it is that Chatbot UI currently receives and reasons about storage rows directly through `ThreadSnapshot`.
- The cleaner direction is to introduce an Agent Harness-owned Chatbot Event projection before rendering, so storage row naming and pairing logic do not leak into widget logic.
- Renaming storage models should only happen if the domain owner language changes, because that can affect migrations, repositories, and tests.

## Unknowns

- Exact API shape for the Agent Harness-owned Chatbot Event projection.
- Whether existing `ThreadSnapshot` should stay available for non-UI callers while Chatbot switches to a projected timeline DTO.
- Whether the current harness invariant that tool-call result follows the matching tool-call is already documented strongly enough.
- Exact icon taxonomy for tool types.
- Exact summary grammar source for succeeded, failed, cancelled, and pending tool events.

## Constraints Observed

- Do not start implementation until the user explicitly says to start.
- Avoid monofile task packet structure; split exploration, design, execution, and result notes as the task matures.
- Do not use turn dividers as a separate Chatbot Event unless a product need returns.
- Keep current persisted Agent Harness semantics unless a durable owner change is explicitly confirmed.

## Candidate Paths

1. UI-local projection only
   - Build Chatbot Event projection inside `ThreadDetailView`.
   - Lowest initial blast radius.
   - Risk: UI keeps too much domain pairing logic.
   - Current status: disfavored after user confirmation that Agent Harness should own projection.

2. Dedicated Chatbot timeline projection adapter
   - Add a small projection helper in Agent Harness or its service boundary.
   - Both snapshot render and incremental apply use the same event semantics.
   - Better fit for EventList direction.
   - Current status: preferred shape.

3. Service-owned Chatbot timeline DTO
   - Agent-facing service emits UI-ready events instead of raw storage rows.
   - Strongest boundary, but higher blast radius and may be premature for this slice.
   - Current status: viable if the projection helper naturally wants a public DTO.

## Verification Anchors

- Existing UI tests for message rendering and tool-call rendering should be updated.
- Add coverage that a request-only tool call renders a pending tool item.
- Add coverage that a tool-call plus result renders one visible tool item, not two bubbles.
- Add coverage that failed results show `Failed to ...` style summary.
- Add coverage that chevron expands and collapses result detail.
- Preserve assistant message streaming update-by-id behavior.

## Smallest Confirmation Needed

- Confirm the exact Agent Harness projection API shape.
- Confirm whether `AgentToolCallRow` naming itself is in scope, or whether the immediate target is removing storage-row reasoning from UI rendering.
- Confirm the initial icon taxonomy and summary wording for known tool families.

## Promotion Candidate Truths

- Prefer making the underlying contract explicit over stacking fallback heuristics.
- Chatbot timeline items are Chatbot Events; persisted Agent Messages are not necessarily one-to-one with visible UI items.
- Tool-call request and result remain separate persisted Agent Harness records but project to one visible Chatbot Tool Event.
- Agent Harness should own Chatbot Event projection and tool-event descriptive text; Chatbot UI should render projected events rather than reconstructing tool semantics.
