# Native AI First Code Topology Draft

## Status

- Mode: Explore moving toward Solidify.
- Scope: implementation topology only.
- Durable docs and source code stay unchanged until this draft is confirmed.
- Global review: `tasks/native-ai-first/global-review.md`.
- High-level decision agenda: `tasks/native-ai-first/high-level-design-decisions.md`.
- Message-provider contract research: `tasks/native-ai-first/provider-message-contract-research.md`.
- Agent Harness boundary notes: `tasks/native-ai-first/agent-harness-design-notes.md`.
- Framework reference research: `tasks/native-ai-first/framework-reference-research.md`.
- Tool design notes: `tasks/native-ai-first/tool-design-notes.md`.
- LLM tool inventory: `tasks/native-ai-first/llm-tool-inventory.md`.
- Thread workspace design: `tasks/native-ai-first/thread-workspace-design.md`.
- Script runtime future direction: `tasks/native-ai-first/script-runtime-design.md`.
- Data transform DSL: `tasks/native-ai-first/data-transform-dsl.md`.
- Artifact link contract: `tasks/native-ai-first/artifact-link-contract.md`.
- AIMock integration: `tasks/native-ai-first/aimock-integration.md`.
- Migration plan: `tasks/native-ai-first/migration-plan.md`.

## Current Repository Facts

- Composition root: `src/xenix/app.py`
- Current native shell: `src/xenix/ui/main_window.py`
- Current Qt surfaces: scenario home, scenario dialogs, dataset workspace, ML workspace, inference workspace, history, settings.
- Current service boundary: `src/xenix/services/`
- Current ML adapter boundary: `src/xenix/services/ml/`
- Current storage boundary: `src/xenix/services/storage/`
- Current runtime contract: `UI -> services -> adapters -> SQLite/filesystem/ML`
- Current Product TDD still names scenario-first UI as the primary operator path and needs replacement.

## Product Topology Claim

AI-first Xenix has one primary interaction surface:

```text
Native Qt MainWindow
  -> ChatBox
      -> Message stream
      -> Composer
      -> File drop intake
      -> Message artifact renderers
  -> services/agent/ Agent Harness service
      -> Canonical Message contract
      -> Thread / Turn / Message owner
      -> LLM providers
          -> OpenAI-compatible Chat Completions v1
          -> DeepSeek Chat Completions
          -> CopilotKit AIMock provider
      -> HarnessCore
      -> Static tool registry
      -> Tool executor
      -> Cancellation controller
      -> Modeling planner
      -> Conversation store
      -> Agent run recorder
      -> Turn model
      -> Xenix service tools
          -> Data tools
          -> Model tools
  -> Refactored services
      -> DatasetService
      -> MLService
      -> ArtifactService
  -> Existing adapters and storage interfaces
      -> services/ml
      -> SQLite metadata
      -> filesystem artifacts
```

The primary user path becomes:

```text
User text / file drag
  -> ChatBox composer
  -> Agent Harness service persists user Message
  -> LLM provider
  -> canonical function calling
  -> Agent Harness service tool execution
  -> Agent Harness service persists tool-call / tool-result Messages
  -> LLM provider
  -> Agent Harness service persists assistant Message
  -> ChatBox Message renderer
  -> next user turn
```

## Proposed Package Layout

```text
src/xenix/
  app.py
  ui/
    main_window.py
    chat/
      __init__.py
      chat_box.py
      message_list.py
      message_composer.py
      file_drop_intake.py
      message_view_models.py
      message_renderers.py
      tool_event_view.py
      artifact_widgets.py
  services/
    agent/
      __init__.py
      harness.py
      core.py
      conversation.py
      events.py
      messages.py
      turns.py
      conversation_store.py
      run_recorder.py
      tool_registry.py
      tool_schema.py
      tool_executor.py
      cancellation.py
      tool_results.py
      providers/
        __init__.py
        base.py
        openai_chat_completions_v1.py
        deepseek_chat_completions.py
        copilotkit_aimock.py
      tools/
        __init__.py
        data_tools.py
        model_tools.py
        turn_tools.py
      artifacts.py
    storage/
      models.py
      repositories/
        conversations.py
        messages.py
        tool_calls.py
```

## Layer Responsibilities

### `src/xenix/ui/chat/`

- Owns Qt widgets only.
- Renders the ChatBox, message timeline, composer, dropped files, tool progress, cancellation state, tables, charts, and artifact cards.
- Emits plain Python events to the Agent Harness service.
- Receives streamed or batched harness events and maps persisted `Message` records to view models.
- Keeps only visual state and transient widget state.
- Treats visible user and assistant messages as the primary display distinction.
- Renders a message's internal content through `content_blocks`.

### `src/xenix/services/agent/`

- Owns the Agent Harness runtime.
- Is a service boundary under `src/xenix/services/`.
- Owns LLM providers, HarnessCore, canonical function-calling, static tool schemas, Xenix service tools, and tool execution.
- Owns Thread, Turn, Message, tool-call, tool-result, and run records.
- Turns a user message and file attachments into one conversation turn.
- Maintains provider-independent HarnessCore turn control.
- Registers Xenix tools with schemas derived from typed request models.
- Executes tool calls through service tools.
- Emits structured events for assistant deltas, tool calls, tool results, cancellation, errors, and final messages.
- Delegates durable writes to conversation store and run recorder.

### `src/xenix/services/agent/providers/`

- Owns provider-specific request and response translation.
- Converts canonical Xenix Messages into OpenAI, Anthropic, Google, or mock provider requests.
- Converts provider responses into canonical Xenix Messages before UI rendering.
- Hosts the CopilotKit AIMock provider boundary for deterministic E2E behavior.
- Implements the canonical function-calling provider contract.

### `src/xenix/services/agent/tools/`

- Owns LLM-facing adapters over existing Xenix services.
- Lives inside Agent Harness.
- Keeps tool inputs and outputs typed.
- Converts service exceptions into user-actionable tool results.
- Provides integration-testable boundaries independent from the ChatBox widget.

### Existing `src/xenix/services/`

- Remains the owner for business operations, validation, storage coordination, ML task creation, and artifact path resolution.
- Current services become callable capabilities behind agent tools.
- `ScenarioWorkflowService` is removed in the target topology.
- First slice uses Thread as the LLM workspace.
- Agent Harness derives first-slice working context from Messages, tool results, and artifacts for tool execution and LLM context injection.

### Existing `src/xenix/services/ml/`

- Remains the native ML execution adapter boundary.
- Receives validated task requests from services.
- Emits task outputs and metadata through existing service-owned contracts.

### Existing `src/xenix/services/storage/`

- Remains the SQLite and filesystem persistence implementation.
- Provides standardized persistence interfaces for Agent Harness and other services.
- Does not own Thread, Turn, Message, tool-call, or tool-result semantics.

## Message Contract

`Message` is the durable unit. `content_blocks` describe what a single Message contains; they are internal content blocks, not separate user-visible messages.

```text
ConversationThread
  id
  title
  created_at
  updated_at

Turn
  id
  thread_id
  sequence_index
  started_by_message_id
  status
  created_at
  ended_at

Message
  id
  thread_id
  turn_id
  sequence_index
  harness_kind:
    developer_instruction
    system_instruction
    user_message
    assistant_message
    tool_call
    tool_call_result
  provider_role:
    developer | system | user | assistant | tool | none
  ui_author:
    user | assistant | hidden
  visibility:
    visible | hidden
  content_blocks:
    - text
    - file_attachment
    - tool_call
    - tool_result
    - table
    - chart
    - artifact_ref
    - cancellation
    - error
  provider_refs:
    response_id
    output_item_id
    call_id
    tool_call_id
    provider_message_id
  status
  created_at

ToolCall
  id
  thread_id
  message_id
  tool_name
  arguments
  status
  result_message_id
  artifact_refs

AgentArtifact
  id
  kind
  title
  source
  path
  preview_payload

```

Invariants:

- Visible UI messages map 1:1 to Harness Messages.
- Thread is composed of turns.
- A turn starts with one user Message and ends when the provider response has no tool calls.
- UI distinguishes visible `user` and `assistant` messages.
- Harness distinguishes provider-facing message kind and tool lifecycle state.
- Thread-level system prompt is persisted as Thread metadata and projected as the first provider message.
- LLM providers own conversion between canonical Messages and provider-specific message or item contracts.
- The tool registry is static for a given native app version; runtime context affects argument validation and required artifact checks.
- HarnessCore emits run events; run recorder persists those events into durable rows.
- First slice derives working context from Messages, tool results, and artifacts; separate structured domain state is deferred.

## First-Slice Tool Topology

Minimum acceptance requires pure conversation plus file drag-and-drop for basic data analysis from data intake to prediction.

The authoritative proposed LLM-facing tool list lives in `tasks/native-ai-first/llm-tool-inventory.md`.

Condensed groups:

```text
data preprocessing
model training and inference
```

Tool outputs may contain markdown links to generated artifacts; ChatBox handles preview rendering for images, tables, CSV/XLSX files, and reports.

## MainWindow Composition Change

Target composition root:

```text
build_main_window()
  -> build refactored services
  -> build AgentHarness service
  -> build LLMProvider from settings/config
  -> build MainWindow(paths, translation_manager, agent_harness, settings, artifacts)
  -> MainWindow hosts History sidebar, Settings, and ThreadDetailView
```

The current `MainWindow` owns a ChatBox-centered shell. Old scenario dialogs, technical workspaces, `ScenarioWorkflowService`, and `WorkItemService` have exited the active source composition.

## Test Topology

```text
Unit tests
  -> canonical Message mapping
  -> LLM provider serialization
  -> tool schema generation
  -> tool result normalization
  -> cancellation behavior

Service integration tests
  -> dataset tool calls real DatasetService with temp files
  -> data tools produce tool-result records and artifact links through services
  -> data tools run preprocessing with fixture data and validate dataset outputs
  -> model tools run training with fixture data and validate model + metrics outputs
  -> model inference tool validates prediction outputs

Harness tests
  -> fake LLM provider emits deterministic tool calls
  -> harness loops through tool registry and produces Messages
  -> running provider/tool call can be cancelled

Qt boundary tests
  -> ChatBox accepts text
  -> file drag intake emits attachment event
  -> tool events render as Messages
  -> artifact Messages render table/chart/file summaries

Deterministic E2E tests
  -> CopilotKit AIMock at LLM provider boundary
  -> fixture-driven LLM/tool behavior
  -> conversation plus file drag produces data-to-prediction result Messages
```

## Migration Phases

1. Solidify product and technical contracts.
2. Add Product TDD/ADR updates for AI-first ChatBox as primary operator path.
3. Add provider-informed canonical Message contract using `tasks/native-ai-first/provider-message-contract-research.md`.
4. Add `services/agent/` with LLM providers, HarnessCore, static tool registry, typed service tools, run recorder, and fake provider harness tests.
5. Add bounded data/model tools.
6. Add `ui/chat/` with Message timeline, composer, and file-drop intake.
7. Add thread/message/tool-call persistence.
8. Wire `MainWindow` to ChatBox and Agent Harness.
9. Add first-slice service integration tests for data-to-prediction tool runs.
10. Add deterministic E2E testing through CopilotKit AIMock at LLM provider boundary.
11. Remove `ScenarioWorkflowService`, `WorkItemService`, and scenario-first Qt surfaces from the target composition. Completed in the cleanup slice.

## Design Questions

- First `content_blocks` set for UI implementation.
- First LLM provider boundary and configuration model.
- Cancellation behavior for provider inference and running tools.
- Modeling planner boundary for choosing model family, training plan, and evaluation strategy from data profile and user objective.
- Exact persistence schema for conversation thread, message, tool call, tool result, and artifact references.
- Tool output presentation contract: markdown summaries, artifact links, and ChatBox preview rendering.
- Whether provider roles should be stored durably or derived by adapter from `harness_kind`.
- Whether a visible assistant message with text plus a tool call persists as one Message, matching Anthropic, or as sequential Messages for easier UI progress rendering.
- OpenAI provider dialect is OpenAI-compatible `/v1/chat/completions`.
- Exact Turn persistence schema and final turn-boundary divider styling.

## Impact Forecast

- `docs/10-prd/product-scope.md`: primary operator path needs AI-first revision.
- `docs/20-product-tdd/runtime-boundaries.md`: call graph needs Agent Harness service layer.
- `src/xenix/ui/AGENTS.md`: scenario-first rule needs replacement.
- `src/xenix/app.py`: composition root adds Agent Harness and ChatBox dependencies.
- `src/xenix/ui/main_window.py`: central widget changes to ChatBox.
- `src/xenix/services/`: new agent harness and tool adapter package.
- `src/xenix/services/work_item_service.py`: removed from target service topology.
- `src/xenix/services/scenario_workflow_service.py`: removed from target topology.
- `src/xenix/services/storage/`: persistence interfaces for Agent Harness records added in the first slice.
- `tests/`: new unit, service integration, harness, Qt boundary, and deterministic E2E tests.
