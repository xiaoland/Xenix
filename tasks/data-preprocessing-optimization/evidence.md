# Evidence

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
