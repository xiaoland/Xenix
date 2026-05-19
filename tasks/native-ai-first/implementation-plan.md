# Native AI First Implementation Plan

## Status

- Mode: Solidify.
- Scope: high-level implementation plan for the first AI-first slice.
- This plan does not start implementation.

## First-Slice Goal

User can complete basic data analysis from files to prediction inside Chatbot through conversation plus file drag-and-drop.

Acceptance scenario:

```text
drag CSV/XLSX files into Chatbot
  -> ask for analysis
  -> data_peek
  -> data_integrate
  -> data_clean
  -> data_feature_select
  -> model_metadata
  -> model_train or model_hyper_train
  -> model_inference
  -> markdown summaries and artifact previews in Chatbot
  -> provider response with empty tool call list
```

This scenario validates that the app can complete the end-to-end job. The thread system prompt describes identity and durable instructions; tool descriptions describe tool semantics and boundaries. Planning and tool ordering remain model-owned.

## Confirmed Direction

- Refactor services first for AI-first ownership.
- Old UI exits the target path immediately.
- `WorkItemService` exits the target service topology immediately.
- `ScenarioWorkflowService` exits the target composition.
- `Thread` is the first-slice workspace.
- Agent Harness is a service under `src/xenix/services/agent/`.
- Agent Harness owns Thread, Turn, Message, tool-call, tool-result, run recorder, and first-slice working context.
- Storage provides standardized persistence interfaces for Agent Harness and other services.
- First slice uses persisted messages, tool results, and artifacts as the working record.
- Separate structured domain state for derived datasets, feature selections, best models, and prediction refs is deferred.
- First slice excludes `data_transform`.
- DuckDB remains a future data transformation direction.
- Result presentation uses markdown plus `artifact://...` links.
- First provider/test route uses OpenAI-compatible `/v1/chat/completions` plus CopilotKit AIMock HTTP boundary.

## Architecture Target

```text
MainWindow
  -> Chatbot
      -> Message timeline
      -> Composer / file drop
      -> Artifact preview renderers
      -> Stop control
  -> services/agent/ Agent Harness service
      -> HarnessCore
      -> Thread / Turn / Message owner
      -> LLM provider boundary
      -> static tool registry
      -> tool executor
      -> run recorder
      -> cancellation
      -> tool handlers over service boundaries
  -> services/artifacts/
      -> Artifact service
      -> artifact resolver
  -> services/data/
      -> Dataset and data preparation services
  -> services/ml/
      -> Modeling planner
      -> ML service
      -> MLTaskService
  -> services/storage/
      -> SQLite / filesystem persistence interfaces
```

## Implementation Phases

### Phase 0: Alignment And Impact Map

Purpose: make the branch truth coherent before mutation-heavy work.

Moves:

- Update durable product/technical docs for Chatbot-first path.
- Replace `src/xenix/ui/AGENTS.md` scenario-first guidance.
- Map all direct references to old UI, `ScenarioWorkflowService`, `WorkItemService`, and WorkItem storage.
- Decide which existing service behaviors are preserved as reusable logic.

Exit proof:

- Impact map exists at `tasks/native-ai-first/phase-0-impact-map.md`.
- Durable docs name Chatbot as the primary operator path.
- Local UI and service AGENTS rules name AI-first ownership.

### Phase 1: Agent Conversation And Artifact Foundation

Purpose: create the Agent Harness-owned conversation and artifact foundation.

Moves:

- Add Agent Harness ownership for Thread, Turn, Message, tool-call, tool-result, and run records.
- Add storage interfaces that persist Agent Harness records.
- Add artifact service and resolver for `artifact://...` links.
- Keep first-slice working context derived from messages, tool results, and artifacts.

Exit proof:

- Repository tests can create a Thread, append a Turn, persist Messages, attach artifacts, and resolve artifact links through storage interfaces.
- Prior tool results and artifacts can be loaded as working context for a later tool call.

### Phase 2: Service Refactor

Purpose: remove WorkItem as the service owner and expose explicit AI-first service contracts.

Moves:

- Remove target dependency on `WorkItemService`.
- Refactor ML service inputs to use explicit dataset id, feature columns, target columns, model selections, and artifact output owner.
- Keep `MLTaskService` as the task queue, worker dispatch, status, logs, and task artifact owner.
- Add or refactor data services for peek, integrate, clean, and feature selection.
- Add Artifact service registration for datasets, models, metrics, reports, images, and predictions.

Exit proof:

- Service integration tests cover data peek/integrate/clean/feature selection without `work_item_id`.
- ML service integration tests train/evaluate/infer with explicit thread-oriented inputs.
- No first-slice service API requires `work_item_id`.

### Phase 3: Agent Harness

Purpose: make LLM-driven tool execution deterministic and testable.

Moves:

- Add Agent Harness module with HarnessCore, provider protocol, static tool registry, tool executor, run recorder, and cancellation.
- Register first-slice tools:
  - `data_peek`
  - `data_integrate`
  - `data_clean`
  - `data_feature_select`
  - `model_metadata`
  - `model_train`
  - `model_hyper_train`
  - `model_inference`
- Implement OpenAI-compatible provider boundary.
- Add AIMock provider configuration path through provider base URL.

Exit proof:

- Harness tests with fake provider execute a complete tool-call sequence and persist Messages.
- Provider serialization tests cover OpenAI-compatible `/v1/chat/completions`.
- Cancellation test stops an active provider/tool run at the Harness boundary.

### Phase 4: Chatbot UI

Purpose: replace the active Qt surface with the AI-first interaction shell.

Moves:

- Replace `MainWindow` central path with Chatbot.
- Add message timeline, composer, file drop intake, artifact preview renderers, tool progress rendering, and stop control.
- Remove scenario-first UI composition and dialog entry points from target path.
- Keep UI service-driven; UI never parses datasets or reconstructs business state.

Exit proof:

- Smoke test opens Chatbot as the first surface.
- Qt boundary tests cover text send, file drop, message rendering, artifact preview, and stop control state.

### Phase 5: Deterministic E2E

Purpose: prove the first-slice product path without live LLM nondeterminism.

Moves:

- Configure CopilotKit AIMock as HTTP provider boundary.
- Add fixture-driven E2E for drag/drop plus conversation plus tool calls.
- Assert final Chatbot contains prediction artifact links and previews.

Exit proof:

- E2E test completes data-to-prediction path through AIMock.
- Tool and artifact outputs are deterministic enough for regression coverage.

### Phase 6: Removal And Cleanup

Purpose: finish the branch as an AI-first target branch.

Moves:

- Remove old scenario UI modules from active composition.
- Remove `ScenarioWorkflowService` and `WorkItemService` target dependencies.
- Clean storage/repository names and artifact paths that still imply WorkItem ownership.
- Remove obsolete tests or rewrite them against Chatbot/Harness/service boundaries.

Exit proof:

- Static search shows no active first-slice dependency on `WorkItemService` or `ScenarioWorkflowService`.
- Test suite covers the new primary path.
- App smoke test and AIMock E2E pass.

## Critical Checkpoints

1. Agent Harness-owned conversation persistence boundary before Phase 1.
2. Artifact service boundary before service refactor writes outputs.
3. ML service explicit input contract before WorkItem removal.
4. Chatbot composition boundary before deleting old UI entry points.
5. AIMock fixture contract before E2E hardening.

## Acceptance Criteria

- App starts directly into Chatbot.
- User can drag CSV/XLSX files into Chatbot.
- User can request basic analysis through conversation.
- LLM can call first-slice tools through Agent Harness.
- LLM can inspect available model keys, capabilities, and parameter schemas through `model_metadata`.
- Data is inspected, integrated, cleaned, and prepared for modeling.
- Feature/target selection is captured as a tool result or artifact-backed record.
- Model training or hyperparameter training produces model and metrics artifacts.
- Inference produces prediction artifacts.
- Chatbot renders markdown summaries and previews artifact links.
- A turn ends when the provider response has an empty tool-call list.
- Conversation, messages, tool calls, tool results, and artifacts persist through Agent Harness-owned boundaries.
- Deterministic AIMock E2E covers the full happy path.

## Known Risks

- Removing old UI early can expose service behavior gaps that old dialogs previously masked.
- Refactoring ML service away from WorkItem may touch storage layout, trained model metadata, inference history, and existing tests together.
- Reintroducing structured workflow state under Thread can become an implicit workflow engine if ownership is not kept narrow.
- Artifact links need a resolver boundary before UI preview work stays reliable.
- Cancellation semantics for worker-backed ML tasks may need staged maturity.
