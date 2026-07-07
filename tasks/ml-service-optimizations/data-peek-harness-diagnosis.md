# data.peek Harness Diagnosis

## Objective & Hypothesis

Objective: diagnose thread `8e844868143140bba7a237a6dcea789c` against real file `assets/4月堂食销售数据.xlsx`, starting from `data.peek`.

Hypothesis: the first durable fix should improve the Agent-facing inspection/result contract before adding broader preprocessing behavior. The current `data.peek` response has low signal-to-noise and misses structural warnings needed for messy exported spreadsheets.

## Guardrails Touched

- Input class: `Reality`.
- Active mode: `Diagnose`.
- Durable owner candidates:
  - Agent Harness provider-facing tool result projection.
  - `data.peek` payload shape in `src/xenix/services/agent/tools.py`.
  - Dataset/tabular loading consistency across `data.peek`, `data.query`, `data.transform`, and `data.clean`.
- No durable code has been changed.

## Evidence

- Xenix thread:
  - id: `8e844868143140bba7a237a6dcea789c`
  - title: `查看4月堂食销售数据`
  - model: `kimi/kimi-k2.5`
  - messages: 44
  - tool calls: 14
- Source dataset:
  - dataset id: `22dae9e9722c45b6a4cce8d799e3e011`
  - source path: `F:\CODING\Project\Xenix_native\tasks\ml-service-optimizations\assets\4月堂食销售数据.xlsx`
  - source format: `XLSX`
- First `data.peek` call:
  - call id: `4ff2c9086be04091b0759b795b6b7899`
  - args: `{"dataset_id": "...", "analysis": true, "top_n": 20}`
  - status: `SUCCEEDED`
  - provider-facing wrapped result size: about 28,006 JSON chars
  - next provider request input: 18,175 tokens

## Current Understanding

The real XLSX is a difficult exported report:

- workbook declared dimensions are suspicious (`openpyxl` reports `max_row=1`, `max_column=1`);
- streaming rows reveal the real structure:
  - row 1: title-like single cell `品项销售明细`
  - row 2: long filter-condition text
  - row 3: real business header row with 50 columns
  - row 4+: data rows
- attachment metadata previously handles this better than the general data tooling path.

The first successful `data.peek` result does show preview rows containing the real header row, but it does not promote that fact into an explicit structural diagnosis. It reports columns as `品项销售明细`, `__UNNAMED__1`, ..., `__UNNAMED__49`, then spends most of the response budget on field info and value frequencies under those unstable placeholder names.

The subsequent failures show two independent problems:

1. Name mismatch between tools:
   - `data.peek` exposed `__UNNAMED__1` style names.
   - `data.transform`/DuckDB saw `Unnamed: 1` style names through pandas.
   - First transform failed with `Referenced column "__UNNAMED__1" not found`.
2. Loader/type mismatch between inspection and query/transform:
   - `data.peek` uses Polars/calamine through `load_tabular_frame`.
   - `data.query` and `data.transform` load through pandas.
   - pandas/DuckDB hit mixed header/data types and failed even for `SELECT * FROM input LIMIT 5` with `Could not convert string '销售数量' to DOUBLE`.

Local `.venv` spot checks:

- Polars/calamine read the full file as `(486122, 50)` in about 27 seconds, with schema names `品项销售明细`, `__UNNAMED__1`, ... and every column as `String`.
- pandas small-sample read sees names `品项销售明细`, `Unnamed: 1`, ... and mixed/object dtypes for amount/count columns.
- The active `.venv` has `polars==1.42.1`, `polars-runtime-32==1.42.1`, `fastexcel==0.20.2`, `pandas==3.0.3`, and `openpyxl==3.1.5`.

Harness-side provider projection makes the response noisier:

- `ConversationStore._tool_result_to_text()` serializes the entire `AgentToolCallRow.result_payload` as provider-facing JSON.
- Tool result messages persist empty `content_blocks`; `ToolExecutionResult.content_blocks` are not used for provider-facing replay.
- `data.peek` payload contains both structured profile and `analysis.markdown`, duplicating content in the same provider result.

## Problem Claims

1. `data.peek` currently gives the model many derived frequencies but not enough operational guidance for messy spreadsheet structure.
2. The provider sees too much raw payload and too little prioritized contract: exact usable column names, suspected header row, rows to skip, type risks, and recommended next tool call.
3. Tool-to-tool inconsistency means the model cannot reliably use column names returned by `data.peek` in `data.query`/`data.transform`.
4. Query/transform failures are not only model mistakes; the service boundary can fail before SQL semantics matter because the loader tries to coerce mixed-type spreadsheet columns.

## Verification To Prepare

- Reproduce first `data.peek` payload size and structural output from the real XLSX.
- Add a focused golden/contract test for provider-facing `data.peek` result projection if implementation proceeds.
- Add a boundary test that `data.query SELECT * LIMIT 5` can read this XLSX or returns a structured, repairable failure.
- Add a consistency test that column names shown by `data.peek` are accepted by `data.query`/`data.transform`, or that the result explicitly marks them as inspection-only placeholders.

## Next Step

Propose an impact handshake before code changes. Likely first slice:

- introduce a compact provider-facing tool-result projection for `data.peek`;
- include structural spreadsheet diagnostics and canonical query column names;
- avoid replaying full analysis markdown plus full structured profile to the provider;
- decide whether `data.peek`, `data.query`, and `data.transform` should share one tabular loading authority for column naming and mixed-type behavior.
