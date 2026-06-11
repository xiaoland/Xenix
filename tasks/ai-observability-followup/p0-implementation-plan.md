# AI Observability P0 Implementation Plan

## Purpose

Plan the first implementation slice that closes the P0 AI observability collection gaps.

This is still a planning artifact. It does not authorize code changes by itself.

## P0 Definition

P0 means the minimum collection layer needed for useful AI trace and token-cost diagnosis:

- preserve agent causality
- explain provider request cost and latency
- explain context/request shape without raw content
- correlate tools, guard work, failures, and cancellation to the turn
- emit backend-neutral OTel-compatible AI signals

P0 does not include eval, judge-model scoring, human rating, quality judgment, or optimization recommendation.

## Scope Boundary

### Owner

Agent Harness owns the AI observability projection.

It owns the state needed to explain:

- `Thread`
- `Turn`
- `AgentRun`
- `ProviderRequest`
- `ToolCall`
- contextual tool exposure
- loop step
- guard/retry behavior
- cancellation and step-budget state

### Non-Owner

LLM Service remains a provider router and provider-construction boundary.

It should not own:

- turn semantics
- trace hierarchy
- token attribution
- tool exposure attribution
- eval state
- AI behavior diagnosis

### Substrate

`xenix.observability` remains the OTel/log/metric substrate. It should not become the owner of Agent semantics.

## Slice P0.1: Agent Correlation Envelope

### Goal

Every AI span and metric should be attributable to the same safe Agent execution context.

### Covers Matrix Gaps

- Turn causality
- Provider request identity
- Tool call parent context
- Analysis readiness

### Likely Work

- Add an Agent-owned helper that builds safe correlation attributes from Harness state.
- Attach correlation to:
  - `agent.turn`
  - `agent.provider_request`
  - `agent.tool_call`
- Decide id policy:
  - remote export: hash or omit raw ids
  - local logs/diagnostic bundle: raw ids may be acceptable if already local-only

### Candidate Facts

- `agent.turn.id_hash`
- `agent.run.id_hash`
- `agent.provider_request.id_hash`
- `agent.tool_call.id_hash`

### Verification

- Tests prove provider request and tool call spans receive correlation attributes.
- Tests prove raw ids are not exported when remote-safe attributes are expected.
- Existing Agent Harness tests still pass.

## Slice P0.2: Provider Request Shape Summary

### Goal

Explain why input tokens grow without exporting raw message content.

### Covers Matrix Gaps

- Agent loop step
- Input message shape
- History growth baseline
- Request kind
- Provider/model

### Likely Work

- At provider request creation time, compute a safe request-shape summary from `provider_messages` and `step_state`.
- Attach summary attributes to the provider request span.
- Optionally persist a compact summary only if later diagnostic bundles need it.

### Candidate Facts

- loop step index
- request kind
- provider name
- model hash
- model family or model bucket if available
- provider message count
- system message present
- user message count
- assistant message count
- tool result message count
- tool call message count

### Verification

- Tests cover first-turn request shape.
- Tests cover multi-step request shape after a tool call.
- Tests cover guard request shape separately from primary request shape.
- Tests prove message content is not included.

## Slice P0.3: Tool Exposure Summary

### Goal

Explain provider request input burden and tool-choice context without exporting full tool schemas.

### Covers Matrix Gaps

- Tool exposure
- Tool schema cost baseline
- Backend compatibility

### Likely Work

- Summarize `tool_specs` immediately after contextual tool selection.
- Attach summary to provider request span.
- Keep full schema out of remote telemetry.

### Candidate Facts

- exposed tool count
- exposed tool category counts, such as `data`, `analysis`, `model`
- optional tool name list only if cardinality/privacy policy accepts it
- tool schema byte-size bucket

### Verification

- Tests cover no-file initial request tool exposure.
- Tests cover post-dataset tool exposure.
- Tests prove full schema JSON is not exported.

## Slice P0.4: Token Usage Projection

### Goal

Make provider-reported token usage available to OTel backends, not only Chatbot UI.

### Covers Matrix Gaps

- Token totals
- Usage missing
- Request status

### Likely Work

- Extend provider request completion projection.
- Record token attributes and metrics from `AgentProviderRequestRow.usage_payload`.
- Emit explicit usage-present/usage-missing signal.

### Candidate Facts

- input tokens
- cached input tokens
- output tokens
- total tokens
- usage present
- provider request status
- request kind
- provider name
- model hash or model bucket

### Verification

- Tests cover usage-present provider request.
- Tests cover usage-missing provider request.
- Tests cover failed/cancelled provider request without token payload.
- Tests prove `provider_usage` raw nested payload is not exported.

## Slice P0.5: Provider Output Shape And Invalid Tool Calls

### Goal

Explain whether a provider request produced text, tools, both, nothing, or an invalid tool call.

### Covers Matrix Gaps

- Output completion
- Invalid tool call
- Tool failure setup

### Likely Work

- Summarize provider response shape before persistence completes.
- Add explicit invalid-tool-call failure category around `_validate_provider_tool_calls`.
- Avoid exporting tool arguments or assistant text.

### Candidate Facts

- assistant text present
- assistant output block count
- tool call count
- empty provider response
- invalid tool call count
- invalid tool name hash or category, if useful and privacy-safe
- failure category

### Verification

- Tests cover text-only response.
- Tests cover tool-only/tool-call response.
- Tests cover empty response.
- Tests cover unexposed tool call rejection.
- Tests prove assistant text and tool arguments are not exported.

## Slice P0.6: Tool Call Context Completion

### Goal

Make tool execution cost and failure understandable inside the same turn/provider-request chain.

### Covers Matrix Gaps

- Tool call execution
- Tool failure
- Turn causality

### Likely Work

- Attach parent turn/run/provider request correlation to tool spans/metrics.
- Keep existing tool name/status/duration metrics.
- Add safe failure stage/category if available.

### Candidate Facts

- tool name
- tool category
- status
- duration
- error type
- parent provider request hash
- loop step index

### Verification

- Tests cover successful tool call telemetry attributes.
- Tests cover failed tool call telemetry attributes.
- Tests cover cancelled tool call telemetry attributes.
- Tests prove result payload and error summary are not exported.

## Slice P0.7: Semantic Projection Target

### Goal

Make AI telemetry understandable by Phoenix/OpenLIT/Langfuse-style backends without introducing backend-specific SDK ownership.

### Covers Matrix Gaps

- Backend compatibility
- Analysis readiness

### Likely Work

- Choose one of:
  - OTel GenAI semantic conventions
  - OpenInference conventions
  - a compatibility projection that can map to both
- Keep Xenix-owned helper names stable even if semantic attributes evolve.
- Document attribute policy before broad instrumentation.

### Verification

- Tests assert the selected semantic attributes are emitted.
- Manual verification target can use Phoenix first, but code must remain backend-neutral.

## Recommended Execution Order

1. P0.7 Semantic Projection Target
2. P0.1 Agent Correlation Envelope
3. P0.2 Provider Request Shape Summary
4. P0.3 Tool Exposure Summary
5. P0.4 Token Usage Projection
6. P0.5 Provider Output Shape And Invalid Tool Calls
7. P0.6 Tool Call Context Completion

Reasoning:

- semantic target and correlation should be settled before adding many attributes
- request shape and tool exposure explain input-side cost
- token usage makes cost visible in backends
- output shape and invalid tool calls explain provider behavior
- tool call completion closes the causal chain

## Non-Goals

- No eval scoring.
- No judge model.
- No human rating surface.
- No prompt/completion/tool-argument remote export by default.
- No vendor SDK in Harness.
- No new storage rows unless request-shape summaries need offline diagnostic persistence.
- No UI interaction telemetry.

## Open Questions Before Execution

1. Should remote-safe correlation use hashed ids everywhere, or should spans omit ids and rely only on trace/span hierarchy?
2. Should tool names be exported, or should P0 start with category/count only?
3. Should request-shape summaries be persisted in `AgentProviderRequestRow`, or remain OTel/log-only in P0?
4. Should P0 include streaming responsiveness now, even though it was listed as P1 in the gap matrix?
5. Which semantic target should be selected first: OTel GenAI, OpenInference, or a small compatibility layer?

## Acceptance Criteria

- A Phoenix or generic OTLP backend can show one turn as a coherent trace.
- Each provider request can be inspected for request kind, loop step, provider/model bucket, input shape, tool exposure, output shape, status, duration, and token usage when available.
- Tool calls are visibly attached to the causality chain.
- Usage-missing providers are measurable.
- Invalid tool calls are distinguishable from ordinary provider failures.
- No raw prompt, completion, tool arguments, tool results, dataset values, local paths, or raw provider payloads are exported by default.
