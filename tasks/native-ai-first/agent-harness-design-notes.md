# Agent Harness Design Notes

## Status

- Mode: Explore moving toward Solidify.
- Scope: clarify Agent Harness internal boundaries.

## External Design References

- LangGraph: useful reference for durable execution, interrupts, thread state, and replay constraints.
- Vercel AI SDK: useful reference for provider registry, typed tools, step control, and language model middleware.
- PydanticAI: useful reference for Pydantic-based tool schema, structured output validation, typed dependencies, and event streaming.

The Xenix first-slice target keeps its own canonical contracts so the Qt Native app, Agent Harness service, storage interfaces, and service boundaries remain product-owned.

## LLM Provider Boundary

Agent Harness is a service under `src/xenix/services/agent/`.

CopilotKit AIMock attaches at the LLM provider boundary.

Primary dialects for first design:

```text
AgentHarness
  -> LLMProvider
      -> OpenAIChatCompletionsV1Provider
      -> DeepSeekChatCompletionsProvider
      -> CopilotKitAIMockProvider
```

Current decision:

- OpenAI means OpenAI-compatible `/v1/chat/completions`.
- DeepSeek documents an OpenAI-compatible `/chat/completions` API with native `tools`, `tool_choice`, assistant `tool_calls`, and `tool` role responses.

## Canonical Function-Calling Contract

HarnessCore works against this provider-independent contract:

```text
FunctionCallingRequest
  thread_id
  messages: list[Message]
  tool_definitions: list[AgentToolDefinition]
  generation_config
  active_tool_names

FunctionCallingEvent
  assistant_delta
  assistant_message_ready
  tool_call_requested
  provider_usage_reported
  provider_error

FunctionCallingToolResult
  tool_call_id
  tool_name
  status
  content_blocks
  artifact_refs
  error
```

Every LLM provider dialect implements this canonical contract:

```text
LLMProvider.complete(FunctionCallingRequest) -> stream[FunctionCallingEvent]
```

Each provider dialect owns provider request assembly and provider response parsing:

```text
Canonical Messages + Tool Definitions
  -> provider-specific request assembly
  -> provider HTTP/API call
  -> provider-specific response parsing
  -> canonical FunctionCallingEvents
```

## Turn

A `Thread` is composed of `Turn` records. A turn is a bounded group of messages.

Turn invariant:

```text
Turn
  starts with exactly one user Message
  contains zero or more assistant/tool-call/tool-result/cancellation/error Messages
  ends with one explicit turn-end Message
```

Most LLM providers do not produce an explicit turn-end message. Xenix adds a reserved `turn_end` tool so the model can explicitly close the turn through normal function-calling mechanics.

Reserved tool:

```text
turn_end()
  side_effect_level: read_only
```

The Harness persists the `turn_end` tool-call Message as the visible turn divider. The paired tool-call-result Message remains durable execution evidence and stays outside the ChatBox visible projection.

## HarnessCore

`HarnessCore` is the canonical orchestration control flow inside Agent Harness.

It:

- Accepts a new user message and starts a Turn.
- Loads the thread snapshot required for the turn.
- Calls the selected `LLMProvider` through the canonical function-calling contract.
- Observes canonical events such as assistant output and tool-call requests.
- Sends each valid tool-call request to the `ToolExecutor`.
- Feeds canonical tool results back into the next provider call.
- Stops on `turn_end`, cancellation, provider error, tool error, or iteration limit.
- Emits canonical run events for UI streaming and persistence.

It owns turn progression and user-message intake. Provider-specific request assembly, provider-specific payload parsing, persistence interfaces, and business logic live in their own boundaries.

## Message Persistence Boundary

Thread, Turn, Message, tool-call, and tool-result ownership belongs to Agent Harness. Storage provides standardized persistence interfaces.

```text
AgentHarness
  -> ConversationService / MessageStore
      -> creates user Message
      -> loads ThreadSnapshot
  -> HarnessCore
      -> emits AgentRunEvents
  -> AgentRunRecorder
      -> persists assistant Messages
      -> persists tool-call Messages
      -> persists tool-call-result Messages
      -> persists artifact references
```

The loop produces events. The recorder decides how those events become Agent Harness records and persists them through storage interfaces.

## Tool Executor

The tool executor is the deterministic dispatch component.

It:

- Receives one normalized tool-call request from HarnessCore.
- Looks up the tool definition in the static registry.
- Validates arguments against the tool input schema.
- Calls the Python tool handler.
- Normalizes success or failure into a structured tool result.
- Returns that result to the loop.

The executor owns one tool call at a time. HarnessCore decides whether another provider step is needed after the result.

## Static Tool Registry

The registry is static for the native app version.

Static means:

- Tool names are declared in code.
- Tool schemas are built at startup from typed input/output models.
- Tool handlers are wired through dependency injection from already-built Xenix services.
- The LLM receives a stable list of available tools for the current app capability set.
- Agent Harness records and tool arguments validate required artifacts, datasets, models, and arguments.

Example shape:

```text
AgentToolDefinition
  name
  description
  input_schema
  output_schema
  side_effect_level
  handler

build_static_tool_registry(services) -> AgentToolRegistry
```

Candidate first-slice registry:

```text
turn_end
data_peek
data_integrate
data_clean
data_feature_select
model_train
model_hyper_train
model_inference
```

## Tool Availability, Autonomy, And Cancellation

First-slice user control is cancellation: the send button becomes a stop button while the provider or a tool is running.

Agent instructions expose tool semantics, constraints, and the `turn_end` convention. Tool choice and ordering remain model-owned.

Contextual constraints still belong in validation:

- Data tools require file references from the ChatBox or resolvable prior tool results/artifact references in Agent Harness records.
- Model tools require explicit dataset, feature columns, and target columns, or resolvable prior tool results/artifact references in Agent Harness records.
- `model_inference` requires a trained model and input data.
- Export/open operations are handled through markdown artifact links and UI affordances in the first slice.

This keeps provider tool definitions stable while allowing the user to stop provider inference or tool execution.

## Modeling Decision Boundary

Training-plan selection belongs to a modeling planner boundary, separate from cancellation and argument validation.

```text
ModelingPlanner
  input:
    working_context
    dataset_profile
    user_objective
    available_model_catalog
  output:
    training_plan
    model_candidates
    evaluation_strategy
    explanation
```

`ModelingPlanner` handles data-aware and goal-aware choices such as model family, default parameters, tuning breadth, and evaluation metric.

The first training tool can call `ModelingPlanner` before it starts ML tasks.

## Script Runtime Deferral

Generic LLM-authored Python scripts are deferred beyond the first slice. First-slice data and model tools can be internally implemented with Python services, but the LLM receives bounded data/model function tools rather than a generic script execution tool.

## Thread As Workspace

First slice uses `Thread` as the LLM workspace.

First slice uses Messages, tool-call records, tool-result records, and artifact records as the working record. Agent Harness may derive an ephemeral working-context projection for provider calls and tool execution.

Structured domain state for dataset lineage, selected features and target, trained models, best model, predictions, and artifacts is deferred beyond the first slice.

WorkItem-style workspace ownership exits the target service topology.

## Implementation Implication

Recommended Agent Harness internal modules:

```text
src/xenix/services/agent/
  harness.py              # public orchestration facade
  core.py                 # HarnessCore turn orchestration
  provider.py             # LLMProvider protocol and normalized events
  messages.py             # canonical message models
  conversation_store.py   # thread/message loading and persistence facade
  run_recorder.py         # converts run events into durable rows
  tool_registry.py        # static registry and definitions
  tool_executor.py        # one-call execution and normalization
  cancellation.py         # stop provider inference and running tools
  modeling_planner.py     # data-aware training plan selection
  providers/              # OpenAI, DeepSeek, AIMock providers
  tools/                  # static Python tool handlers
```
