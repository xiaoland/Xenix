# Implementation Plan

## Objective & Constraints

- Objective: Move Composer attachment intake from path-backed file blocks to dataset-backed message blocks.
- Primary constraint: registration happens when the user sends the message, not when the user selects or drops a file.
- LLM-facing invariant: local filesystem paths never appear in provider-facing messages, tool schemas, tool arguments, tool results, or thread-title prompts.
- Ownership invariant: uploaded `.csv`, `.xlsx`, and `.xls` files become source datasets, not artifacts.
- Storage invariant: `DatasetRow.source_path` may remain the internal service-owned authority for local execution, but it is not an Agent/LLM contract.

## Slice 0: Contract Restatement Before Mutation

### Scope

- Restate the impact handshake before production code edits.
- Confirm whether source dataset files remain user-managed external files or should be copied into app-managed storage.
- Keep current assumption unless changed by the user: source files remain user-managed; Xenix stores their paths internally.

### Files Likely Touched

- `tasks/composer-dataset-attachments/packet.md`
- `tasks/composer-dataset-attachments/implementation-plan.md`

### Verification

- Human confirmation of impact handshake.
- No production test run required.

### Status

- Completed. User explicitly started implementation with `开始`; source files remain user-managed external files under the current storage ownership model.

## Slice 1: Dataset Attachment Shape

### Scope

- Define the persisted user message block for Composer datasets.
- Candidate block shape:

```json
{
  "type": "dataset",
  "dataset_id": "<opaque id>",
  "name": "<dataset display name>",
  "file_name": "<basename only>",
  "source_format": "csv|xlsx|xls",
  "row_count": 123,
  "column_count": 12,
  "preview_columns": ["..."]
}
```

- Keep absolute path out of this block.
- Add a provider-facing text projection such as:

```text
Attached dataset: <name> (dataset_id: <id>, file: <basename>, rows: <n>, columns: ...)
```

- Preserve legacy message rendering where possible, but display dataset attachments as dataset chips/cards rather than path-backed file chips.

### Files Likely Touched

- `src/xenix/services/agent/conversation_store.py`
- `src/xenix/services/agent/harness_service.py`
- `src/xenix/services/agent/chatbot_events.py`
- `src/xenix/ui/chatbot.py`
- `src/xenix/ui/main_window.py`
- `tests/test_agent_harness_foundation.py`
- `tests/test_agent_harness_first_slice.py`
- `tests/test_i18n.py`
- `tests/test_main.py`

### Verification

- Implemented and verified. Regression scan found no remaining `Attached file:` provider projection.

## Slice 2: Send-Time Dataset Registration

### Scope

- Keep Composer selection/drop as a local pending-file list until send.
- Restrict pending attachments to supported dataset extensions: `.csv`, `.xlsx`, `.xls`.
- On send, register each pending file through `DatasetService.register_dataset(...)`.
- Inspect registered datasets through service code and build safe dataset attachment blocks.
- If one file fails validation, fail the message submission before starting the Agent turn; surface a clear localized UI error.
- Avoid creating artifacts for uploaded input datasets.

### Files Likely Touched

- `src/xenix/ui/chatbot.py`
- `src/xenix/ui/main_window.py`
- `src/xenix/services/dataset_service.py`
- `src/xenix/services/dataset_inspection.py`
- `tests/test_main.py`
- `tests/test_services.py`
- `tests/test_i18n.py`

### Verification

- Implemented and verified. `tests/test_main.py` covers send-time registration into dataset attachments; i18n extraction/compile and full test suite pass.

## Slice 3: Harness Input Contract

### Scope

- Replace or extend `SubmitUserTurnInput.file_paths` with dataset attachment input.
- Prefer a compatibility transition only inside service code if tests or fixtures still call `file_paths`; do not keep path-bearing input as the forward contract.
- Change `_attached_files_for_thread(...)` into dataset-context extraction.
- Use dataset presence for contextual tool gating.
- Ensure thread title generation uses dataset names/file names only.

### Files Likely Touched

- `src/xenix/services/agent/harness_service.py`
- `src/xenix/services/agent/conversation_store.py`
- `tests/test_agent_harness_first_slice.py`
- `tests/test_agent_harness_streaming.py`
- `tests/test_agent_ai_observability.py`

### Verification

- Implemented. Harness tests cover dataset blocks, provider-safe tool exposure, title fallback, and no forward `file_paths` contract.

## Slice 4: Data Tool Schema Migration

### Scope

- Change `data.peek` schema from `source_path` to `dataset_id`.
- Change `data.integrate` schema from `source_paths` to `dataset_ids`.
- Resolve dataset ids internally through `DatasetService`.
- Return safe inspection/profile payloads without `source_path`.
- Keep generated outputs as artifacts where they are produced by transform/integrate/model/apply/chart flows.

### Files Likely Touched

- `src/xenix/services/agent/tools.py`
- `src/xenix/services/dataset_service.py`
- `src/xenix/services/dataset_inspection.py`
- `src/xenix/services/analysis_profile.py`
- `tests/test_analysis_profile.py`
- `tests/test_analysis_graph.py`
- `tests/test_data_transform.py`
- `tests/test_agent_harness_first_slice.py`

### Verification

- Implemented. Data tool tests cover `dataset_id`/`dataset_ids` schemas, safe inspection payloads, and generated artifact ownership.

## Slice 5: Durable Docs And Runtime Contract

### Scope

- Promote stable contract changes to durable docs after implementation is verified.
- Clarify that Composer data attachments become datasets and that artifacts are generated outputs.
- Clarify that Agent tools resolve datasets by id and never by local path.

### Files Likely Touched

- `docs/20-product-tdd/runtime-boundaries.md`
- `docs/20-product-tdd/storage-ownership.md`
- `docs/40-deployment/runtime-state.md`
- Possibly `docs/10-prd/` if user-visible workflow language needs updating.

### Verification

- Implemented and verified in `docs/20-product-tdd/runtime-boundaries.md` and `docs/20-product-tdd/storage-ownership.md`.

## Full Verification Shape

- Focused tests first:

```powershell
pdm run pytest tests/test_agent_harness_first_slice.py tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py tests/test_analysis_profile.py tests/test_main.py tests/test_i18n.py -q
```

- Boundary regression searches:

```powershell
rg -n "Attached file:|source_path|source_paths|file_paths" src/xenix/services/agent src/xenix/ui tests
```

- Broader confidence after focused fixes:

```powershell
pdm run check
pdm run test
```

## Open Decisions

- Resolved: no forward `SubmitUserTurnInput.file_paths` compatibility path remains.
- Resolved: provider-facing dataset projection includes safe shape and column names only; preview rows remain behind `data.peek(dataset_id)`.
- Resolved: multi-file Composer submission creates multiple dataset blocks; integration is an explicit `data.integrate(dataset_ids=[...])` tool action.
