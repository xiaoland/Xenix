# Change Map

## Durable Owners Touched

- Agent tool registry and tool payload contracts:
  - `src/xenix/services/agent/tools.py`
  - `src/xenix/services/agent/tool_presentations.py`
  - Agent skills and dev fixtures
- Agent Harness result replay:
  - `src/xenix/services/agent/harness_service.py`
  - conversation/tool-call storage surfaces
  - provider-facing tool-result text projection
- Dataset service and storage:
  - `src/xenix/services/dataset_service.py`
  - `src/xenix/services/dataset_inspection.py`
  - `src/xenix/services/storage/models.py`
  - `src/xenix/services/storage/migrations.py`
- Data execution:
  - `src/xenix/services/data_transform.py`
  - `src/xenix/services/tabular.py`
  - cleaning/tokenization/analysis services that load registered datasets
- ML:
  - `src/xenix/services/ml/dataset_loader.py`
  - `src/xenix/services/ml_service.py`
  - `src/xenix/services/ml_task_service.py`
- Link activation and artifacts:
  - `src/xenix/services/link_router.py`
  - `src/xenix/services/dataset_export_service.py`
  - `src/xenix/services/artifact_service.py`
- UI:
  - `src/xenix/ui/chatbot.py`
  - `src/xenix/ui/main_window.py`
  - translation catalogs
- Durable docs:
  - `docs/10-prd/`
  - `docs/20-product-tdd/`
  - `docs/30-unit-tdd/`
  - `docs/40-deployment/`

## Blast Radius

- Existing runtime DB rows may have legacy dataset semantics. This is tracked by OQ-001.
- The lazy `dataset://` path committed in `542561f` is now superseded locally. The current slice updates `LinkRouter`, dataset-producing tool payloads, System Prompt, durable docs, UI tests, and artifact-link tests together.
- Packaging now depends on `xlsxwriter` for Polars XLSX export. This is tracked by OQ-005.
- Remote ML worker staging may need explicit Parquet-path verification. This is tracked by OQ-006.
- Future Agent behavior depends on skills and prompt guidance avoiding stale `data.peek` recipes.
- Deferred attachment import crosses the UI/Harness boundary: Chatbot UI owns source artifact registration and optimistic rendering, while AgentHarness owns source artifact import, durable user-turn creation after successful import, provider gating, and ready dataset block projection.
- UserMessage rendering for attachments should stay workbook/file-level; dataset rows created from workbook sheets should not become visible UserMessage chips.
- Composer attachment adds should register source workbook/file artifacts through `ArtifactService` for later UserMessage click/open behavior.
- Large preprocessing execution is a cross-boundary concern: `data.transform`, `data.clean`, dataset registration, dataset export, AgentHarness streaming, UI event projection, and observability all participate in the user-visible stall surface. Treat it as a runtime-boundary change, not a local UI rendering bug.
- The first runtime-isolation slice moves `data.transform`, `data.clean`, generated dataset registration, and eager workbook export artifact materialization into a local preprocessing worker subprocess. `data.query` stays in-process because it is bounded and creates no dataset/artifact.
- Xenix Table Text changes the provider-facing representation of tabular tool results. The primary implementation blast radius is AgentHarness provider-message replay, `data.query`, generated dataset inspection previews from `data.integrate` / `data.transform` / `data.clean` / `data.tokenize`, shared result formatting, tests that parse tool result JSON, and durable Agent Harness docs/skills that describe tool-result shape.

## Invariants

- Tools must not expose raw local filesystem paths as user-facing links.
- LLM-authored SQL must use aliases, not service-owned file paths.
- Internal app-owned Parquet files are not user-openable artifacts by default.
- User-visible dataset result links should point at export artifacts, not dataset ids. Tool payloads should carry `dataset_id` and `artifact_id`, while the System Prompt teaches the model to form `artifact://<artifact_id>` links. Artifact activation must not perform dataset lookup fallback.
- Failed transforms must not create half-success durable datasets.
- Local file attachment paths must not reach provider-facing content; after deferred import, provider requests may include only ready dataset blocks.
- Once Send is accepted, the attachment import stage is not cancellable.
- AgentRun rows for source-attachment turns are created only after attachment import succeeds.
- Import failure must restore the submitted text and source attachments to Composer, roll back the optimistic user message to the previous stable message view, avoid durable half-turns, and project an error item in the message list.
- Large preprocessing must not monopolize the Qt application process. A background Python thread is not a sufficient isolation boundary for full-table materialization, Pandas-heavy cleaning, DuckDB result export, or workbook export creation.
- `data.transform` must not fetch the full output relation into Pandas before writing Parquet.
- Service-layer query/transform result objects and tool `result_payload` objects should remain structured and testable. Xenix Table Text belongs to AgentHarness provider-facing tool-result projection, not core tabular execution and not tool implementation output.
