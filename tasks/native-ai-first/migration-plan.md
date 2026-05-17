# Migration Plan

## Status

- Mode: Execute.
- Scope: decision-oriented migration plan plus cleanup state for AI-first first slice.

## Migration Table

| Area | Decision Element | Current State | Target State | Migration Move | Key Risk | Verification |
|---|---|---|---|---|---|---|
| Product path | Primary interaction | ChatBox shell is active | ChatBox-first thread workflow | MainWindow composition is ChatBox-first | Artifact preview still link-based | Smoke test opens ChatBox as first surface |
| Workspace | Durable workspace owner | Agent Harness owns Thread records; storage baseline has no WorkItem schema | Agent Harness owns Thread workspace records; first-slice working context derives from messages, tool results, and artifacts | WorkItemService exited active source composition; development schema reset applied | Existing local dev DBs must be deleted/rebuilt | Tool schemas, service APIs, and fresh schema contain no `work_item_id` |
| Turns | Conversation boundary | No explicit turn model | Agent Harness Thread contains turns; each turn starts with user message and ends when provider returns no tool calls | Add Turn record and recorder behavior through storage interfaces | Empty provider response semantics are ambiguous | Harness test covers empty text plus empty tool calls |
| Tool registry | LLM tools | Scenario/UI-driven service calls | Minimal static registry: data peek/integrate/clean/feature selection, model train/hyper-train/inference | Build typed registry and executor | Tool surface grows too early | Registry snapshot test |
| Data transform | Transformation DSL | pandas service logic and UI choices | Deferred from first slice | Keep DuckDB design notes for later | Hidden transform scope creeps back into first slice | Registry excludes `data_transform` |
| Model execution | Training/inference | `MLService` public inputs are dataset-scoped | `model_train`, `model_hyper_train`, `model_inference` tools call refactored service layer | Refactor ML service inputs away from WorkItem | Dataset/thread-level best-model contract remains deferred | Integration tests with fixture dataset |
| Artifact rendering | Result presentation | Dialogs/history open files | Tool returns markdown artifact links; ChatBox previews | Add artifact URI resolver and preview widgets | Broken links or heavy previews | UI test renders image/table/report links |
| LLM provider | Provider dialect | None in native app | OpenAI-compatible `/v1/chat/completions`, DeepSeek, AIMock | Add provider protocol and OpenAI-compatible provider | Literal `/v1/completions` confusion | Provider serialization tests |
| AIMock | Harness testing | None | AIMock HTTP server at LLM provider boundary | Configure provider `base_url` to AIMock in tests | Fixture drift or mismatched tool calls | E2E fixture replay test |
| User control | Cancellation | Dialog-driven confirmations | Stop button cancels provider inference or tool run in first slice | Add cancellation path from ChatBox send/stop button | Long tool runs block UI | Cancellation test for running tool |
| Scenario UI | Existing screens | Scenario home/dialog modules exited source composition | Removed from target path immediately | Replace MainWindow composition with ChatBox path | Feature parity belongs to tools and ChatBox artifacts | Feature parity checklist per tool |
| Storage | Persistence interface | SQLite AI-first baseline v1 | Standardized persistence interfaces for Agent Harness records, artifacts, datasets, ML tasks, and trained models | Reset migrations before production release | Existing local dev DBs are obsolete | Bootstrap, migration rejection, and repository tests |

## Open Decision Order

1. Tool input/output schemas.
2. Agent Harness working-context projection.
3. Artifact URI and preview contract.
4. Turn persistence and empty-tool-call turn ending behavior.
5. OpenAI-compatible provider contract and AIMock fixture shape.
6. Data cleaning contract expansion after cleanup.
