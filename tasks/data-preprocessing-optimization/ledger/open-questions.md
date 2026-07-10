# Open Questions

| ID | Owner | Blocking | Question | Impact | Next Step |
| --- | --- | --- | --- | --- | --- |
| OQ-001 | Storage / DatasetService | medium | What is the migration policy for existing local DB rows whose dataset `source_path` still points at raw CSV/XLS/XLSX user files? | Prevents a clean long-term storage contract if legacy rows silently keep old semantics. | Add a dedicated workstream for runtime DB migration and legacy compatibility policy. |
| OQ-002 | DatasetExportService | low | Should workbook export support import-group or derived-family multi-sheet exports, beyond single dataset -> one-sheet workbook? | Affects future user-facing export ergonomics. | Defer until eager derived export artifact behavior is stable. |
| OQ-003 | Analysis services | low | Should `AnalysisProfileService` return as a future atomic descriptive-statistics tool, or remain internal service code? | Replaces the useful part of old `data.peek.analysis` without reintroducing a bundled tool. | Decide with a separate query/profile workstream and real agent traces. |
| OQ-004 | Agent Harness storage | low | Is there a later schema simplification for tool-call/result storage after provider-facing result convergence? | Could reduce storage complexity, but risks losing invocation ledger semantics if rushed. | Revisit only after several tool families follow the canonical result contract. |
| OQ-005 | Packaging / deployment | medium | Are `polars`, `fastexcel`, and `xlsxwriter` packaged and runtime-tested for all target desktop builds? | Workbook import/export depend on these libraries in production builds. | Add deployment verification in a packaging-focused sub-task. |
| OQ-006 | ML workers | medium | Do remote/SSH ML worker staging paths preserve Parquet input behavior without reintroducing CSV conversion? | Internal dataset contract includes ML; worker staging is part of that blast radius. | Add targeted worker-path verification if current tests do not cover it sufficiently. |
| OQ-015 | Runtime / AgentHarness / Data services | medium | Should preprocessing worker execution become a durable async task model with progress, resumable status, and possible cancellation semantics? | The current fix isolates heavy work in a subprocess but keeps Agent tool calls synchronous while waiting for worker completion. | Defer until large-data traces prove synchronous waiting is insufficient for user feedback or cancellation. |
| OQ-016 | Data services | medium | Should `data.integrate`, `data.tokenize`, and source attachment import move their full-data compute into the preprocessing worker boundary too? | Generated dataset registration/export is now worker-isolated, but some upstream compute paths can still do full-table work in the desktop process. | Add follow-up slices after transform/clean isolation is verified. |

## Resolved During `08-eager-derived-export-artifacts`

- OQ-007: covered Agent-visible generated registered datasets that share `AgentToolRegistry._register_generated_dataset_result()`: `data.integrate`, `data.clean`, `data.tokenize`, and `data.transform`. `model.apply` already produces an apply-result artifact through the ML task path and is not a dataset-export helper path in this slice.
- OQ-008: dataset export artifacts default to workbook `.xlsx`; CSV remains an interchange/export/report format only where a specific tool owns that output.

## Resolved During `09-deferred-attachment-import-after-send`

- OQ-009: UserMessage represents an attachment as a workbook/file-level visible block. It does not show pending dataset import blocks or resulting sheet datasets.
- OQ-010: AgentRun row is created only after attachment import succeeds.
- OQ-011: Once Send is accepted, the submitted attachment import is not cancellable.
- OQ-012: Multi-sheet workbook imports do not change the visible UserMessage into multiple dataset chips; sheet datasets are provider/tool context only.
- OQ-013: Source workbook/file attachments use `ArtifactService`. The attachment is registered with `ArtifactService` when it is added to the Composer, and clicks open through `ArtifactService`.

## Resolved During `10-preprocessing-runtime-isolation`

- OQ-014: Large `data.transform` and `data.clean` execution uses a local preprocessing worker subprocess. The current product contract remains synchronous: AgentHarness waits for worker completion, derived dataset registration, and eager export artifact creation before the tool result is recorded.
