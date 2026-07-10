# Decisions

## Current Durable Decisions

- `data.peek` is removed from the Agent-facing tool surface. Historical `data.peek` notes are archived and must not drive future implementation.
- `data.query` is the atomic read-only probing surface for registered datasets.
- `data.transform` is the durable transformation surface. It may run bounded DuckDB scripts, but scripts must leave a final relation named `output`.
- Tool results use canonical compact `result_payload`. Ordinary tools should not emit `content_blocks` as a normal LLM-facing result shape.
- Superseding target for Agent-facing tabular result projection: use Xenix Table Text, a YAML-style metadata block plus Markdown table or records block. This replaces compact JSON `_schema` plus `data` for tabular data when the result is meant to be read by the LLM.
- Xenix Table Text is owned by AgentHarness provider-facing replay only. It must not become a service-layer return type, a tool implementation output schema, a persisted/provider-facing dual payload split, or a `content_blocks` mechanism.
- Provider-facing replay for tabular tool results must return the Xenix Table Text directly, without wrapping it in a JSON object.
- `data.query` and generated dataset previews from `data.integrate`, `data.transform`, `data.clean`, and `data.tokenize` are in scope for Xenix Table Text. Non-tabular `data.clean.metadata`, `data.feature.select`, and operation reports remain structured.
- The compact table pattern remains available for non-provider internal JSON payloads and non-tabular structured values, but should not be the default LLM-facing representation for tabular previews/query results.
- Tool parameter schemas should stay compatible with conservative provider JSON Schema subsets. Do not rely on `anyOf` / `oneOf` for Moonshot-facing tool schemas.
- When both `bindings` and `dataset_id` are supplied to query/transform tools, `bindings` wins. This should be documented in schema descriptions and enforced in execution.
- A dataset is an app-owned tabular table, usually Parquet. Original CSV/XLS/XLSX files are import provenance, not execution authority.
- Workbook imports can produce multiple datasets, usually one non-empty sheet per dataset.
- App-owned Parquet is the internal registered-dataset format for data tools and ML. CSV is import/export interchange, not durable internal storage.
- User-authored SQL may reference only registered aliases. Service-owned file reads are implementation details and must not expose filesystem authority to the LLM.
- `artifact://<id>` is artifact-id authority only. It must not fall back to dataset lookup.
- Superseding target decision: remove `dataset://` globally. Dataset ids are tool/input identities, not clickable link authorities.
- Derived dataset-producing tools should synchronously create a corresponding user-openable export artifact before returning and should return `dataset_id` plus `artifact_id`.
- Tool payloads should not return `artifact_uri`. The System Prompt owns the `artifact://<artifact_id>` URI format and should explain that artifacts are user-openable/previewable business outputs.
- The committed `dataset://` lazy activation design is now historical. Keep `LinkRouter`, but it should route service-owned user links through `artifact://` artifact activation and ordinary external links, not dataset activation.
- Link activation for service-owned URIs belongs to `LinkRouter`.
- Artifact file opening belongs to `ArtifactService`.
- Dataset export materialization still belongs to a dataset/export service boundary; it should be called by derived-dataset tool completion instead of by lazy link activation.
- UI may choose execution mode for link activation, but must not parse datasets, resolve service-owned paths, or open artifact files itself.
- Dataset export should use Polars for registered dataset export paths. Pandas export is not the intended path.
- Dataset export progress must not block main-window interaction. Current UI surface is non-modal and i18n-aware.
- New target decision: source file attachment import should move out of Chatbot UI preflight and into AgentHarness-owned turn startup after the user clicks Send. UI should render the submitted message and thinking state immediately; AgentHarness should import files into ready dataset blocks before any LLM provider request.
- AgentHarness should import source attachment artifacts before persisting the real user turn for that submission. UI-owned optimistic rendering provides immediate feedback; durable conversation state should not contain a half-sent user turn when source import fails.
- Once Send is accepted for a message with source file attachments, the submitted attachment import is not cancellable.
- UserMessage attachment presentation is workbook/file-level. It must not expand imported worksheets into visible dataset chips; imported sheet datasets are provider/tool context only.
- Deferred import does not need a separate visible "importing datasets" event. The normal submitted-message plus thinking/running state is the user-visible waiting state.
- AgentRun rows for turns with source file attachments are created only after attachment import succeeds. Import failure is a pre-run failure, not a failed provider run.
- Source workbook/file attachments are registered with `ArtifactService` when they are added to the Composer. UserMessage attachment clicks open through `ArtifactService`.
- If deferred attachment import fails, the original user text and source attachments return to the Composer and the message list shows an error item.
- Large `data.transform` and `data.clean` execution should not run in the desktop UI process. They dispatch full-data execution through a local preprocessing worker subprocess while preserving the current synchronous Agent tool-call contract.
- Generated dataset registration and eager workbook export artifact materialization for dataset-producing tools also run through the preprocessing worker boundary, so full-table copy/export work does not return to the GUI process.
- `data.transform` writes the final DuckDB `output` relation directly to Parquet and must not fetch the full transform output into Pandas.
- `data.clean` writes derived cleaning output as Parquet. Its current operation catalog may still use Pandas internally, but that Pandas work is isolated inside the preprocessing worker process.

## Explicit Non-Decisions

- This task does not perform a broad LLM service/provider DTO cleanup unless it directly blocks tool-result convergence.
- This task does not make tools decide semantic header rows for messy spreadsheets.
- This task does not require immediate deletion of `agent_tool_call`; the table still owns invocation ledger, status, arguments, errors, message linkage, and observability identity.
- This task does not make CSV disappear from user-facing exports or reports.
