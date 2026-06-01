# Issue 98 - Data Analysis And Interpretation

## Objective & Hypothesis

Issue: https://github.com/xiaoland/Xenix/issues/98

Objective: turn general data analysis and interpretation into service-backed Agent tools that are useful for non-technical business users, without exposing arbitrary local file access or freeform code execution.

Hypothesis: the first durable slice should introduce `analysis.profile` for bounded common descriptive analysis, while keeping `data.peek` focused on dataset metadata and preview lookup. This separates "what dataset is available and what are its fields" from "what descriptive evidence can be derived from the data", avoids raw freeform file access, and does not create a separate artifact for transient exploratory analysis.

## Input Classification

Intent.

The issue requests new product behavior:

- general descriptive analysis and common data exploration
- image/report-like outputs with unified save, preview, and export treatment, but not necessarily in the first slice
- more atomic data-analysis abilities for AI while avoiding unsafe freeform file access
- simple RAG-based knowledge base with active retrieval

## Current Facts

- `data.peek` currently registers/inspects a source file and returns row count, column metadata, and preview rows. Target semantics should remain dataset metadata and preview lookup, not full descriptive analysis.
- `data.clean` defines atomicity as an operation-centric contract: provider-facing schema stays compact, each operation is `{operation, params?}`, detailed parameter schemas are discoverable through metadata, and service code may perform complex deterministic work behind one named operation.
- `data.query` runs bounded read-only SELECT/CTE queries over registered datasets and returns tool-result payloads. It intentionally does not create artifacts by default.
- `data.transform` materializes SELECT/CTE output as a derived dataset artifact.
- `ArtifactService` already registers local artifacts and resolves `artifact://<artifact_id>` links, while still accepting legacy `view` query hints.
- Current artifact view hints include `preview`, `table`, `image`, and `report`.
- Query/transform SQL validation rejects mutation, DDL, direct file scans, extension management, and multi-statement shapes.
- Existing task sample `tasks/issue-98/common-descriptive-analysis.py` is a broad descriptive statistics script that exports an Excel report.

## Guardrails Touched

- PRD: `docs/10-prd/product-scope.md`
- Runtime boundary: `docs/20-product-tdd/runtime-boundaries.md`
- Artifact contract: `docs/20-product-tdd/artifact-links.md`
- Storage ownership: `docs/20-product-tdd/storage-ownership.md`
- Agent Harness unit contract: `docs/30-unit-tdd/agent-harness.md`
- Code likely affected:
  - `src/xenix/services/agent/tools.py`
  - new or existing data-analysis service under `src/xenix/services/`
  - targeted tests under `tests/`

## Candidate Slice A - `analysis.profile`

Add an LLM-facing `analysis.profile` tool for common descriptive statistics and exploratory evidence:

- Input: `dataset_id`, optional bounded controls such as top-N, correlation column cap, and explicit `target_columns`.
- The tool performs general descriptive analysis for a registered dataset and returns Markdown directly in the tool-call result.
- Service reads registered dataset source paths only, not arbitrary freeform paths or table payloads passed through the tool call.
- Output payload contains structured profile sections:
  - basic info: rows, columns, duplicate rows
  - field info: dtype, missing count/ratio, non-null count, unique count
  - field type groups: continuous numeric, binary, categorical/text, datetime
  - numeric stats: count, mean, std, min, quartiles, max, median, mode, skew, kurtosis, coefficient of variation
  - binary/category frequencies, bounded by top-N
  - datetime min/max/span
  - numeric correlation matrix, bounded by size
  - optional target-field grouped statistics if the contract is explicit and bounded
- Tool result: structured profile data plus the Markdown report in payload, with no persisted ToolCallResultMessage `content_blocks`.
- Artifact: none in the first slice. Profile output is exploratory evidence, not a durable user-openable file by default.

Why this slice: it is small enough to test, directly covers "通用描述性分析、常见的数据探索", and keeps data inspection (`data.peek`) separate from analysis/interpretation (`analysis.*`).

`data.peek` should stay focused:

- source-path registration/inspection for newly attached files, as current behavior requires
- lookup of row count, column count, column metadata, and preview rows for a registered dataset
- no descriptive statistics, correlations, grouped statistics, or chart rendering

## Candidate Slice B - Unified Rich Artifacts

Avoid designing a new "unified artifacts" subsystem first. The current `ArtifactService` already owns identity, preview payload, metadata payload, local path resolution, and thread/tool ownership.

First improvement should be local and should not depend on a new artifact kind or previewer:

- keep `analysis.profile` as direct Markdown in the tool result
- keep the existing dataset artifact registration for `preview`/source registration behavior
- defer report/image artifact generation until a later issue explicitly needs save, preview, or export semantics

Only introduce new artifact abstractions if profile output exposes missing behavior that cannot be represented by current rows.

## Candidate Slice C - Atomic Analysis Operations

The intended meaning of "atomic" should follow `data.clean`: one named operation with an explicit parameter schema, bounded inputs, deterministic service execution, structured payload, and bounded user-facing output. Atomic does not mean trivial internally; it means the Agent composes stable operations rather than writing freeform code or reading arbitrary paths.

After `analysis.profile`, add analysis operation tools only when each has a stable contract. Candidate namespace:

- `analysis.profile`
- `analysis.graph`
- `analysis.metadata` or `analysis.graph.metadata`
- later: `analysis.compare_groups`, `analysis.correlation`, `analysis.segment_summary`, `analysis.outlier.summary`

`analysis.graph` candidate contract:

- Input: `dataset_id`, `operation`, `params`.
- Operation examples:
  - `histogram`: one numeric column, optional bins, optional group column.
  - `bar_count`: one categorical column, optional top-N.
  - `scatter`: x/y numeric columns, optional color/group column.
  - `line`: x datetime/order column and y numeric column, optional group column.
  - `box`: numeric column by optional category column.
  - `correlation_heatmap`: bounded numeric-column set.
- `params_schema` should be discoverable like `data.clean.metadata`, not shoved into one large provider-facing enum-heavy schema.
- The service should validate column existence and kind, cap row count/category count/chart size, and reject arbitrary expressions or filesystem paths.
- Output should include structured chart metadata and an image artifact id, because graph output is a binary visual artifact rather than ordinary text. The model constructs `artifact://...` markdown image links from the system-prompt rule. This is separate from `analysis.profile`, whose first slice remains direct Markdown with no artifact.

Avoid a generic "run Python/lambda" tool in the first slice. Even if expression-like analysis is later useful, it needs a constrained expression/runtime contract; otherwise it conflicts with the current no-direct-filesystem and no-freeform-execution safety posture.

## Candidate Slice D - Active Knowledge Retrieval

RAG should be a later separate owner. It likely needs:

- knowledge source registration
- chunk/index persistence or app-managed files
- retrieval tool semantics
- provider prompt integration rules

It should not block the first data-analysis tool.

## Proposed First Implementation Shape

1. Solidify product and technical contract for `analysis.profile`, and confirm `data.peek` remains dataset metadata/preview only.
2. Implement a bounded descriptive-analysis helper/service under `src/xenix/services/`.
3. Register `analysis.profile` in AgentToolRegistry under the same contextual exposure rule as data tools for now: only when a file/dataset exists in the thread.
4. Return Markdown directly in the tool result, with a structured payload for provider follow-up.
5. Do not create a report artifact in the first slice.
6. Add targeted tests:
   - service common-analysis output on mixed CSV data
   - tool schema registration and execution
   - `analysis.profile` returns bounded Markdown and no artifact id
   - `data.peek` preserves current metadata/preview behavior
   - contextual exposure includes `analysis.profile` only when a file/dataset exists
7. Update durable docs after contract confirmation.

Implementation update: `analysis.graph` is now the next slice after `analysis.profile`:

1. Define graph operation shape as `{dataset_id, operation, params?}`.
2. Implement deterministic graph rendering behind service-managed operations.
3. Register generated image artifacts through `ArtifactService`.
4. Add tests for schema compactness, validation, artifact registration, and bounded output.

First implemented graph operations:

- `bar_count`
- `histogram`
- `scatter`
- `line`
- `correlation_heatmap`

Graph presentation update:

- `analysis.graph` returns `artifact_id` plus structured graph metadata, without `artifact_link` and without `content_blocks`.
- The Thread system prompt tells the model to reference image artifacts with Markdown image syntax, for example `![Amount distribution](artifact://<artifact_id>)`.
- Chatbot resolves artifact URIs in assistant markdown through `ArtifactService` and renders markdown image artifacts inline only for normal message markdown; clicking the rendered image opens the same artifact file, ordinary markdown artifact links remain clickable/openable too, and tool detail markdown downgrades image syntax to a plain link.
- No raw local path is exposed in the Message content.

Exposure rule refinement:

- `data.peek` remains the file/dataset metadata entry and can appear when a thread has an attached file or an existing dataset.
- `data.integrate` remains a file-intake tool and can appear when a thread has an attached file.
- Other `data.*` tools and all `analysis.*` tools appear only after thread tool payloads contain a dataset id.

## Verification

Executed:

- `pdm run pytest tests/test_analysis_graph.py tests/test_analysis_profile.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py::test_agent_harness_stream_filters_tools_by_thread_files tests/test_data_cleaning.py tests/test_data_transform.py tests/test_main.py::test_thread_detail_view_renders_inline_image_artifact_preview tests/test_main.py::test_thread_detail_view_renders_tool_image_artifact_preview tests/test_main.py::test_thread_detail_view_artifact_link_resolves_and_opens_file`
- `pdm run pytest tests/test_analysis_graph.py tests/test_analysis_profile.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py::test_agent_harness_stream_filters_tools_by_thread_files tests/test_data_cleaning.py tests/test_data_transform.py tests/test_main.py::test_thread_detail_view_renders_inline_image_artifact_preview tests/test_main.py::test_thread_detail_view_renders_tool_image_artifact_preview tests/test_main.py::test_thread_detail_view_artifact_link_resolves_and_opens_file tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell`
- `pdm run pytest tests/test_agent_harness_first_slice.py::test_agent_harness_first_slice_runs_from_file_to_apply_result tests/test_agent_harness_first_slice.py::test_agent_harness_first_slice_runs_inline_rows_to_apply_result tests/test_agent_harness_first_slice.py::test_agent_harness_exposes_and_uses_data_tools_after_prior_thread_file -q`
- `pdm run pytest tests/test_analysis_graph.py tests/test_analysis_profile.py tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py::test_agent_harness_stream_filters_tools_by_thread_files tests/test_data_cleaning.py tests/test_data_transform.py -q`
- `pdm run pytest tests/test_main.py::test_thread_detail_view_renders_inline_image_artifact_preview tests/test_main.py::test_thread_detail_view_renders_tool_image_artifact_preview tests/test_main.py::test_thread_detail_view_artifact_link_resolves_and_opens_file tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell -q`
- `pdm run pytest tests/test_main.py::test_thread_detail_view_expands_tool_event_detail tests/test_main.py::test_thread_detail_view_renders_tool_image_artifact_preview tests/test_main.py::test_thread_detail_view_renders_inline_image_artifact_preview tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell -q`
- `git diff --check`
- `pdm run python -m compileall -q src/xenix/services/analysis_profile.py src/xenix/services/analysis_graph.py src/xenix/services/agent src/xenix/services/storage/models.py`
- `pdm run i18n-extract`
- `pdm run i18n-compile`
- `pdm run check`
- `pdm run pytest tests/test_markdown_renderer.py tests/test_main.py::test_thread_detail_view_expands_tool_event_detail tests/test_main.py::test_thread_detail_view_renders_tool_image_artifact_preview tests/test_main.py::test_thread_detail_view_renders_inline_image_artifact_preview tests/test_main.py::test_thread_detail_view_artifact_link_resolves_and_opens_file -q`
- `pdm run pytest tests/test_analysis_graph.py tests/test_analysis_profile.py tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py::test_agent_harness_stream_filters_tools_by_thread_files tests/test_data_cleaning.py tests/test_data_transform.py tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell -q`
- `pdm run pytest tests/test_main.py -q`
- `git diff --check`

## Open Questions

- Should `analysis.profile` accept only `dataset_id`, or also allow `source_path` and register first? Current hypothesis: prefer `dataset_id`; the model can call `data.peek` first.
- Should common descriptive analysis include generated charts in the first slice? Current hypothesis: no; direct Markdown only.
- Should "target field grouping" be keyword-driven in service code or requested explicitly by tool args? Current hypothesis: explicit optional `target_columns` is safer than hard-coded Chinese business keywords.
- Should `analysis.graph` have one shared `analysis.metadata` catalog for all future analysis operations, or a narrower `analysis.graph.metadata` catalog? Current hypothesis: start with `analysis.graph.metadata` to keep scope bounded.
