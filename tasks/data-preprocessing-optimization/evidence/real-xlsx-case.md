# Evidence

This file is raw diagnosis evidence. It contains historical observations from before `data.peek` was removed. Current decisions live in `../ledger/decisions.md`.

## Case Inputs

Primary evidence file:

- `tasks/ml-service-optimizations/assets/4月堂食销售数据.xlsx`

Primary Xenix thread:

- id: `8e844868143140bba7a237a6dcea789c`
- title: `查看4月堂食销售数据`
- model: `kimi/kimi-k2.5`
- messages: 44
- tool calls: 14

Focused diagnosis:

- `tasks/ml-service-optimizations/data-peek-harness-diagnosis.md`

## Observed File Shape

The file is a realistic exported business report rather than a clean analytical table.

- row 1: report title-like cell `品项销售明细`
- row 2: long filter-condition text
- row 3: dense row with 50 business-looking labels
- row 4+: dense data rows
- workbook dimensions are suspicious in `openpyxl` (`max_row=1`, `max_column=1`), while streaming/calamine sees the full sheet

## Observed Tool Failures

- `data.peek` succeeds but reports placeholder columns like `__UNNAMED__1`.
- `data.transform` sees pandas-style columns like `Unnamed: 1`, so the first transform fails on column-name mismatch.
- `data.query SELECT * FROM input LIMIT 5` fails because pandas/DuckDB hits mixed header/data types such as `销售数量` inside a numeric-looking column.
- Later derived CSVs still hit runtime/type inference issues.

## Local Runtime Checks

- Polars/calamine read the full file as `(486122, 50)` in about 27 seconds, with schema names `品项销售明细`, `__UNNAMED__1`, ... and every column as `String`.
- pandas small-sample read sees names `品项销售明细`, `Unnamed: 1`, ... and mixed/object dtypes for amount/count columns.
- The active `.venv` has `polars==1.42.1`, `polars-runtime-32==1.42.1`, `fastexcel==0.20.2`, `pandas==3.0.3`, and `openpyxl==3.1.5`.

## Problem Claims

1. `data.peek` currently gives the model many derived frequencies but not enough operational structure evidence for messy spreadsheet exports.
2. The provider sees too much raw payload and too little prioritized contract: executable column names, row/column coordinates, type evidence, and repairable next-call facts.
3. Tool-to-tool inconsistency means the model cannot reliably use column names returned by `data.peek` in `data.query` or `data.transform`.
4. Query/transform failures are not only model mistakes; the service boundary can fail before SQL semantics matter because the loader tries to coerce mixed-type spreadsheet columns.

## 2026-07-07 Follow-Up Thread

Observed Xenix thread:

- id: `c1eddca9396c4f3ba18aaa54e8be8805`
- title: `清洗4月堂食销售数据`
- model: `kimi/kimi-k2.5`
- active runtime DB: `C:\Users\yyh\AppData\Local\Xenix\state\xenix.db`
- dataset id: `60965a1f625f481fb1a52d0ae05d734d`
- source path: `tasks/ml-service-optimizations/assets/4月堂食销售数据.xlsx`

Observed outcome:

- 48 messages, 16 tool calls, 15 provider requests, 0 artifacts.
- The first `data.peek` succeeded with `analysis=false`.
- The first downstream `data.transform` referenced `__UNNAMED__1` and failed.
- The next `data.transform` referenced `column_1` and failed.
- `data.query SELECT * FROM input LIMIT 3` then revealed the executable columns are `品项销售明细`, `column_2`, `column_3`, ...
- Two later `data.transform` calls failed with `tabular_runtime_unavailable` after materializing derived CSV files, so transform has a side-effect ordering risk.
- `data.clean.metadata` failed once because the model called group `missing_values`; the valid group is `missing`.
- Final assistant messages overstated completion: the thread produced diagnostics and failed transform attempts, not a successful durable cleaned dataset.

Provider/history size facts:

- `data.peek` persisted result was about 26 KB.
- `data.peek` provider-facing `tool_result` was still about 25 KB.
- The provider projection included `inspection` at about 9 KB and `structure` at about 15.8 KB.
- Replayed tool-result JSON across the thread totaled about 59.6 KB.
- Assistant `provider_payload` persisted raw streaming chunks; several assistant rows were 80 KB to 387 KB. Current provider serialization ignores most of that payload, but storage/snapshot still carry unnecessary provider raw data.
- Provider request input grew from about 12K tokens after the first tool calls to about 26K tokens by the end.

Updated diagnosis:

1. Phase 1 fixed loader placeholder mismatch enough for canonical SQL names to exist, but `data.peek` still presents competing naming systems: `inspection` exposes loader names such as `__UNNAMED__1`, while `structure.columns` exposes executable names such as `column_2`.
2. The tool does expose row 3 as a dense 50-column business-header row, but it does not publish an explicit operational projection such as "candidate header row is row 3; executable columns map index 1 -> `column_2` -> `机构编码` evidence." The model is left to infer the execution plan from large evidence.
3. The first column remains `品项销售明细`, not `column_1`, because the resolver preserves non-placeholder loader names. This is technically consistent but poor for messy report exports where row 1 is a title, not a field name.
4. The persisted/provider-facing split is not clearly owned. Tool handlers create provider projections, Harness stores them inside `agent_message.provider_payload.tool_result`, and `ConversationStore` decides replay fallback. This works mechanically, but the boundary is implicit and makes every tool handler a multi-consumer projection owner.
5. Production Harness is wired through `LLMService`, but `AgentHarnessService` still has raw `AgentProvider` bypass seams for tests/fallback. The deeper naming smell is that the canonical LLM interface still uses provider-shaped DTOs (`ProviderMessage`, `ProviderResponse`) across Harness and LLM service boundaries.
