# Issue 83 Data Cleaning Exploration

## Objective & Hypothesis

- Objective: Define the product and technical route for foundational data-cleaning capability in the Chatbot-first native app.
- Hypothesis: Issue 83 needs a compact `data.clean` tool for atomic predefined cleaning operations, plus a separate DuckDB DSL tool for expressive relational cleaning when needed.

## Prompt

- GitHub Issue 83 requests foundational data-cleaning capabilities across missing values, duplicates, type correction, standardization, outliers, inconsistencies, invalid data, parsing, join validation, and business rules.
- Prior handoff: `tasks/native-ai-first/data-cleaning-handoff.md`.
- Current discussion direction: keep `data.clean` on predefined atomic capabilities, avoid `profile` inside `data.clean`, and use a separate DuckDB DSL tool for richer LLM-authored transformations.

## Guardrails Touched

- Product scope: Chatbot is the non-technical user entry point.
- Agent Harness: LLM-facing tools should have stable, precise, auditable schemas.
- Runtime boundaries: UI calls services; services own workflow semantics and dataset artifact production.
- Storage ownership: SQLite stores metadata; filesystem stores artifact bytes such as datasets, reports, images, model binaries, and predictions.
- Deferred transform: DuckDB DSL should have a separate tool boundary.

## Current Facts

- Current `data.clean` accepts `dataset_id`, optional `name`, and optional `drop_duplicates`.
- Current behavior is implemented inside `src/xenix/services/agent/tools.py`.
- Existing behavior writes a cleaned CSV under `artifacts/datasets/cleaned/`, registers a dataset row, registers a dataset artifact, and returns inspection plus artifact link.
- `data.clean` is an LLM-facing tool. Chatbot is the non-technical user entry point.
- A DuckDB-backed DSL can give the LLM more expressive power for relational cleaning, filtering, type coercion, deduplication, validation queries, and rule-based transformations.
- Current `pyproject.toml` has no DuckDB dependency.
- Current `xenix.spec` has no DuckDB-specific PyInstaller hook, hidden import, or binary/data collection rule.
- Current storage and service code still has `ProjectRow`, `ProjectService`, `project_id`, and project-scoped dataset queries.
- Current Agent tools hide this by resolving or creating a default project when no `project_id` is provided.

## Decisions Emerging

- `data.clean` should mean: apply a set of atomic predefined cleaning operations to one specified dataset and produce a new derived dataset.
- `profile` should not be part of `data.clean`.
- If preset profiles are needed later, they should be represented by a separate tool or loaded subtool, not mixed into `data.clean`.
- `data.clean` may include capabilities such as `duplicate_policy`, `missing_policy`, `type_corrections`, `text_standardization`, and `validation_rules`, as long as the schema stays compact.
- Cleaning operations that need only a small, stable DuckDB expression may remain inside `data.clean` when they are common enough to deserve a named preset.
- More open-ended DuckDB DSL cleaning belongs in a separate LLM-facing tool.
- `DataCleaningPlanner` should mean deterministic service-layer planning and validation logic, not another LLM agent.
- Keep `data.clean` small. If the schema grows into many specialized behaviors, split those behaviors into dedicated tools.
- A possible future split mechanism is `data.clean.list`: load only the cleaning subtools for the current turn/workspace and unload them after leaving the cleaning tool family. This protects the global LLM tool budget.
- Tool count guidance: keep active tools within 21.
- Execution preference: use Python/Pandas service code for operations that are straightforward in Python; use DuckDB where relational SQL is materially clearer or safer.
- Dataset lineage should support a separate `derived_from_dataset_id` style field for cleaned or transformed datasets. Do not overload `copied_from` if its semantics remain copy-oriented.
- Project cleanup should be treated as a preceding or parallel migration because Issue 83 touches dataset registration and lineage.
- Thread, dataset, artifact, and lineage should not be modeled as a single chain. Thread/turn is interaction context; dataset lineage is a dataset-to-dataset graph; artifact is a produced durable output such as a dataset, report, image, model, prediction file, or other generated file.

## Unknowns

- Exact tool name for the DuckDB DSL boundary.
- Exact dividing line between `data.clean` presets and DuckDB DSL.
- Whether the first implementation should include the DSL tool in the same slice or define it and defer execution.
- How much validation reporting belongs in `data.clean` versus the future DSL tool.
- How generated/copy lineage should be represented in dataset listing semantics.
- How to phase out or reinterpret `ProjectRow`, `project_id`, and project-scoped dataset queries now that the product path is Chatbot/thread-first.
- Exact DuckDB introduction point and packaging strategy.
- Whether `copied_from` is retained for byte-identical copies or renamed/migrated.

## Constraints Observed

- Keep LLM-facing tools JSON-schema friendly.
- Preserve generated dataset registration and artifact output behavior.
- Keep SQL execution bounded to registered datasets and generated artifacts.
- Keep domain behavior in services when it grows beyond tool orchestration.
- Keep UI free of CSV/XLSX parsing and business decisions.
- Keep `data.clean` limited to frequent operations that are easy to describe and easy to audit.
- Use separate tools for complex, custom, join-heavy, or DSL-heavy cleaning.
- Treat Project references in current code as an implementation reality to resolve, not as product-facing vocabulary for Issue 83.
- Do not add DuckDB until a slice truly needs it. Python/Pandas remains preferred for simple `data.clean` operations.
- If DuckDB is added, package verification must include packaged smoke coverage, not only unit tests.
- Avoid DuckDB runtime extension downloads in packaged builds unless explicitly designed and verified.

## Candidate Paths

1. Two-tool route:
   - `data.clean`: predefined common cleaning policies.
   - `data.transform` or `data.query`: DuckDB DSL for expressive transformations.
2. Split-by-complexity route:
   - `data.clean`: named operations and tiny expressions for frequent business cleaning.
   - DuckDB DSL tool: multi-step, join-heavy, window-heavy, or custom expression-heavy cleaning.
3. Staged route:
   - First implement service-backed `data.clean`.
   - Next define and implement DuckDB DSL tool after preset behavior is stable.
4. Tool-family route:
   - Keep the always-loaded tool list small.
   - Add `data.clean.list` only when cleaning requires multiple specialized subtools.
   - Load cleaning subtools on demand and unload them after the cleaning family is exited.

## Verification Anchors

- Tool spec tests cover `data.clean` schema and backward compatibility.
- Service tests cover duplicate, missing, type correction, text standardization, and validation summaries.
- DuckDB DSL tests, when added, verify SELECT/CTE-only execution, registered dataset binding, and generated artifact registration.
- Tool-boundary tests verify artifact link, parent lineage metadata, and inspection payload.

## Smallest Confirmation Needed

- Confirm the two-tool route.
- Confirm first implementation scope for `data.clean`.
- Decide whether DuckDB DSL tool is in the same implementation slice or only designed now.

## Promotion Candidate Truths

- Leave empty until design is stable and verified.
