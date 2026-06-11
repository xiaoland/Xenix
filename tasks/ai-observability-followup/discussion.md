# AI Observability Discussion

## Reframed Goal

The goal is AI observability, not a larger runtime telemetry surface.

Xenix needs to answer:

- Why did this turn feel slow, expensive, repetitive, or wrong?
- Where did input and output tokens go?
- Which part of the agent loop produced useful work versus waste?
- Which models, tools, guard decisions, retries, and failures are correlated with poor experience?
- What should be optimized first: prompts, tool schema size, tool result shape, history window, model choice, guard behavior, or tool reliability?

## What Eval Means Here

In this project context, `eval` means a structured judgment about AI behavior quality.

It is not ordinary ML model evaluation such as accuracy, precision, recall, or ROC-AUC for trained scikit-learn models. It is closer to asking:

- Did the assistant answer the user's actual business intent?
- Did it call the right tool when a tool was needed?
- Did it avoid unnecessary tool calls?
- Did it produce an artifact link when a task created an artifact?
- Did it stop correctly, or did it claim it would continue while doing nothing?
- Was the response grounded in tool results instead of inventing facts?
- Was the chosen model/tool path cost-effective for the task?

Eval can be produced by humans, deterministic rules, or a judge model. It can attach to a turn, provider request, tool call, or final assistant answer. It is not a collection-layer responsibility. The collection layer should preserve enough trace and request facts for a later analysis layer to evaluate behavior quality.

## Recommended First Scope

First AI observability slice:

- Trace the agent causal chain: turn, provider request, tool call, guard, retry, cancellation, step-budget pause, final status.
- Attribute token usage by provider request and request kind.
- Record enough request-shape facts to explain token growth without capturing raw content.
- Capture latency and reliability signals at each Harness-owned boundary.
- Keep raw prompt, completion, tool arguments, tool results, and provider payload out of remote export by default.

Later analysis-layer candidate:

- Add eval surfaces after traces are trustworthy.
- Start with deterministic or Harness-derived eval markers before judge-model eval.

## Maintainability Boundary

Working claim: AI telemetry projection belongs in Agent Harness.

Reasons:

- Harness owns `Thread`, `Turn`, `AgentRun`, `ProviderRequest`, and `ToolCall`.
- Harness builds provider messages from persisted snapshots.
- Harness decides contextual tool exposure.
- Harness owns retries, guard calls, cancellation, step-budget pause/resume, and turn completion.
- Harness is the only layer that can explain why a provider request happened in the surrounding agent loop.

LLM Service should stay narrow:

- Provider configuration.
- Configured model lists.
- `fq_model_key` generation and parsing.
- Provider construction.
- Provider adapter request/response normalization.

LLM Service may expose provider-level facts, but it should not own turn semantics, trace hierarchy, cost attribution, eval state, or AI behavior diagnosis.

## Projection Pattern

AI telemetry should be a projection from existing Harness facts.

Preferred flow:

```text
Agent Harness record/state transition
  -> AI observability projection
  -> OTel span/metric/log attributes
  -> backend-neutral export
  -> Phoenix/OpenLIT/Langfuse/Collector analysis
```

Avoid:

```text
Vendor SDK callback
  -> vendor trace object
  -> inferred Agent semantics
  -> parallel truth beside Harness storage
```

## Request-Shape Facts Worth Discussing

These are candidate safe facts, not final field names:

- request kind: primary or guard
- loop step index or retry index
- provider name
- model family or model hash
- number of provider messages
- counts by message role
- whether system prompt is present
- whether tool result messages are present
- number of exposed tools
- broad tool categories exposed
- tool schema byte size or token estimate bucket
- provider usage presence
- input, cached input, output, and total token counts when provider-reported
- time to first provider event for streaming
- provider request duration
- final status and error type

## Privacy Posture

Default public-beta remote export should not include:

- raw prompts
- assistant completions
- tool arguments
- tool result payloads
- dataset values
- column values
- local file paths
- provider API keys or credentials
- raw provider payloads
- raw exception messages that may contain data or paths

Local/dev opt-in content capture can remain open for discussion, but it must be explicit, visibly configured, and easy to disable.

## Platform Fit Implication

Phoenix remains the strongest first backend candidate for local AI trace/eval work because it can receive OTel traces and is lightweight enough for development verification.

OpenLIT remains valuable as an OTel-native AI instrumentation reference.

Langfuse remains valuable later if Xenix needs a broader LLMOps surface such as prompt management, datasets, scores, and collaborative evaluation workflows.

The backend decision should not leak into Harness code. Harness should project backend-neutral OTel-compatible AI spans.

## Open Design Axes

1. AI semantic convention:
   Decide whether to target OTel GenAI semantics directly, OpenInference semantics, or a compatibility projection.

2. Token attribution depth:
   Decide whether first slice stops at provider request/request shape, or also adds local token estimation for message and tool-schema components.

3. Content capture policy:
   Decide whether dev/local opt-in raw content capture is part of first implementation or explicitly deferred.

4. Eval boundary:
   Treat eval as analysis-layer work. The collection-layer question is only what trace/request facts must exist so eval can be computed later.

5. Storage impact:
   Decide whether existing `AgentProviderRequestRow.usage_payload` and ids are enough, or whether request-shape summaries should be persisted for later offline analysis.
