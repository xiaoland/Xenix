# Native AI First Global Review

## Status

- Mode: Explore moving toward Solidify.
- Purpose: keep the whole task packet aligned around the current AI-first topology before implementation.
- Current branch: `native-ai-first`.
- Implementation plan: `tasks/native-ai-first/implementation-plan.md`.
- Phase 0 impact map: `tasks/native-ai-first/phase-0-impact-map.md`.

## Current Global Spine

### Product Surface

- Xenix remains a Qt Native desktop application.
- The primary surface is `ChatBox`.
- Existing functional screens are removed from the active user path after ChatBox reaches the first acceptance target.
- `Message` is the atomic UI and Harness concept.
- User interaction begins from conversation and file drag-and-drop.
- Tool outputs return markdown summaries and artifact links; ChatBox previews images, tables, CSV/XLSX files, metrics, reports, and model artifacts.

### Conversation Model

- `Thread` is the first-slice workspace.
- A thread contains ordered `Turn` records.
- A turn starts with one user Message.
- A turn ends when the provider response has an empty tool-call list.
- ChatBox renders turn dividers before user Messages.
- Agent Harness owns Thread, Turn, Message, tool-call, tool-result, run recorder, and first-slice working context.
- Storage provides standardized persistence interfaces for Agent Harness and other services.
- First-slice working context is derived from persisted messages, tool results, and artifacts.
- Separate structured domain state for derived datasets, feature selections, best models, and prediction refs is deferred.

### Agent Harness

- Agent Harness is a service under `src/xenix/services/agent/`.
- Agent Harness owns LLM function calling and Xenix service tools.
- `HarnessCore` owns user-message intake, turn progression, provider step control, tool-call dispatch sequencing, cancellation observation, and run events.
- LLM providers own provider-specific request assembly and response parsing.
- Thread, Turn, Message, tool-call, and tool-result ownership belongs to Agent Harness; storage supplies persistence interfaces.
- `ToolExecutor` executes one normalized tool call, validates arguments, calls the Python handler, and returns a structured result.
- Static tool registry is built at app startup from typed tool definitions and service-backed handlers.
- First-slice user control is cancellation through the ChatBox send/stop button.

### Provider Boundary

- First target dialect: OpenAI-compatible `/v1/chat/completions`.
- DeepSeek shares the OpenAI-compatible chat completions shape for messages and tools.
- CopilotKit AIMock attaches at the LLM provider boundary by replacing the provider base URL in tests.
- Provider research for OpenAI Responses, Anthropic Messages, and Google Gemini constrains the canonical Message shape, even if first implementation targets OpenAI-compatible chat completions.

### LLM Tool Registry

First-slice provider-facing tool names:

```text
data_peek
data_integrate
data_clean
data_feature_select
model_metadata
model_train
model_hyper_train
model_inference
```

Documentation aliases:

```text
data.peek
data.integrate
data.clean
data.feature.select
model.metadata
model.train
model.hyper_train
model.inference
```

First-slice excluded or deferred capabilities:

- LLM-authored arbitrary Python scripts.
- Generic `script_run_python`.
- Direct database query tools.
- Raw service invocation tools.
- Arbitrary filesystem, network, or package-install access.
- Artifact open/export tools as LLM tools.
- WorkItem and WorkItemService ownership in the target service topology.
- First-slice `data_transform` capability and DuckDB dependency.

### Acceptance Scenario

Minimum acceptance scenario:

```text
file drag/drop
  -> data_peek
  -> data_integrate
  -> data_clean
  -> data_feature_select
  -> model_metadata
  -> model_train or model_hyper_train
  -> model_inference
  -> markdown artifact links
  -> ChatBox previews
```

This scenario validates the product path. The thread system prompt describes identity and durable instructions; tool descriptions describe tool semantics and boundaries. Planning and tool ordering remain model-owned.

Model-specific preprocessing remains inside model training pipelines.

## Current Package Topology Candidate

```text
src/xenix/ui/chat/
  chat_box.py
  message_list.py
  message_composer.py
  file_drop_intake.py
  message_view_models.py
  message_renderers.py
  tool_event_view.py
  artifact_widgets.py

src/xenix/services/agent/
  harness.py
  core.py
  provider.py
  messages.py
  turns.py
  conversation_store.py
  run_recorder.py
  tool_registry.py
  tool_schema.py
  tool_executor.py
  cancellation.py
  modeling_planner.py
  artifacts.py
  providers/
    base.py
    openai_chat_completions_v1.py
    deepseek_chat_completions.py
    copilotkit_aimock.py
  tools/
    data_tools.py
    model_tools.py
    turn_tools.py
```

## Consistency Corrections Made

- Replaced broad Harness policy wording with concrete cancellation, validation, and modeling planner responsibilities.
- Kept AIMock at the LLM provider boundary.
- Aligned OpenAI naming to OpenAI-compatible `/v1/chat/completions`.
- Moved WorkItem out of the target service topology.
- Kept generic script runtime as a future direction.
- Removed first-slice approval-result states from tool-call results.
- Aligned package names around `data_tools`, `model_tools`, `turn_tools`, and provider dialect modules.

## Confirmed High-Level Decisions

- First implementation uses refactor-first service boundary cleanup.
- Old UI exits the target path immediately.
- `WorkItemService` exits the target service topology immediately.
- First slice excludes `data_transform`; DuckDB remains a likely future transformation engine.
- Result presentation uses markdown plus `artifact://...` links as the unified ChatBox contract.
- First provider/test route uses OpenAI-compatible `/v1/chat/completions` plus CopilotKit AIMock HTTP boundary.

## High-Level Design Agenda

The next discussion should stay at product and architecture level.

1. Product interaction model: what "basic data analysis from data to prediction" means in one ChatBox-first happy path.
2. Ownership topology: which durable owners exist after the AI-first shift: ChatBox, Agent Harness, existing services, storage, ML adapters, and artifacts.
3. Conversation architecture: how Agent Harness reconstructs working context from messages, tool results, and artifacts.
4. Agent responsibility split: what belongs to HarnessCore, provider dialects, tool registry, tool executor, recorder, and modeling planner.
5. Tool surface scope: whether the eight first-slice tools are sufficient for the first acceptance target.
6. Migration strategy: how to retire old UI and WorkItemService while preserving reusable behavior.
7. Testing strategy: what proof is required before old UI flows are retired.

## Key Implementation Gap Decisions

These are implementation-impacting decisions that should be settled before low-level design.

1. Service gap: current `DatasetService`, `MLService`, and storage contracts were built for screen-driven flows; refactor service boundaries for ChatBox/Harness ownership.
2. Workspace gap: current ML contracts assume WorkItem-like ids; replace them with Agent Harness records plus explicit task inputs.
3. Persistence gap: current storage lacks persistence interfaces for Agent Harness-owned thread, turn, message, tool-call, tool-result, and artifact-link records.
4. UI gap: current MainWindow is scenario/screen-oriented; decide the replacement strategy for ChatBox as central widget and renderer host.
5. Provider gap: the app currently lacks an LLM provider boundary; decide first provider implementation and AIMock test mode.
6. Transform gap: data transformation DSL is deferred from first slice.
7. Artifact gap: current outputs are file/history oriented; decide whether artifact links become the universal ChatBox result presentation contract.
8. Cancellation gap: long-running model training and provider calls need stop semantics; decide the minimum reliable cancellation behavior for first slice.

## Low-Level Design Backlog

The following are intentionally deferred until the high-level decisions above are stable:

- Exact Message fields, enum values, and provider refs.
- Exact final styling for the turn-boundary divider.
- Exact working-context projection and prompt injection format.
- Exact Pydantic schemas for each tool.
- Exact future DuckDB SQL validation rules and input alias mechanics.
- Exact artifact URI parser, preview row limits, and resolver payloads.
- Exact provider streaming event shape and AIMock fixture JSON.
- Exact Qt widget classes, signals, and model/view binding.
