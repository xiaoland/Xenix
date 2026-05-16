# High-Level Design Decisions

## Status

- Mode: Explore.
- Purpose: keep discussion with the user at high-level architecture and key implementation gap level.

## Discussion Boundary

Current discussion should focus on:

- product interaction shape
- architecture ownership
- migration strategy
- first-slice acceptance
- major gaps between target topology and current code

Current discussion should defer:

- exact data models
- exact Pydantic schemas
- exact Qt widget implementation
- exact prompt text
- exact test fixture JSON
- exact provider streaming events

## Decision Log

- Service gap strategy: first implementation uses refactor-first service boundary cleanup.
- Old UI exits the target path immediately.
- `WorkItemService` exits the target service topology immediately.
- First slice excludes `data_transform`.
- DuckDB SQL remains a likely future DSL for deterministic data transformation.
- Result presentation uses markdown plus `artifact://...` links as the unified ChatBox contract.
- First provider/test route uses OpenAI-compatible `/v1/chat/completions` plus CopilotKit AIMock HTTP boundary.
- Agent autonomy principle: acceptance scenarios validate capability; prompts expose tools and boundaries while leaving planning and tool ordering to the LLM.
- Agent Harness is a service under `src/xenix/services/agent/`.
- Agent Harness owns Thread, Turn, Message, tool-call, tool-result, run recorder, and first-slice working context.
- Storage provides persistence interfaces.
- First slice defers structured domain state for derived dataset, feature selection, best model, and prediction refs.

## High-Level Decisions To Make

### 1. First-Slice Product Path

Decision needed:

```text
User drags files into ChatBox
  -> asks for analysis
  -> LLM inspects/integrates/cleans data through tools
  -> LLM selects features/target with user confirmation only when needed
  -> LLM trains/evaluates models
  -> LLM runs inference
  -> ChatBox shows markdown summaries and artifact previews
```

Question:

- Is this the first acceptance path, or should first slice stop before inference?

### 2. Workspace Owner

Current proposal:

- `Thread` is the first-slice workspace.
- Agent Harness owns Thread, Turn, Message, tool-call, and tool-result records.
- First-slice working context is derived from messages, tool results, and artifacts.
- WorkItem exits the target service topology.

Decision needed:

- Confirm `Thread` as the first-slice workspace owner.

Working interpretation:

- Messages remain the user-visible chronological history.
- Tool calls, tool results, and artifact records carry machine-readable execution facts.
- Agent Harness may derive a compact working-context projection for provider calls and tool execution.
- Structured domain state for derived dataset, feature selection, best model, and prediction refs is a later-slice option.

### 3. Migration Strategy

Current proposal:

- Build ChatBox and Agent Harness as the active product path.
- Retire old screens from the target branch immediately.
- Remove `ScenarioWorkflowService` from target composition.
- Remove `WorkItemService` from target composition.

Current decision:

- Immediate old UI retirement is confirmed for the target path.

### 4. Tool Surface Scope

Current proposal:

```text
data_peek
data_integrate
data_clean
data_feature_select
model_train
model_hyper_train
model_inference
```

Decision needed:

- Confirm this as the complete first-slice LLM tool surface.

### 5. Service Gap Strategy

Current implementation risk:

- Current services are designed around native screens and WorkItem state.
- First-slice tools use Agent Harness records, explicit arguments, and artifact links.

Current decision:

- Use refactor-first for the first implementation.
- Retire WorkItem-centered service contracts from the target topology.

Refactor-first route:

- Split current screen/work-item workflow state from reusable domain services.
- Represent dataset lineage, feature/target selection, model outputs, predictions, and artifacts through tool results and artifact records in the first slice.
- Make model training/inference accept explicit dataset id, feature columns, target columns, model selections, and output owner instead of a `work_item_id`.
- Keep `MLTaskService` as atomic queue/worker/task artifact owner.
- Add an Artifact service boundary that registers and resolves datasets, models, metrics, reports, images, and prediction files for ChatBox links.

### 6. Data Transform Dependency

Deferred proposal:

- Use DuckDB SQL SELECT for `data_transform`.

Clarification:

- DuckDB is the execution engine for deterministic `data_transform` operations.
- The tool registers one or more input datasets as DuckDB tables or views, runs a validated SELECT/CTE query, then materializes the result as a derived dataset artifact.
- SQLite remains the metadata store.
- Pandas/openpyxl can still handle file loading, export, inspection, and non-SQL data utilities where they already fit.

Decision needed:

- Decide after the first slice when `data_transform` returns to scope.

Current decision:

- First slice has no `data_transform` tool and no DuckDB dependency requirement.

### 7. Result Presentation

Current proposal:

- Tool results are markdown summaries plus `artifact://...` links.
- ChatBox preview rendering becomes the universal presentation path.

Decision needed:

- Confirm artifact links as the result contract for tables, charts, reports, metrics, models, and predictions.

Current decision:

- Confirmed. Artifact link details need a separate design pass.

### 8. Provider And Test Boundary

Current proposal:

- First provider: OpenAI-compatible `/v1/chat/completions`.
- DeepSeek uses the same compatible dialect where possible.
- AIMock attaches at provider base URL for deterministic E2E tests.

Decision needed:

- Confirm this provider/test boundary as the first implementation route.

Current decision:

- Confirmed.

## Key Implementation Gaps

| Gap | Why It Matters | High-Level Decision Needed |
|---|---|---|
| Screen-first UI | Current MainWindow and user workflows are screen/scenario-oriented | Immediate old UI retirement |
| Missing conversation persistence | First slice requires persisted Agent Harness records for threads, turns, messages, tool calls, and artifacts | Add storage interfaces for Agent Harness before UI wiring |
| Service shape mismatch | Existing services require WorkItem or screen-driven inputs | Refactor-first service boundary cleanup |
| ML task lifecycle | Training/inference can be long-running and cancellable | Minimum cancellation semantics |
| Provider absence | Native app has no LLM provider abstraction | OpenAI-compatible provider first |
| Deterministic AI tests | E2E must avoid live LLM nondeterminism | AIMock HTTP server at provider boundary |
| Artifact rendering | Results move from screens/history into ChatBox | Artifact link contract as presentation spine |
| Transform engine | Transformation DSL is useful and broad | Defer from first slice |
