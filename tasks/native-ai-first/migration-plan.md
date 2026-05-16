# Migration Plan

## Status

- Mode: Explore moving toward Solidify.
- Scope: decision-oriented migration plan for AI-first first slice.

## Migration Table

| Area | Decision Element | Current State | Target State | Migration Move | Key Risk | Verification |
|---|---|---|---|---|---|---|
| Product path | Primary interaction | Scenario-first Qt screens and dialogs | ChatBox-first thread workflow | Update PRD/Product TDD, then replace `MainWindow` central surface | Product docs conflict with local UI rules | Smoke test opens ChatBox as first surface |
| Workspace | Durable workspace owner | WorkItem exists as service/storage concept | Agent Harness owns Thread workspace records; first-slice working context derives from messages, tool results, and artifacts | Add Agent Harness conversation records; remove WorkItemService from target topology | WorkItem assumptions remain in ML services | Tool schemas and service APIs contain no `work_item_id` |
| Turns | Conversation boundary | No explicit turn model | Agent Harness Thread contains turns; each turn starts with user message and ends when provider returns no tool calls | Add Turn record and recorder behavior through storage interfaces | Empty provider response semantics are ambiguous | Harness test covers empty text plus empty tool calls |
| Tool registry | LLM tools | Scenario/UI-driven service calls | Minimal static registry: data peek/integrate/clean/feature selection, model train/hyper-train/inference | Build typed registry and executor | Tool surface grows too early | Registry snapshot test |
| Data transform | Transformation DSL | pandas service logic and UI choices | Deferred from first slice | Keep DuckDB design notes for later | Hidden transform scope creeps back into first slice | Registry excludes `data_transform` |
| Model execution | Training/inference | `MLService` and `services/ml` task contracts | `model_train`, `model_hyper_train`, `model_inference` tools call refactored service layer | Refactor ML service inputs away from WorkItem | Existing APIs assume WorkItem | Integration tests with fixture dataset |
| Artifact rendering | Result presentation | Dialogs/history open files | Tool returns markdown artifact links; ChatBox previews | Add artifact URI resolver and preview widgets | Broken links or heavy previews | UI test renders image/table/report links |
| LLM provider | Provider dialect | None in native app | OpenAI-compatible `/v1/chat/completions`, DeepSeek, AIMock | Add provider protocol and OpenAI-compatible provider | Literal `/v1/completions` confusion | Provider serialization tests |
| AIMock | Harness testing | None | AIMock HTTP server at LLM provider boundary | Configure provider `base_url` to AIMock in tests | Fixture drift or mismatched tool calls | E2E fixture replay test |
| User control | Cancellation | Dialog-driven confirmations | Stop button cancels provider inference or tool run in first slice | Add cancellation path from ChatBox send/stop button | Long tool runs block UI | Cancellation test for running tool |
| Scenario UI | Existing screens | Scenario home/dialog active path | Removed from target path immediately | Replace MainWindow composition with ChatBox path | Behavior loss from old screens | Feature parity checklist per tool |
| Storage | Persistence interface | SQLite ML tasks/datasets/work items | Standardized persistence interfaces for Agent Harness records, artifacts, datasets, ML tasks, and trained models | Add migrations after Agent Harness ownership contract solidifies | Schema churn | Migration and repository tests |

## Open Decision Order

1. Tool input/output schemas.
2. Agent Harness working-context projection.
3. Artifact URI and preview contract.
4. Turn persistence and empty-tool-call turn ending behavior.
5. OpenAI-compatible provider contract and AIMock fixture shape.
6. WorkItemService removal impact map.
