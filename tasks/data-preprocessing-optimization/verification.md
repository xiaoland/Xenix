# Verification Plan

## Phase 1 Tests

- Golden/contract test for `data.peek` over `4月堂食销售数据.xlsx` or a compact fixture with the same structure.
- Harness provider-message test proving compact provider-facing tool result projection.
- Query/transform boundary test proving column-name consistency.
- Failure contract test for mixed-type spreadsheet reads when a direct query cannot proceed.
- Loader wrapper unit tests for pandas and Polars placeholder/duplicate/unstable name cases.
- Bounded XLSX row-window test proving suspicious declared dimensions (`A1`) do not hide physical rows from the structure DSL.

## Proof Obligations

`data.peek` structure DSL:

- exposes bounded row and column evidence;
- does not make semantic header claims;
- exposes canonical executable `tool_name` values;
- includes loader/source names only as evidence.

Harness provider projection:

- avoids replaying full payloads when a compact provider projection exists;
- excludes human-facing markdown from provider-facing tool results;
- preserves enough information for next-call planning.

Canonical resolver:

- gives the same `tool_name` mapping to `data.peek`, `data.query`, and `data.transform`;
- handles empty, duplicated, loader-placeholder, and unstable names deterministically;
- confines loader-specific naming logic to the thin wrapper;
- supports index as a separate reference channel in DSL evidence.

Regression case:

- the real XLSX no longer causes a `__UNNAMED__1` vs `Unnamed: 1` mismatch between peek and transform;
- the LLM can use names returned by `data.peek` directly in downstream SQL;
- `SELECT column_23 FROM input LIMIT 5` or an equivalent canonical-name query can return the header-like `销售数量` evidence without DuckDB failing during registration/type conversion.
