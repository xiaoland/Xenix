# Phase 1 Scope

Phase 1 should include these together because they form one contract boundary:

1. `data.peek` compact JSON result for executable inspection/schema evidence.
2. Agent Harness tool-result replay convergence around canonical `result_payload`.
3. Column-name/loading consistency between `data.peek`, `data.query`, and `data.transform`.

## Rationale

A better `data.peek` is not enough if the names it exposes cannot be used by the next tools. Harness compaction is not enough if the compact facts are not executable. Column-name consistency is therefore part of the first useful slice, not a later polish item.

## Execution Constraint

The shared resolver must address both column naming and load/register behavior. A pandas-only rename after `read_excel` fixes the `__UNNAMED__1` vs `Unnamed: 1` mismatch but does not fix the mixed-type failure where DuckDB rejects header-like text such as `销售数量` in numeric-looking columns.

Phase 1 should therefore make query/transform registration use the same schema projection and a conservative read shape for messy spreadsheet exports, such as string-preserving XLSX reads before DuckDB registration.

## Out Of Phase 1

- Semantic header selection by the tool.
- Publishing a `candidate_header_row` claim as tool-owned truth.
- Automatic promotion of a spreadsheet row into business column names.
- Expanding the data-cleaning operation catalog.
- Persisting schema snapshots to storage tables.
- Human-facing Markdown/table rendering by Harness or tool handlers.
- A broad LLM service/provider DTO rename or architecture cleanup unless it directly blocks tool-result convergence.

## Durable Docs Follow-Up

Add an Agent Harness TDD constraint that tool-call results are LLM-facing lookup/planning surfaces. Human-facing explanation belongs in assistant messages authored by the LLM from tool evidence, not in Harness-packaged tool output.
