# AI Observability Collection Gap Matrix

## Purpose

Define the collection-layer gaps that must be closed before Xenix can do serious AI experience diagnosis and token-consumption optimization.

This matrix is collection-only. It does not assign quality scores, run judge models, or decide whether an answer is good. Those are analysis-layer responsibilities.

## Reading Guide

- Existing fact source: durable Xenix model, lifecycle transition, or current OTel signal already present.
- Direct projection: facts that can be exported from existing state without new persisted data.
- Collection gap: missing facts that the Agent Harness likely needs to record or project.
- Explicit non-collection: facts or judgments that should stay out of the collection layer.
- Priority:
  - P0: needed to make AI trace and token cost diagnosis basically useful.
  - P1: needed for reliable optimization and backend analysis.
  - P2: useful later, but not required to close the first AI O11y gap.

## Matrix

| Area | Diagnostic Question | Existing Fact Source | Direct Projection Available Now | Collection Gap | Explicit Non-Collection | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| Turn causality | Which user turn did this AI work belong to? | `AgentTurnRow`, `AgentRunRow`, active `agent.turn` span | `agent.turn` count/status metric | Add safe turn/run correlation on spans, preferably ids hashed or local-only according to privacy policy | User intent quality judgment | P0 |
| Agent loop step | Which loop iteration caused this provider request? | `step_state["used_steps"]` in Harness runtime | Not persisted/exported today | Add loop step index to provider request span/summary | Whether the loop step was "good" | P0 |
| Provider request identity | Which provider request produced this cost/latency? | `AgentProviderRequestRow.id`, input/output message ids | Provider span exists with provider, request kind, model hash | Add safe request id correlation and parent turn/run context | Raw request payload | P0 |
| Request kind | Was this primary model work or guard work? | `AgentProviderRequestKind` | Already persisted and exported on provider span | None for basic trace | Guard quality scoring | P0 |
| Provider/model | Which provider/model family is slow or costly? | `provider_name`, `model`, selected `fq_model_key` | Provider name and model hash on span | Decide whether to add model family or normalized model class bucket | Raw model key if treated as sensitive/high-cardinality | P0 |
| Request status | Did the provider request succeed, fail, cancel, or miss usage? | `AgentProviderRequestStatus`, `usage_payload` | Count/duration metric by status | Add usage-present boolean/status and explicit failure/cancel stage | Error message content | P0 |
| Provider latency | How long did each provider request take? | `created_at`, `completed_at`; span duration | Histogram exists | Ensure streaming and non-streaming use equivalent timing semantics | Subjective slowness score | P0 |
| Streaming responsiveness | How long until the first visible provider event/token? | Streaming loop knows first stream event and first delta timing | Not exported today | Capture time-to-first-event and time-to-first-text/delta where available | Whether the answer felt responsive enough | P0 |
| Output completion | Did the provider produce text, tool calls, both, or nothing? | `ProviderResponse`, output message ids, tool call creation | Indirectly available after snapshot inspection | Add output shape summary: assistant text present, tool call count, empty response flag | Raw assistant completion | P0 |
| Token totals | How many tokens did this request consume? | `usage_payload` normalized from provider usage | Chatbot turn usage overview; persisted payload | Add OTel attributes/metrics for input/cached/output/total token counts with request kind/status | Cost optimization recommendation | P0 |
| Usage missing | Which providers/models do not report usage? | `usage_payload is None` | Indirectly known from persisted row | Export usage-present/missing metric | Local token estimation as truth | P0 |
| Input message shape | What kind of context inflated input tokens? | `provider_messages`, message ids and roles | Not summarized today | Add request-shape summary: total message count, role counts, system present, tool result present | Raw message content | P0 |
| History growth | Is context growing across turns? | Thread snapshot messages and provider input message ids | Not exported today | Add message count and approximate input context size buckets per request | Conversation semantic summary | P1 |
| Tool exposure | Which tools were exposed to the model for this request? | `tool_specs` from `_tool_specs_for_context` | Not persisted/exported today | Add exposed tool count, tool categories, and optionally tool names if cardinality accepted | Whether tool exposure was optimal | P0 |
| Tool schema cost | Are tool schemas consuming too much input budget? | `AgentToolSpec` schemas exist at request assembly | Not measured today | Add schema byte size and/or estimated token bucket per provider request | Full tool schema body in remote telemetry | P1 |
| Tool call execution | Which tools were actually called and how long did they take? | `AgentToolCallRow`, tool call span, duration metric | Tool name/status/duration already exported | Add parent provider request/loop context if missing | Whether the chosen tool was correct | P0 |
| Invalid tool call | Did provider call a tool that was not exposed? | `_validate_provider_tool_calls` failure path | Provider request marked failed | Add explicit invalid-tool-call reason/category and unknown tool count/name hash | Raw provider tool arguments | P0 |
| Tool result size | Are tool results bloating later context? | `ToolCall.result_payload`, provider-facing projection | Not measured today | Add result payload size bucket and provider-facing tool-result text size/token estimate bucket | Raw tool result payload, dataset values | P1 |
| Tool failure | Which tool failures create bad AI turns? | `AgentToolCallStatus`, `error_summary`, exception type | Tool count/duration metric with status/error type | Ensure failure stage and error type are exported without raw message | Eval of final answer after failure | P0 |
| Guard behavior | How often does guard run, continue, fail, or add retry context? | `AgentTurnCompletionGuardRow`, guard provider request | Guard request kind persisted; rows persisted | Add guard verdict counters and retry/attempt index projection | Judge whether guard verdict was correct | P1 |
| Retry / continuation | How many provider requests were caused by guard continue or loop continuation? | Guard action creates system reminder and loop continues | Not explicit in telemetry | Add retry/continuation reason and attempt index | Whether retry improved quality | P1 |
| Step budget | Did the turn pause because the step budget was exhausted? | `StepBudgetPause`, `AgentRunStatus.AWAITING_CONFIRMATION`, usage payload | Agent turn metric can record awaiting confirmation | Add step budget state: used/granted/max buckets and pause count | Whether user should have granted more steps | P1 |
| Cancellation | Where was the run cancelled? | `AgentRunCancelled`, message/tool/provider status updates | Turn/provider/tool statuses are persisted/exported partly | Add cancellation stage: before provider, during provider, during tool, after response | User cancellation intent analysis | P1 |
| Title generation | How much AI work is spent on auto title generation? | Thread title provider path | Likely not part of current provider request rows | Decide whether title generation should create provider request records or stay outside AI O11y v1 | Title quality eval | P2 |
| Provider raw payload | Can we inspect provider-specific details? | Assistant message/provider payload can persist raw payload in app state | Not exported remotely by design | Keep out of default remote export; optional local diagnostic bundle policy can be separate | Remote raw payload export | P2 |
| Content capture | Can dev reproduce exact prompts and outputs? | Messages, tool payloads, provider payloads exist locally | Local state has content | Optional explicit local/dev capture mode; not required for beta remote telemetry | Default remote prompt/completion/tool content export | P2 |
| Backend compatibility | Can Phoenix/OpenLIT/Langfuse understand the spans? | Current spans are Xenix-named | Basic OTel transport exists | Choose semantic projection: OTel GenAI, OpenInference, or compatibility layer | Vendor-specific trace model in Harness | P0 |
| Analysis readiness | Can later eval/cost analysis run on collected facts? | Harness facts and future AI trace summaries | Partial | Ensure collection preserves causality, shape, usage, latency, and status facts | Eval score, judge-model decision, human rating | P0 |

## P0 Gap Summary

Close these first:

1. Add safe turn/run/provider-request correlation to AI spans.
2. Add loop step index and request attempt context.
3. Add provider request output shape.
4. Export token usage as AI metrics/span attributes, including usage-missing.
5. Add request input shape summary: message count, role counts, system present, tool result present.
6. Add tool exposure summary: exposed tool count and categories.
7. Add invalid tool call reason/category.
8. Ensure tool call spans correlate to parent provider request/turn.
9. Select an AI semantic projection target that remains backend-neutral.

## P1 Gap Summary

Close after P0:

1. Add streaming responsiveness metrics: time-to-first-event and time-to-first-text.
2. Add tool schema size/token estimate bucket.
3. Add tool result size/token estimate bucket.
4. Add guard verdict and guard retry/attempt counters.
5. Add step-budget and cancellation-stage projection.
6. Add history growth buckets across turns.

## Explicitly Out Of Collection Layer

- Eval scores.
- Judge-model decisions.
- Human ratings.
- Prompt quality judgments.
- Whether a tool call was semantically correct.
- Whether an answer was grounded, unless represented later as analysis output.
- Cost optimization recommendations.

The collection layer must make these analyses possible later, but should not perform them.

## Likely Implementation Shape

This is a design hypothesis, not an implementation instruction.

- Add a small Agent-owned AI observability projection helper, called only from Agent Harness.
- Keep `xenix.observability` as the OTel/metric/log substrate, not the AI semantics owner.
- Reuse `AgentProviderRequestRow`, `AgentToolCallRow`, `AgentRunRow`, and snapshot-derived request state.
- Avoid new storage rows unless request-shape summaries need to survive beyond OTel/log export and diagnostic bundles.
- Keep backend-specific SDKs out of Harness.
