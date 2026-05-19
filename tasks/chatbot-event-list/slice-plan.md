# Chatbot EventList Slice Plan

## Target Shape

Agent Harness remains the owner of persisted conversation semantics and becomes the owner of Chatbot timeline projection.

```text
Agent Harness persisted records
  Thread / Turn / Message / ToolCall / AgentRun
        |
        v
Agent Harness ChatbotEvent projection
  ChatbotTextEvent
  ChatbotToolEvent
  ChatbotControlEvent, if needed later
        |
        v
Chatbot UI EventList
  render event widgets only
  keep visual local state such as expanded/collapsed rows
```

The target state is not "two messages are merged in storage." The target state is "two persisted tool-call messages project into one Chatbot tool event."

## Current State

- Agent Harness exposes `ThreadSnapshot` with raw storage rows.
- Agent Harness stream emits message-centric events:
  - `message_created`
  - `message_updated`
  - `message_finalized`
- Chatbot UI renders `ThreadSnapshot.messages` and applies message rows directly.
- Tool-call and tool-call-result messages render as separate `ChatMessageBubble` instances.
- Tool result presentation is partly implicit in generic content blocks and partly reconstructed in UI.
- Turn dividers are inserted by UI based on user-message count.

## Target Invariants

- Chatbot UI consumes Chatbot Events, not storage rows.
- Agent Harness owns ChatbotEvent projection, including:
  - event identity
  - event kind
  - visible ordering
  - tool-call pairing
  - tool icon key
  - summary text
  - status wording
  - expandable result detail
- Tool-call request and result remain separate persisted records.
- A request-only tool-call record projects to a visible pending tool event.
- A request plus result projects to one final tool event.
- Tool-event descriptive text belongs to Agent Harness because it can be reused for LLM-facing tool result context.
- Assistant message streaming remains the only true streaming text path.
- EventList upsert should be uniform enough that UI does not maintain separate "streaming renderer" and "non-streaming renderer" architectures.
- Turn dividers are not Chatbot Events in this target.

## Slice 0: Durable Contract Solidification

### Goal

Update durable TDD language before implementation so the ownership shift is explicit.

### Changes

- `docs/30-unit-tdd/agent-harness.md`
  - Add ChatbotEvent projection to Agent Harness ownership.
  - Replace or narrow "Chatbot timeline changes are message-centric events" with a transition target.
  - Document the tool-call pairing invariant.
  - Document that tool result summary/detail text is Harness-owned.
- `docs/30-unit-tdd/chatbot-ui.md`
  - Rename the rendering model from MessageList to EventList conceptually.
  - State that UI renders Chatbot Events and does not inspect storage rows for tool pairing.
  - Remove turn-divider requirement unless retained as pure layout styling.

### Verification

- Doc review only.
- No code behavior changes.

### Risk

- Low implementation risk, but high conceptual importance. Skipping this makes later code changes ambiguous.

## Slice 1: Agent Harness ChatbotEvent Projection DTO

### Goal

Create the projection contract while keeping current UI behavior untouched.

### Changes

- Add Agent Harness DTOs, likely under `src/xenix/services/agent/`:
  - `ChatbotEventKind`
  - `ChatbotEventStatus`
  - `ChatbotEvent`
  - `ChatbotToolEventPayload` or equivalent structured payload
- Add projection function or service method:
  - `project_chatbot_events(snapshot: ThreadSnapshot) -> list[ChatbotEvent]`
  - or `ThreadSnapshot.chatbot_events()`
- Use `AgentToolCallRow.request_message_id` and `result_message_id` as authoritative pairing in snapshot projection.
- Preserve request-only tool calls as pending tool events.
- Preserve user and assistant message events as one-to-one text events.
- Hide system messages from normal EventList projection unless a future control event needs them.

### Verification

- Unit tests for projection:
  - user and assistant messages project in order
  - tool request only projects one pending tool event
  - tool request plus result projects one final tool event
  - failed result uses Harness-owned failure summary
  - system messages stay hidden

### Risk

- Medium. This introduces a new contract but does not yet move UI.

## Slice 2: Harness-Owned Tool Presentation Text

### Goal

Make tool summary and result detail first-class Harness presentation data instead of widget-derived strings.

### Changes

- Define a stable presentation mapping for known tool names:
  - `data.peek`
  - `data.integrate`
  - `data.clean`
  - `data.feature.select`
  - `model.metadata`
  - `model.train`
  - `model.hyper_train`
  - `model.inference`
- Produce:
  - `icon_key`
  - pending summary
  - success summary
  - failure summary using `Failed to ...`
  - cancelled summary
  - expandable detail blocks
- Decide whether this presentation data is stored in message content blocks at creation time, derived at projection time from tool records, or both.

### Preferred Direction

- Store durable descriptive text in Harness-created tool-call-result content blocks when it is LLM-relevant.
- Derive UI-only fields such as `icon_key` during ChatbotEvent projection if they are not meaningful to the LLM.

### Verification

- Agent Harness tests prove result message content includes stable summary/detail.
- Projection tests prove the same summary appears in ChatbotToolEvent.
- Provider message projection still receives useful tool result text.

### Risk

- Medium-high. This touches the LLM-facing result content contract, so wording must be useful and not only decorative.

## Slice 3: Incremental Stream Event Projection

### Goal

Let running turns update the UI through Chatbot Events rather than raw message rows.

### Changes

- Keep provider deltas internal.
- Preserve assistant message streaming as Harness updates to one assistant event.
- When tool-call message is created, emit or expose a pending ChatbotToolEvent.
- When tool-result message is created, emit or expose the completed ChatbotToolEvent.
- Prefer adding event-shaped data while keeping old message event fields temporarily for compatibility.

### Verification

- Existing assistant streaming tests still pass.
- New tests prove:
  - tool-call event appears before result exists
  - result updates/replaces the same logical tool event
  - no duplicate tool event appears after final snapshot convergence

### Risk

- High enough to isolate after snapshot projection is stable.

## Slice 4: Chatbot UI EventList Migration

### Goal

Move `Chatbot` from message rendering to event rendering.

### Changes

- Replace direct `ThreadSnapshot.messages` rendering with projected events.
- Replace `_message_bubbles_by_id` with event-widget tracking keyed by ChatbotEvent id.
- Add `ToolCallItem` widget:
  - tool-type icon
  - summary text
  - chevron button
  - expandable detail area
- Preserve `ChatMessageBubble` for user and assistant text events, or rename later after behavior is stable.
- Remove turn-divider insertion logic from the event rendering path.

### Verification

- Qt tests prove:
  - user and assistant messages still render
  - assistant streaming updates one visible item
  - tool request only renders one pending compact item
  - tool request plus result renders one compact item
  - failed tool event shows `Failed to ...`
  - chevron expands/collapses detail
  - artifact links still activate from expanded details if present

### Risk

- Medium. Most risk is layout and event identity churn in existing tests.

## Slice 5: Cleanup And Compatibility Removal

### Goal

Remove old message-list assumptions after EventList is proven.

### Changes

- Rename internal UI fields where helpful:
  - message list -> event list
  - message layout -> event layout
  - message widget map -> event widget map
- Remove obsolete tests that assert `chatMessageTool` bubbles.
- Remove any temporary compatibility adapter that lets UI consume raw messages.
- Keep storage model names, including `AgentToolCallRow`, unless a separate domain migration is approved.

### Verification

- Full focused test run for Agent Harness and Chatbot UI.
- Manual app smoke if UI changes are substantial.

### Risk

- Low to medium. Mostly mechanical, but should happen only after behavior is covered.

## Recommended Sequence

1. Slice 0: Durable Contract Solidification
2. Slice 1: Agent Harness ChatbotEvent Projection DTO
3. Slice 2: Harness-Owned Tool Presentation Text
4. Slice 3: Incremental Stream Event Projection
5. Slice 4: Chatbot UI EventList Migration
6. Slice 5: Cleanup And Compatibility Removal

Slices 1 and 2 can be adjacent but should not be collapsed into one large change. Slice 1 proves structure; Slice 2 proves wording and LLM-facing content.

## Open Decisions

- Should `ThreadSnapshot` expose `chatbot_events()` or should projection live in a separate `ChatbotTimelineProjector`?
- Should stream events gain a new `chatbot_event` field, or should new event kinds replace message events after migration?
- Should tool summary/detail be persisted in content blocks, generated during projection, or persisted plus projected?
- What is the initial icon taxonomy and exact `icon_key` vocabulary?
