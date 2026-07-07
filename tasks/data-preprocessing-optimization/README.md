# Data Preprocessing Optimization

## Objective & Hypothesis

Objective: improve Xenix Agent's data preprocessing capability for real-world business spreadsheets, using `tasks/ml-service-optimizations/assets/4月堂食销售数据.xlsx` and Xenix thread `8e844868143140bba7a237a6dcea789c` as the first diagnostic case.

Hypothesis: the first valuable slice is not a larger cleaning catalog. It is a stronger inspection and planning contract: the Harness and `data.peek` should expose compact, operational facts that help the model choose the next safe tool call.

## Input Classification

- Type: `Reality`
- Mode: `Diagnose` moving toward `Solidify`
- Durable owner candidates:
  - Agent Harness provider-facing tool result projection
  - `data.peek` inspection/result payload
  - Thin tabular loader wrapper and column-name consistency
  - Data query/transform error repairability
  - Preprocessing skill/tool guidance

## Active Decisions

- This is an independent task, not part of `ml-service-optimizations`.
- Phase 1 includes `data.peek` structure DSL, Harness provider-facing result compaction, and column-name/loading consistency together.
- Provider-facing spreadsheet structure has one authoritative representation: JSON DSL.
- Agent Harness gives the LLM a reliable real-world interaction base. It does not pre-package human-facing explanation for the LLM.
- Markdown tables or narrative explanations belong in assistant messages authored by the LLM from tool evidence when the user needs them.
- The tool should not decide semantic claims such as which row is "the real header"; it should expose executable structure evidence and coordinates.
- Canonical column names are not stored directly on `dataset` table in Phase 1.
- Canonical column names are deterministic runtime projections from a shared thin loader/schema resolver.
- Loader-specific facts such as `Unnamed: n` and `__UNNAMED__n` must stay inside the loader wrapper boundary.
- Column index is valid as a separate reference channel, but name and index must not be mixed in one ambiguous field.

## File Map

- `evidence.md`: observed real-world failure chain and current code facts.
- `phase-1-scope.md`: first implementation slice.
- `structure-dsl.md`: provider-facing spreadsheet structure DSL.
- `canonical-columns.md`: canonical column reference design.
- `loader-wrapper-boundary.md`: where loader-specific logic belongs.
- `harness-tool-results.md`: Harness responsibility boundary for tool results.
- `source-notes.md`: notes from Polars/pandas docs and local asset scripts.
- `verification.md`: tests and proof obligations.
- `execution.md`: implementation notes and verification results.

## Next Step

Phase 1 implementation is in progress. Current verified slice covers canonical column projection, `data.peek` structure DSL, query/transform canonical XLSX execution, and compact Harness provider replay.
