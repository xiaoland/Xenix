# Polars Native Migration Plan

## Intent

Move Xenix data loading and common data operations toward a Polars-native service kernel while keeping product-facing outputs as Xenix-owned typed results.

This is not a `polars -> pandas -> existing code` compatibility migration. pandas can remain where an external library contract requires it, especially scikit-learn model adapters and explicitly pandas-facing analysis lambda support.

## Current Claim

Benchmark evidence supports a native Polars track:

- Real Excel, 100,721 x 5:
  - pandas/openpyxl full read median: 20.367s
  - pandas/calamine full read median: 2.748s
  - polars/calamine full read median: 0.566s
- Generated 3M CSV, 3,000,000 x 8:
  - pandas full read median: 4.304s
  - polars full read median: 0.119s
  - pandas profile-like median: 4.509s
  - polars lazy profile-like median: 0.408s

The memory evidence is directional only. The current harness records same-process RSS deltas, not isolated peak RSS.

## Boundary Decision

Use Polars as an internal service engine object:

- `pl.DataFrame` for materialized table work.
- `pl.LazyFrame` for scan/projection/aggregation work.
- Xenix typed result objects for service output.

Do not expose `pl.DataFrame` directly to:

- UI widgets
- Agent tool result payloads
- storage rows
- provider-facing message blocks
- durable runtime docs as a product contract

## Main Change Points

### 1. Dependency and packaging

Files:

- `pyproject.toml`
- `pdm.lock`
- `xenix.spec`
- `docs/40-deployment/development.md`

Change:

- Add Polars with Excel support, most likely `polars[calamine]`.
- Decide whether `pyarrow` is required. Avoid adding it unless a real boundary needs Arrow IPC/conversion.
- Verify PyInstaller collection for `polars-runtime-32` and `fastexcel`.

Risk:

- Windows native wheels and PyInstaller collection.
- Distribution size increase.
- Python 3.12-3.14 compatibility.

### 2. New tabular service kernel

Likely new file:

- `src/xenix/services/tabular.py`

Possible responsibilities:

- Resolve supported source formats.
- Read CSV/XLSX/XLS through Polars.
- Return schema summaries, preview rows, row/column counts, nullability, and column kinds.
- Provide profile primitives that do not leak engine objects across product boundaries.
- Provide row records for bounded UI/Agent payloads.
- Provide CSV materialization for generated datasets.

Possible types:

- `TabularSource`
- `TabularColumn`
- `TabularPreview`
- `TabularInspection`
- `TabularProfile`
- `TabularFrame`

Important naming constraint:

- Do not create generic DTO names if existing product names are already accurate.
- Existing `DatasetInspection`, `DatasetColumnMetadata`, `DatasetAttachmentMetadata`, `ProfileDatasetResult`, `DataQueryResult`, and `DataTransformResult` should remain public result contracts unless a product reason proves they need replacement.

### 3. Dataset inspection first

Files:

- `src/xenix/services/dataset_inspection.py`
- `src/xenix/services/dataset_service.py`
- `tests/test_services.py`

From:

- `load_dataframe()` returns pandas.
- `inspect_dataset_file()` derives metadata through pandas dtypes and pandas null checks.
- XLSX attachment metadata uses openpyxl read-only path.

To:

- `inspect_dataset_file()` uses Polars-native reader/kernel.
- `inspect_attachment_metadata_file()` can use Polars/calamine for XLS/XLSX if it is faster or simpler, but the current openpyxl metadata path is already fast for XLSX.
- Keep public `DatasetInspection` and `DatasetAttachmentMetadata` shape stable.
- Keep UI and Agent attachments unaware of Polars.

Verification:

- Existing dataset service tests.
- New tests covering dtype/kind mapping for numeric, boolean, text/category, datetime, nullable.
- Regression benchmark for the real Excel file.

### 4. Analysis profile next

Files:

- `src/xenix/services/analysis_profile.py`
- `tests/test_analysis_profile.py`

From:

- Full pandas load.
- pandas dtype APIs.
- pandas groupby/value_counts/corr/quantile.

To:

- Polars scan/read with lazy aggregation where possible.
- Keep `ProfileDatasetResult` and markdown output stable.
- Preserve field grouping semantics intentionally, not accidentally.

Verification:

- Golden-ish profile payload tests for small fixtures.
- Benchmark 3M CSV profile-like path.
- Confirm markdown remains stable where product text matters.

### 5. Data query/transform

Files:

- `src/xenix/services/data_transform.py`
- `tests/test_data_transform.py`

From:

- Load each source into pandas.
- Register pandas DataFrame into DuckDB.
- Fetch pandas DataFrame from DuckDB.
- Write transformed CSV with pandas.

Possible target A:

- Keep DuckDB SQL execution.
- Register Polars/Arrow relation if supported cleanly, or have DuckDB scan Xenix-owned staged/cache files directly.
- Fetch Arrow/Polars or records instead of pandas where feasible.

Possible target B:

- Use Polars SQL/lazy expressions only for a subset.
- Keep DuckDB as the SQL engine because the existing validator and SQL contract are DuckDB-shaped.

Recommended:

- Do not replace DuckDB in the first Polars slice.
- Remove pandas from query/transform materialization path if DuckDB can return Arrow/Polars or if direct scan can preserve the no-arbitrary-file-read contract.

Verification:

- Existing SQL validator tests.
- Query/transform payload tests.
- Security regression: user SQL still cannot call file scan functions or read arbitrary paths.

### 6. Analysis graph

Files:

- `src/xenix/services/analysis_graph.py`
- `tests/test_analysis_graph.py`

From:

- Load full pandas DataFrame.
- Validate fields from pandas columns.
- Convert bounded rows to JSON records for Vega.

To:

- Read through tabular kernel.
- For row-level graphing, collect only `_MAX_RENDER_ROWS`.
- Validate fields from schema without full materialization where possible.
- Keep `GraphDatasetResult` stable.

Verification:

- Existing graph tests.
- Large dataset test proving only bounded rows are materialized for graph rendering.

### 7. Data cleaning

Files:

- `src/xenix/services/data_cleaning.py`
- `tests/test_data_cleaning.py`

Risk:

- Largest deterministic pandas algorithm surface in service layer.
- Many operations rely on pandas-specific behavior.

Plan:

- Do not include in first implementation slice unless the selected operation subset is small and tests are strong.
- Migrate operation families incrementally, probably starting with schema normalization, duplicate handling, missing values, and type conversion.
- Preserve CSV output artifact contract.

### 8. Agent tools and analysis lambda

Files:

- `src/xenix/services/agent/tools.py`
- `src/xenix/services/analysis_lambda_worker.py`
- `docs/20-product-tdd/runtime-boundaries.md`

Decision:

- Agent tool result payloads should stay typed/plain JSON.
- `analysis.lambda` is explicitly pandas-facing in the current contract and is not registered in the Agent-facing tool set.
- Keep lambda pandas support until a separate product decision changes the user-authored analysis runtime.

### 9. ML adapters

Files:

- `src/xenix/services/ml/dataset_loader.py`
- `src/xenix/services/ml/models/*.py`
- `src/xenix/services/ml_service.py`

Decision:

- scikit-learn, XGBoost, LightGBM, mlxtend, and model code are pandas-shaped today.
- Keep pandas at the ML adapter boundary for now.
- If data loading into ML becomes a measured bottleneck, add a controlled `TabularFrame.to_pandas_for_ml()` adapter and benchmark it separately.

## Proposed Implementation Slices

Status as of 2026-06-20:

- Slice 1 dependency promotion and tabular kernel skeleton started.
- Slice 2 dataset inspection migration started and targeted tests pass.
- Slice 3 analysis profile migration started and targeted tests pass.
- Slice 4+ remain planned.

### Slice 0: stronger benchmark and packaging probe

No product behavior change.

- Run each benchmark case in a fresh child process.
- Capture peak RSS from parent.
- Add dependency in a temporary branch and run PyInstaller smoke.

Exit criteria:

- peak RSS and wall-time evidence is stable enough to justify dependency promotion.
- packaged app can import and use Polars Excel/CSV paths.

### Slice 1: dependency plus tabular kernel skeleton

Product behavior should remain equivalent.

- Add Polars dependency.
- Add `tabular.py` with internal APIs.
- Keep existing pandas code paths until tests establish parity.
- Add focused kernel tests.

Exit criteria:

- `pdm run test` and `pdm run check` pass.
- packaged smoke passes.

### Slice 2: dataset inspection on Polars

Replace the highest-impact user-facing read path.

- Move `inspect_dataset_file()` to Polars-native kernel.
- Keep `DatasetInspection` output stable.
- Keep attach-time metadata behavior stable or simplify with Polars only if equivalent and fast.

Exit criteria:

- service tests pass.
- real Excel inspection benchmark improves materially.
- no UI contract changes.

### Slice 3: analysis profile on Polars

Move common profile analysis to lazy/native Polars.

- Preserve `ProfileDatasetResult` payload and markdown.
- Implement field info, numeric stats, frequencies, datetime stats, correlations, and target-group stats.

Exit criteria:

- profile tests pass.
- 3M CSV profile benchmark improves materially.

### Slice 4: graph and query/transform pandas removal

Reduce repeated materialization.

- Graph should collect only bounded rows.
- Query/transform should avoid pandas registration/fetch where safe.

Exit criteria:

- graph/query/transform tests pass.
- security boundary remains intact.

### Slice 5: cleaning and ML boundary decisions

Larger follow-up.

- Migrate cleaning operation families incrementally.
- Keep ML pandas boundary unless measured evidence says otherwise.
- Decide whether analysis lambda remains pandas-only.

## Invariants

- UI does not parse CSV/XLSX files.
- Provider-facing payloads never expose local source paths.
- Dataset inspection metadata remains runtime-derived.
- Existing public result shapes remain stable unless explicitly renegotiated.
- DuckDB SQL validator continues to reject mutation, DDL, extension management, direct file scans, and multi-statement inputs.
- Generated datasets remain app-managed artifacts with registered metadata.
- ML training and apply behavior remains correct even if the internal data kernel changes.

## Verification Matrix

- Unit:
  - dataset inspection
  - profile output
  - graph row injection
  - query/transform security and result payloads
  - cleaning operation parity for any migrated operation
- Integration:
  - Agent `data.peek` over CSV and XLSX
  - `analysis.graph` over large dataset
  - `data.query` and `data.transform`
  - model train/apply path still works with pandas ML boundary
- Performance:
  - real Excel file
  - generated 3M CSV
  - child-process peak RSS
- Packaging:
  - `pdm run check`
  - `pdm run test`
  - `pdm run smoke`
  - `pdm run package` or targeted PyInstaller smoke after dependency promotion

## Open Decisions

- Should `.xls` stay supported through Calamine, or should old Excel stay a fallback path?
- Do we introduce an app-managed Parquet/Arrow cache in the same track, or defer until repeated read cost is measured after Polars migration?
- Should query/transform keep DuckDB as the SQL engine permanently while Polars handles non-SQL data operations?
- Should `analysis.lambda` eventually expose Polars to user code, or remain pandas-only because it is an explicit Python analysis compatibility surface?
