# AI Observability P0 Execution

## Objective & Hypothesis

- Objective: close the P0 AI observability collection gaps while keeping Agent Harness as the owner of AI telemetry semantics.
- Hypothesis: a small Agent-owned projection helper can enrich existing OTel spans and metrics from Harness facts without introducing vendor SDK ownership or exporting raw sensitive content.

## Pre-Execution Restatement

- Target: P0 AI observability collection gaps.
- Current state and context: basic runtime telemetry already emitted `agent.turn`, `agent.provider_request`, and `agent.tool_call` spans plus provider/tool metrics. Provider request rows already persisted request kind, status, input/output message ids, provider/model metadata, and usage payload.
- Operation: add a Harness-owned AI observability projection helper, enrich Agent spans and token metrics, classify invalid tool calls, and add targeted tests.
- Scope included: correlation envelope, provider request shape, tool exposure summary, token usage projection, output shape, invalid tool-call classification, tool-call parent context, and GenAI/OpenInference-compatible metadata.
- Scope excluded: eval, judge-model scoring, human ratings, prompt/completion/tool payload export, vendor SDK integration, new storage rows, and UI telemetry.
- Invariants: Harness remains the owner of AI telemetry semantics; LLM Service remains a provider router; existing Harness records remain the source of truth; metrics avoid high-cardinality correlation ids.

## Guardrails Touched

- Agent Harness owns thread, turn, run, provider request, tool call, guard, step-budget, and cancellation semantics.
- OpenTelemetry remains the backend-neutral substrate.
- Raw prompt, completion, tool arguments, tool results, dataset values, local paths, raw provider payloads, and raw provider usage payloads must not be exported by default.
- Eval belongs to analysis layers, not the collection layer.

## Implementation Notes

- Added `src/xenix/services/agent/observability.py` as an Agent-owned projection helper.
- Added `set_span_attributes()` to `src/xenix/observability.py` so spans can be enriched after a response is known but before the span closes.
- Enriched `agent.turn` spans with Agent workflow and hashed thread/turn/run correlation.
- Enriched `agent.provider_request` spans with:
  - `gen_ai.operation.name`
  - `gen_ai.provider.name`
  - `openinference.span.kind`
  - request kind
  - stream flag
  - loop step index
  - hashed provider request/turn/run correlation
  - message role counts
  - system/tool-result presence
  - exposed tool counts and categories
  - tool schema size bucket
  - provider response shape
  - provider request status
  - usage-present and token counts when provider-reported
  - invalid-tool-call failure category/count/hash
- Enriched `agent.tool_call` spans with tool operation metadata, tool category, hashed tool-call id, parent provider request hash, and loop step.
- Added `gen_ai.client.token.usage` histogram measurements for provider-reported input/output tokens.
- Kept correlation ids off metrics to avoid high-cardinality metric streams.

## Verification

- Command: `pdm run pytest tests/test_agent_ai_observability.py -q`
- Expected: targeted AI observability projection tests pass.
- Observed: `3 passed`.

- Command: `pdm run pytest tests/test_agent_ai_observability.py tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py -q`
- Expected: new tests plus core Harness persistence/streaming tests pass.
- Observed: `35 passed`.

- Command: `pdm run check`
- Expected: compileall succeeds for `src`, `tests`, and `scripts`.
- Observed: passed.

- Command: `pdm run pytest -q`
- Expected: full suite passes.
- Observed: `221 passed`.

## Follow-Up Transport Patch

- Split OTLP export enablement by signal so Phoenix can be used as a
  traces-only backend without sending metrics to it.
- `OTEL_EXPORTER_OTLP_ENDPOINT` continues to enable traces and metrics for an
  OpenTelemetry Collector.
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` enables traces only.
- `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` enables metrics only.
- `XENIX_OTEL_EXPORT_LOGS=true` is still required before remote log export can
  be enabled.
- Added `XENIX_OTEL_EXPORT_TRACES=false` and
  `XENIX_OTEL_EXPORT_METRICS=false` override support.
- Documented that endpoint, protocol, and headers should all be configured per
  signal when different backends or API keys are used.
- Kept backend API keys on standard OTel `OTEL_EXPORTER_OTLP_<SIGNAL>_HEADERS`
  variables instead of introducing Xenix-specific telemetry secret settings.
- Verification:
  - `pdm run pytest tests/test_observability.py -q` -> `7 passed`
  - `pdm run smoke` -> passed
  - `pdm run check` -> passed
  - `pdm run pytest -q` -> `226 passed`

## Promotion Notes

- Durable truth candidates:
  - Agent Harness owns AI observability collection semantics.
  - LLM Service remains a provider router and provider-construction boundary.
  - AI collection projects safe facts from existing Harness models and runtime state; it does not create a parallel truth model.
  - Eval is analysis-layer work, not collection-layer work.
- Keep in task:
  - Exact P0 implementation sequencing and temporary verification notes.
