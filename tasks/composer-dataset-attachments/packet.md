# Composer Dataset Attachments

## Objective & Hypothesis

- Objective: Redesign Composer file intake so supported tabular uploads become registered datasets before they reach Agent/LLM interaction.
- Hypothesis: The LLM-facing boundary should operate on opaque `dataset_id` values and safe dataset projections, while local filesystem paths stay inside service-owned execution boundaries.

## Guardrails Touched

- UI layer: Composer file selection/drop intake, attachment chips, submission payload, and user-visible validation.
- Agent Harness: user message content blocks, provider-facing history projection, contextual tool exposure, thread-title prompts, and tool execution context.
- Agent tools: `data.peek`, `data.integrate`, and any schema/result payloads that currently expose `source_path` or `source_paths`.
- Dataset service: registration and inspection remain the durable owner of local source paths, but provider-facing projections must hide them.
- Storage/runtime docs may need promotion after implementation, because this changes the LLM-facing data access contract.

## Verification

- Static checks:
  - Provider-facing request payloads must not include absolute local paths from Composer uploads.
  - LLM-facing tool schemas must not expose `source_path` or `source_paths` for uploaded datasets.
  - Tool result payloads sent back through provider history must not include `inspection.source_path`.
- Targeted tests:
  - Composer accepts only `.csv`, `.xlsx`, `.xls` attachments for dataset intake.
  - Submitting an attached supported file registers a dataset and sends a dataset attachment block, not a file path block.
  - `data.peek` operates by `dataset_id`.
  - `data.integrate` operates by `dataset_ids`.
  - Thread-title generation uses safe file names / dataset display names only.
- Regression search:
  - Search provider-facing code and tests for `Attached file:` / `source_path` leakage.

## Current Understanding

- Composer pending attachments remain local UI state until send.
- On send, supported `.csv`, `.xlsx`, and `.xls` files are registered through `DatasetService` and turned into safe dataset attachment blocks.
- `SubmitUserTurnInput` now carries `dataset_attachments` rather than path-bearing `file_paths`.
- User message blocks use `{"type": "dataset", ...}` and include `dataset_id`, display name, basename, source format, shape, and preview column names.
- Provider-facing projections and thread-title prompts use safe dataset metadata only.
- `data.peek` accepts `dataset_id`, resolves the internal source path through `DatasetService`, and returns safe inspection/profile payloads without `source_path`.
- `data.integrate` accepts `dataset_ids` and records input dataset ids for generated outputs.
- Uploaded input datasets are source datasets, not artifacts; generated outputs remain artifact-owned.

## Current State

- Input Type: Constraint.
- Active Mode: Execute / Verify.
- Supporting Files:
  - `tasks/composer-dataset-attachments/implementation-plan.md`
- Durable Owner Forecast:
  - Product-facing behavior: Chatbot/Composer dataset attachment workflow.
  - Technical contract: Agent Harness provider-facing projection and data tool schemas.
  - Service authority: DatasetService owns local source path resolution and dataset registration.
- Temporary Assumption: Source datasets remain user-managed external files; Xenix stores their paths internally for service execution but does not expose those paths to the Agent/LLM.

## Proposed Target Contract

- Composer accepts only supported tabular dataset files: `.csv`, `.xlsx`, `.xls`.
- Local file paths are used only inside UI/service boundaries to register datasets.
- Agent user messages store dataset attachment references such as `dataset_id`, display name, file name, row/column shape, and safe column metadata.
- Provider-facing messages never include absolute filesystem paths.
- `data.peek` accepts `dataset_id` and optional analysis controls.
- `data.integrate` accepts `dataset_ids`.
- Generated outputs, charts, reports, models, and exported/apply files remain artifact-owned; user-uploaded input datasets are dataset-owned.

## Negotiation Triggers

- If implementation requires changing SQLite schema or persisted content-block semantics beyond additive-safe message projection, pause for impact handshake.
- If existing durable docs claim source-path tool access as the LLM-facing contract, update PRD/Product TDD first.
- If source datasets should be copied into app-managed storage instead of referencing user-managed files, pause because that changes storage ownership and backup/reset behavior.

## Next Step

- Run final focused tests, i18n checks, static leakage scans, and `pdm run check`.
- Record final verification results here before handoff.

## Verification Log

- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py tests/test_analysis_profile.py -q`
- Passed: `pdm run pytest tests/test_agent_harness_foundation.py tests/test_agent_ai_observability.py tests/test_main.py -q`
- Passed: `pdm run pytest tests/test_data_transform.py tests/test_data_cleaning.py tests/test_analysis_graph.py tests/test_analysis_profile.py -q`
- Passed individually after i18n state pollution was suspected: `pdm run pytest tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell tests/test_i18n.py::test_startup_splash_language_switch_updates_stage_text -q`
- Completed: `pdm run i18n-extract`
- Completed: `pdm run i18n-compile`
- Fixed verification-discovered QApplication translator leakage in `TranslationManager`, then passed: `pdm run pytest tests/test_agent_ai_observability.py tests/test_main.py tests/test_i18n.py -q`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py tests/test_analysis_profile.py tests/test_main.py tests/test_i18n.py -q`
- Passed: `pdm run check`
- Passed: `pdm run test` (`228 passed`)
- Passed: `git diff --check`
- Completed leakage scan: `source_path` remains only in internal service resolution and durable docs; `file_paths` remains only in UI-local pre-registration method arguments; no `Attached file:` provider projection remains.
