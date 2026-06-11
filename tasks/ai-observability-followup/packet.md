# AI Observability Follow-Up

## Objective & Hypothesis

- Objective: design the next AI observability slice for Xenix so future public-beta diagnosis, user experience tuning, and token-cost optimization are based on trustworthy Agent facts rather than vendor-specific telemetry state.
- Hypothesis: the Agent Harness should own AI telemetry projection because it owns `Thread`, `Turn`, `AgentRun`, `ProviderRequest`, `ToolCall`, contextual tool exposure, retries, cancellation, and token usage aggregation. LLM Service should remain a request router and provider-construction boundary.

## Current State

- Current Understanding: runtime telemetry is already OTel-first with `structlog` JSON logs and optional OTLP export. The next upgrade is not general runtime observability; it is AI behavior observability. The collection-layer gap matrix now separates existing facts, direct projections, missing collection facts, and analysis-layer exclusions.
- Active Mode or Transition Note: Execute for P0 collection gaps.
- Next Step: review implemented P0 collection coverage and decide whether P1 streaming/schema/result-size gaps should follow.

## Guardrails Touched

- Agent Harness owns provider-facing conversation projection and provider request records.
- LLM Service owns provider configuration, model routing, `fq_model_key`, and provider construction, but not turn-level AI behavior semantics.
- OpenTelemetry remains the export-neutral observability substrate.
- Existing Agent storage models should be reused as observability facts where possible.
- Raw prompt, completion, tool arguments, tool results, dataset values, local paths, and raw provider payloads must not be remotely exported by default.

## User-Confirmed Constraints

- The main goal is better AI observability because it is core to future user experience and token-consumption optimization.
- Prompt/completion/tool payload capture should follow the recommended posture: disabled for public beta remote export by default; local/dev opt-in can be discussed.
- Token attribution should start with the recommended minimum: provider request, request kind, exposed tools, loop step, retries, guard, latency, and usage.
- The user does not yet have a working definition of eval; define it in project terms before deciding scope.
- Eval is not a collection-layer responsibility. It belongs to the later analysis layer after trustworthy AI traces and request facts exist.
- AI telemetry instrumentation boundaries should be at Agent Harness because that layer owns thread and turn. LLM Service is essentially an LLM request router.

## Current Facts

- `AgentProviderRequestRow` records one provider call with input message ids, output message ids, request kind, status, provider/model metadata, and usage payload when available.
- `AgentToolCallRow` records tool execution metadata and result status.
- `AgentRunRow` records an orchestration attempt for a turn.
- `AgentTurnCompletionGuardRow` records guard decisions.
- Existing OTel spans already cover `agent.turn`, `agent.provider_request`, and `agent.tool_call` at a basic level.
- Chatbot usage overview already projects token usage from provider request rows instead of inferring it from UI state.

## Unknowns

- Which first implementation details are needed for traces/cost/latency/reliability without crossing into eval analysis.
- Whether local/dev prompt and tool payload capture should be implemented as a first-class opt-in mode in the same slice.
- Whether token attribution needs provider-native token counts only, local estimation, or both.
- Which semantic convention should govern AI spans: OTel GenAI semantic conventions, OpenInference conventions, or a small compatibility layer over both.
- Whether Phoenix should be the first verification backend, or only one of several manual OTLP targets.

## Verification

- For this packet: confirm the discussion state is captured and can guide the next conversation.
- For future implementation: targeted Agent Harness tests must prove AI telemetry uses existing records, does not export raw sensitive content by default, and remains backend-neutral.

## Supporting Files

- `discussion.md`: current reasoning, eval explanation, maintainability boundary, and open design axes.
- `collection-gap-matrix.md`: collection-layer matrix for existing AI facts, direct projections, missing gaps, and explicit non-collection analysis concerns.
- `p0-implementation-plan.md`: proposed implementation slices for closing the P0 collection gaps.
- `execution.md`: implementation notes and verification outcomes for the executed P0 slice.
- `decision-log.md`: dated decisions and working assumptions.
