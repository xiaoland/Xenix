# Issue 83 Data Cleaning Implementation Plan

## Objective & Hypothesis

- Objective: Convert the Issue 83 discussion into implementation slices that keep `data.clean` compact and leave DuckDB DSL work behind a separate boundary.
- Hypothesis: The safest route is to first clean up dataset ownership/lineage, then implement a Python-first `data.clean`, then design and implement a DuckDB DSL tool when the package implications are explicitly verified.

## Guardrails Touched

- Chatbot remains the user entry point.
- Agent tools remain LLM-facing contracts.
- `data.clean` stays limited to atomic predefined cleaning operations.
- DuckDB DSL work belongs to a separate LLM-facing tool.
- Project and Work Item concepts should not remain product-facing ownership anchors.
- Artifacts are produced durable outputs, not UI presentation behavior.

## Slices

### Slice 0: Dataset Ownership And Lineage Cleanup

- Goal: Remove Project as the effective dataset owner for the AI-first path and introduce explicit derived dataset lineage.
- Durable docs to update:
  - `docs/10-prd/product-scope.md`: record that the AI-first data workspace is conversation-led and dataset/artifact-centered.
  - `docs/20-product-tdd/storage-ownership.md`: define source dataset, derived dataset, and dataset lineage ownership.
  - `docs/20-product-tdd/runtime-boundaries.md`: record dataset registration/listing ownership after Project cleanup.
- Candidate changes:
  - Add a `derived_from_dataset_id` style field to dataset metadata.
  - Decide whether `copied_from` remains for byte-identical copies or is migrated away.
  - Replace project-scoped dataset registration/listing paths used by Agent tools with thread/session-neutral service calls.
  - Keep old Project storage only as a compatibility detail if immediate deletion creates too much blast radius.
- Verification:
  - Dataset registration tests.
  - Derived dataset lineage tests.
  - Existing ML task tests, because they currently carry `project_id`.

### Slice 1: Python-First `data.clean`

- Goal: Implement `data.clean` as an LLM-facing tool for atomic predefined cleaning operations on one dataset.
- Durable docs to update:
  - `docs/10-prd/product-scope.md`: describe data cleaning as a retained AI-first capability and clarify that Chatbot is the user-facing entry.
  - `docs/20-product-tdd/runtime-boundaries.md`: define `DataCleaningService` ownership and keep UI free of dataset parsing.
  - `docs/20-product-tdd/storage-ownership.md`: define cleaned dataset artifact storage and lineage metadata.
  - `tasks/issue-83-data-cleaning/result.md`: capture implementation outcome and residual follow-ups.
- Included operations:
  - Exact duplicate row removal.
  - Key-column duplicate policy if the rule is simple and auditable.
  - Missing value handling with explicit per-column or type-group strategies.
  - Basic type correction where Pandas can do it deterministically.
  - Text standardization such as trim, empty-string normalization, and simple value mapping.
  - Validation rules that report violations, with filtering only when explicitly requested.
- Excluded operations:
  - `profile`.
  - Open-ended SQL/DSL.
  - Join-heavy cleaning.
  - Fuzzy duplicate matching.
  - Text extraction.
  - Complex business-rule engines.
- Verification:
  - Service tests for each included operation.
  - Tool-boundary test for output dataset, artifact, lineage, report payload, and backward-compatible default behavior.

### Slice 2: DuckDB Query And Transform Tool Design

- Goal: Define the separate LLM-facing query and transform contracts before adding DuckDB as a dependency.
- Durable docs to update:
  - `docs/20-product-tdd/runtime-boundaries.md`: define the DuckDB DSL service boundary and allowed execution shape.
  - `docs/20-product-tdd/storage-ownership.md`: define output artifact and derived dataset rules for DSL-produced datasets.
  - `docs/40-deployment/development.md`: add planned dependency and verification notes only when the dependency is selected.
- Public LLM-facing tool names:
  - `data.query`: read-only SELECT/CTE over registered datasets; returns bounded rows and summary payloads.
  - `data.transform`: SELECT/CTE over registered datasets; materializes the result as a new derived dataset artifact.
- Internal implementation naming:
  - DuckDB belongs in service/validator names, not as a public `data.duckdb` tool.
- Contract constraints:
  - Registered datasets only.
  - SELECT/CTE-only query shape.
  - No runtime extension downloads by default.
  - `data.query` creates no dataset artifact by default.
  - `data.transform` output must be a new artifact/dataset, never in-place mutation.
  - Query, bindings, and validation summary must be auditable.
- Verification:
  - Static query validator tests.
  - Contract tests for rejected mutation statements.
  - Design review before dependency addition.

### Slice 3: DuckDB Dependency And Packaging

- Goal: Add DuckDB for `data.query` and `data.transform` execution once the public contracts are fixed.
- Durable docs to update:
  - `docs/40-deployment/development.md`: add DuckDB to runtime dependency and package verification guidance.
  - `docs/40-deployment/runtime-state.md`: add any DuckDB-related cache or artifact paths if introduced.
  - `docs/20-product-tdd/runtime-boundaries.md`: record packaged-runtime constraints such as registered datasets only and no implicit extension downloads.
- Candidate changes:
  - Add `duckdb` to runtime dependencies with a pinned compatible range.
  - Use in-memory DuckDB execution first.
  - Load registered CSV/XLS/XLSX datasets through Pandas DataFrames and register them as DuckDB input views.
  - Verify PyInstaller packaging with the available DuckDB hook.
  - Add packaged smoke coverage for a minimal DuckDB query.
- Verification:
  - `pdm install`.
  - `pdm run check`.
  - targeted DuckDB service tests.
  - `pdm run package`.
  - `pdm run smoke-package`.

### Slice 4: Dynamic Tool Family Loading

- Goal: Keep active LLM tools within budget if cleaning grows into multiple specialized tools.
- Durable docs to update:
  - `docs/20-product-tdd/runtime-boundaries.md`: define dynamic Agent Tool Registry loading, unloading, and scope.
  - `docs/00-meta/` or an Agent Harness unit doc if one exists by then: record the active tool budget target and tool-family lifecycle.
- Candidate shape:
  - `data.clean.list` exposes available cleaning subtools.
  - Loading is scoped to the current cleaning workflow.
  - Exiting the cleaning family unloads those subtools.
- Verification:
  - Agent Tool Registry tests for load/unload behavior.
  - Tool count budget tests with target maximum of 21 active tools.

## Current Recommendation

- Slice 0 and Slice 1 are implemented.
- Implement Slice 2 and Slice 3 together so the LLM can use `data.query` and `data.transform` for read-only analysis and derived-dataset transformation.
- Keep `data.clean` Python-first and compact while expressive SQL belongs to `data.query` and `data.transform`.

## Durable Documentation Promotion Plan

- Promote stable product truths to `docs/10-prd/product-scope.md` before code changes that expose new user-visible capabilities.
- Promote service and tool boundary truths to `docs/20-product-tdd/runtime-boundaries.md` before changing Agent tool schemas or adding services.
- Promote dataset lineage, artifact ownership, and generated dataset storage truths to `docs/20-product-tdd/storage-ownership.md` before schema or repository changes.
- Promote DuckDB runtime and packaging truths to `docs/40-deployment/development.md` and `docs/40-deployment/runtime-state.md` in the same slice that adds the dependency.
- Keep unsettled tool-family loading details in this task packet until the implementation slice is active.

## Durable Truth Candidates

- Chatbot is the user-facing entry point; `data.clean` is an LLM-facing tool.
- `data.clean` applies atomic predefined cleaning operations to one specified dataset and produces a new derived dataset.
- `profile` belongs outside `data.clean`.
- DuckDB-backed SQL belongs behind `data.query` and `data.transform`; `data.duckdb` is not exposed as an LLM tool.
- Artifacts are produced durable outputs such as datasets, reports, images, models, predictions, and other generated files.
- Dataset lineage should use explicit derived-from semantics.
- Project should exit the AI-first product ownership model.

## Open Questions

- How far Project cleanup should go before Issue 83 implementation starts.
- Whether `derived_from_dataset_id` should support only one parent in v1 or a parent list for integrated datasets.
- Whether validation rules in `data.clean` should only report by default.
- Whether multi-input transformed datasets need a first-class multi-parent lineage field beyond artifact metadata.
