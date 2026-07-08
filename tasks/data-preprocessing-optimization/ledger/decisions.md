# Decisions

## Current Durable Decisions

- `data.peek` is removed from the Agent-facing tool surface. Historical `data.peek` notes are archived and must not drive future implementation.
- `data.query` is the atomic read-only probing surface for registered datasets.
- `data.transform` is the durable transformation surface. It may run bounded DuckDB scripts, but scripts must leave a final relation named `output`.
- Tool results use canonical compact `result_payload`. Ordinary tools should not emit Markdown or `content_blocks` as a normal LLM-facing result shape.
- The compact table pattern is cross-tool: repeated rows should prefer `{"_schema": {"key": index}, "data": [[...]]}` when it improves signal-to-noise.
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

## Explicit Non-Decisions

- This task does not perform a broad LLM service/provider DTO cleanup unless it directly blocks tool-result convergence.
- This task does not make tools decide semantic header rows for messy spreadsheets.
- This task does not require immediate deletion of `agent_tool_call`; the table still owns invocation ledger, status, arguments, errors, message linkage, and observability identity.
- This task does not make CSV disappear from user-facing exports or reports.
