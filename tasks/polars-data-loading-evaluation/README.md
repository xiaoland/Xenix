# Polars Data Loading Evaluation

## Objective & Hypothesis

- Objective: evaluate whether Polars should be introduced to improve Xenix dataset loading and data-tool performance.
- Initial hypothesis: Polars may help, but the right optimization layer must be proven with end-to-end measurements. Xenix currently exposes pandas-shaped semantics across inspection, cleaning, analysis, ML, and Agent analysis boundaries, so a complete pandas replacement is an architecture change rather than a loader edit.
- Updated direction after discussion: prefer evaluating a Polars-native replacement path over a `Polars -> pandas` compatibility path. The compatibility path is useful as a control, but it is not the target design because conversion can erase performance gains and keep the pandas boundary intact.

## Guardrails Touched

- Reality / Explore route.
- Service boundary: `DatasetService` owns source dataset registration, source-file inspection, and export helpers.
- Data service boundary: dataset inspection metadata remains ephemeral and runtime-derived.
- Runtime boundary: UI must not parse `.csv` or `.xlsx`; data loading belongs in services/adapters.
- Packaging boundary: new compiled data dependencies must be verified under PyInstaller on Windows.

## Current Local Facts

- Project dependency baseline declares `pandas>=2.3.0` and `openpyxl>=3.1.0`; it does not declare `polars`, `pyarrow`, `python-calamine`, or `fastexcel`.
- Current environment reports:
  - `pandas == 3.0.1`
  - `polars` not installed
  - `pyarrow` not installed
  - `python_calamine` not installed
  - `fastexcel` not installed
- Benchmark isolation environment under this packet uses:
  - Python `3.14.0`
  - `pandas == 3.0.1`
  - `openpyxl == 3.1.5`
  - `polars == 1.41.2`
  - `pyarrow == 24.0.0`
  - `python-calamine == 0.7.0`
  - `fastexcel == 0.20.2`
- `src/xenix/services/dataset_inspection.py` centralizes `detect_source_format`, `load_dataframe`, full dataset inspection, and lightweight attachment metadata.
- Attach-time metadata for `.csv` is already streaming through Python `csv.reader`.
- Attach-time metadata for `.xlsx` already avoids full pandas load by using `openpyxl.load_workbook(read_only=True, data_only=True)` and worksheet dimensions/header.
- Full `inspect_dataset_file()` still calls `load_dataframe()`, which uses `pd.read_csv()` and `pd.read_excel()`.
- Downstream services are pandas-shaped:
  - `AnalysisProfileService` loads a full pandas DataFrame and uses pandas dtype APIs, `value_counts`, `corr`, `groupby`, etc.
  - `DataCleaningService` loads a full pandas DataFrame and writes CSV output.
  - `AnalysisGraphService` loads pandas rows before Vega rendering.
  - `DataQueryTransformService` loads pandas DataFrames, registers them into DuckDB, then fetches pandas outputs.
  - ML dataset loader returns pandas DataFrames for scikit-learn model adapters.
  - Agent `analysis.lambda` contract explicitly exposes pandas DataFrames.

## Prior Evidence

- Previous profiling packet: `tasks/dataset-create-ui-freeze-profile/README.md`.
- For `F:\CODING\Project\Xenix\ml\recommendations\movie_recommendations.xlsx`, previous evidence recorded:
  - file size: 2,863,935 bytes
  - parsed shape in current code path: 100,721 rows x 5 columns
  - `pandas.read_excel()` via openpyxl dominated full inspection time
  - hot-cache repeated `pandas.read_excel()` was roughly 3.3-3.4s
  - lightweight xlsx metadata path was roughly 0.10-0.12s hot
- That fix moved the UI pain away from send-time blocking, but full inspection/profile/tool execution can still pay the same all-data read cost.

## Online Research Notes

- Polars official docs describe `scan_csv()` as lazy and able to push projections/predicates into the CSV scan, reducing memory overhead for queries that need only some columns or rows. Source: <https://docs.pola.rs/py-polars/html/reference/api/polars.scan_csv.html>
- Polars user guide recommends lazy evaluation as the default style for performance because the optimizer can reduce reads and intermediate materialization. Source: <https://docs.pola.rs/user-guide/migration/pandas/>
- Polars can read Excel through external engines, not a native Excel reader. The default/recommended fast path is the Calamine/fastexcel engine; openpyxl is a slower fallback. Sources:
  - <https://docs.pola.rs/user-guide/io/excel/>
  - <https://docs.pola.rs/api/python/dev/reference/api/polars.read_excel.html>
- Polars optional dependencies are intentionally split. Excel support needs extras such as `polars[calamine]`, `polars[openpyxl]`, or `polars[excel]`; pandas/pyarrow conversion support is also optional. Source: <https://docs.pola.rs/user-guide/installation/>
- `pl.DataFrame.to_pandas()` copies data unless `use_pyarrow_extension_array=True`; that option requires `pyarrow` and may still convert later if pandas operations need NumPy-backed arrays. Source: <https://docs.pola.rs/api/python/dev/reference/dataframe/api/polars.DataFrame.to_pandas.html>
- pandas itself supports `engine="calamine"` for `read_excel()` in pandas 2.2+, using `python-calamine`. For `.xlsx`, pandas still defaults to `openpyxl` when `engine=None`. Sources:
  - <https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.read_excel.html>
  - <https://pandas.pydata.org/docs/dev/whatsnew/v2.2.0.html>
- pandas `read_csv()` supports a `pyarrow` engine; pandas docs say C and pyarrow engines are faster, and multithreading is currently only supported by pyarrow, but some features remain unsupported/experimental in pandas 2.3 docs. Source: <https://pandas.pydata.org/pandas-docs/version/2.3/reference/api/pandas.read_csv.html>
- PyInstaller packaging may need hooks for packages with dynamic imports or binary/data files. This matters for Polars, pyarrow, fastexcel, and python-calamine because they include compiled native components. Source: <https://pyinstaller.org/en/stable/hooks.html>

## Evaluation

### Option A: pandas + Calamine for Excel

- Shape: keep pandas DataFrame as the service boundary; add `python-calamine`; use `pd.read_excel(..., engine="calamine")` where supported, with openpyxl fallback.
- Expected upside: likely accelerates `.xlsx`/`.xls` full reads without crossing the pandas semantic boundary.
- Risk: one new compiled dependency; Excel edge cases must be compared against openpyxl behavior.
- Fit: best first benchmark because current full xlsx read bottleneck is openpyxl-backed `pandas.read_excel()`.

### Option B: Polars as an internal read accelerator, then convert to pandas

- Shape: use Polars for `read_csv`/`read_excel`, then convert to pandas before existing consumers.
- Expected upside: faster parsing may help; conversion may erase part of the gain, especially without `pyarrow`.
- Risk: dependency set grows to `polars` plus Excel/conversion extras; dtype/null/date semantics can shift twice, first into Polars and then into pandas.
- Fit: control only, not recommended as the target. It keeps Xenix's pandas boundary and likely spends complexity without earning the main Polars benefits.

### Option C: Native Polars for inspection/profile/query/transform

- Shape: create a Polars-native data service path and only convert at boundaries that truly require pandas/scikit-learn.
- Expected upside: largest potential wins for CSV scan, column projection, aggregation, profiling, and memory use.
- Risk: high blast radius. Existing pandas dtype inference, Agent lambda contract, cleaning operations, graph rows, DuckDB registration, and ML adapters all assume pandas behavior.
- Fit: not a first slice. Needs contract-level design before implementation.

### Option D: Registered dataset cache in Parquet/Arrow

- Shape: on attach/register or first heavy operation, materialize an app-owned columnar cache and route future inspections/tools through it.
- Expected upside: reduces repeated CSV/XLSX parse cost across a conversation; pairs well with Polars or DuckDB.
- Risk: new artifact lifecycle, invalidation, storage use, and source-file freshness policy.
- Fit: promising later optimization if repeated tool calls over the same dataset are common.

### Option E: DuckDB direct scans for SQL query/transform

- Shape: for `data.query` and `data.transform`, avoid loading pandas first; let DuckDB read registered files or staged/cached files directly, while still blocking arbitrary file scans from user SQL.
- Expected upside: reduces one pandas materialization step for SQL workflows; DuckDB is already a dependency.
- Risk: must preserve the security boundary that SQL cannot read arbitrary paths.
- Fit: separate but relevant because current query/transform path loads pandas just to register a DuckDB table.

## Initial Recommendation

1. Benchmark before adding dependencies to product code.
2. First benchmark pandas Calamine versus current pandas/openpyxl for full Excel reads, because it preserves almost all existing service semantics.
3. Benchmark Polars in two modes:
   - eager read + `to_pandas()` only as a compatibility control
   - native Polars lazy/eager operations for inspection/profile-like summaries
4. Treat native Polars migration as a service-boundary redesign, not a local loader edit.
5. Include packaged-app verification before promoting any dependency change.

## Benchmark Harness

- Script: `tasks/polars-data-loading-evaluation/benchmark_data_loading.py`
- Ignored local state:
  - `.bench-venv/`
  - `fixtures/`
  - `artifacts/`
- Setup command used:

```powershell
pdm run python -m venv tasks/polars-data-loading-evaluation/.bench-venv
tasks\polars-data-loading-evaluation\.bench-venv\Scripts\python.exe -m pip install --upgrade pip pandas==3.0.1 openpyxl python-calamine "polars[calamine]" pyarrow psutil
```

- Benchmark commands used:

```powershell
tasks\polars-data-loading-evaluation\.bench-venv\Scripts\python.exe tasks\polars-data-loading-evaluation\benchmark_data_loading.py --repeats 3 --csv-rows 500000
tasks\polars-data-loading-evaluation\.bench-venv\Scripts\python.exe tasks\polars-data-loading-evaluation\benchmark_data_loading.py --suite csv --repeats 3 --csv-rows 3000000 --output tasks\polars-data-loading-evaluation\artifacts\benchmark-results-3m-csv.json
tasks\polars-data-loading-evaluation\.bench-venv\Scripts\python.exe tasks\polars-data-loading-evaluation\benchmark_data_loading.py --suite excel --repeats 3 --csv-rows 1000 --output tasks\polars-data-loading-evaluation\artifacts\benchmark-results-excel.json
```

## Benchmark Results

### Real Excel File

- Input: `F:\CODING\Project\Xenix\ml\recommendations\movie_recommendations.xlsx`
- File size: 2,863,935 bytes
- Parsed shape: 100,721 rows x 5 columns
- Result artifact: `tasks/polars-data-loading-evaluation/artifacts/benchmark-results-excel.json`

| Case | Median Time | Min-Max | Median RSS Delta |
| --- | ---: | ---: | ---: |
| `pandas.read_excel.openpyxl.full` | 20.367s | 18.923-20.794s | 23,375,872 bytes |
| `pandas.read_excel.calamine.full` | 2.748s | 2.622-3.004s | 44,478,464 bytes |
| `polars.read_excel.calamine.full` | 0.566s | 0.491-0.583s | 5,853,184 bytes |
| `polars.read_excel.calamine.inspect_like` | 0.574s | 0.472-0.579s | 5,025,792 bytes |

Interpretation:

- Current pandas/openpyxl full Excel read is the dominant slow path.
- pandas+Calamine is a low-risk improvement, but Polars+Calamine is materially faster in this test.
- Polars-native full read is about 36x faster than pandas/openpyxl and about 4.9x faster than pandas+Calamine for this file.

### Generated 3M CSV

- Input: `tasks/polars-data-loading-evaluation/fixtures/mixed-3000000.csv`
- File size: 154,927,211 bytes
- Shape: 3,000,000 rows x 8 columns
- Result artifact: `tasks/polars-data-loading-evaluation/artifacts/benchmark-results-3m-csv.json`

| Case | Median Time | Min-Max | Median RSS Delta |
| --- | ---: | ---: | ---: |
| `pandas.read_csv.full` | 4.304s | 4.174-4.488s | 1,142,784 bytes |
| `pandas.read_csv.profile_like` | 4.509s | 4.465-4.708s | -1,232,896 bytes |
| `polars.read_csv.full` | 0.119s | 0.118-0.121s | 211,017,728 bytes |
| `polars.scan_csv.profile_like` | 0.408s | 0.360-0.455s | 75,689,984 bytes |

Interpretation:

- For this generated CSV, Polars eager full read is about 36x faster than pandas full read.
- Polars lazy profile-like aggregation is about 11x faster than pandas profile-like logic.
- RSS delta in this harness is not a reliable peak-memory metric because all cases run in one long-lived process and native allocators retain memory. Use it only as a rough signal that native/Rust allocations exist; do not use it as the final memory claim.

## Current Claim

- The benchmark evidence supports a Polars-native migration track.
- The strongest first target is a service-owned tabular data kernel for inspection/profile/query-like operations, returning Xenix-owned result DTOs rather than pandas DataFrames.
- pandas should remain only where downstream libraries require it, especially scikit-learn model adapters and any explicit compatibility surface.
- The `Polars -> pandas` path should not be the main design because it preserves pandas as the semantic owner and risks losing Polars' lazy/projection advantages.

## Execution Log

### 2026-06-20 Slice 1/2 Start

- Added product dependency `polars[calamine]>=1.41.0`.
- PDM resolved and installed:
  - `polars == 1.41.2`
  - `polars-runtime-32 == 1.41.2`
  - `fastexcel == 0.20.2`
- Added `src/xenix/services/tabular.py` as the first low-level Polars-native service kernel surface.
- Moved full `inspect_dataset_file()` from pandas `load_dataframe()` to the Polars-native tabular path.
- Kept `DatasetInspection`, `DatasetColumnMetadata`, and `DatasetAttachmentMetadata` as public result contracts.
- Kept pandas `load_dataframe()` for still-pandas boundaries such as export, cleaning, graph/profile before their migration, Agent lambda, and ML adapters.
- Updated `xenix.spec` to collect `polars` and `fastexcel` data files and include hidden imports.
- Updated deployment docs to list Polars/Fastexcel as runtime dependencies.
- Added service tests proving XLSX full inspection no longer calls `pandas.read_excel()`.
- Moved `AnalysisProfileService` from pandas to Polars-native loading and aggregation.
- Kept `ProfileDatasetResult` and profile markdown as the public output contract.
- Preserved profile semantics covered by tests:
  - numeric, binary, non-numeric, and datetime grouping
  - datetime detection for date-like string columns
  - duplicate row count
  - target group statistics
- Actual file retest for `F:\CODING\Project\Xenix\ml\recommendations\movie_recommendations.xlsx` through `DatasetService.inspect_source_file()`:
  - 0.424s
  - 0.427s
  - 0.441s
  - 0.409s
  - 0.400s
  - returned 100,721 rows x 5 columns.
- Generated 3M CSV retest through `AnalysisProfileService.profile_dataset()`:
  - 2.935s
  - 2.684s
  - 2.924s
  - returned 3,000,000 rows x 8 columns with full profile output.
- Verification so far:
  - `pdm run pytest tests/test_services.py tests/test_main.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py tests/test_analysis_profile.py tests/test_data_transform.py tests/test_analysis_graph.py -q`: 118 passed.
  - `pdm run check`: passed.
  - `pdm run smoke`: passed.
  - `pdm run package`: passed.
  - `pdm run smoke-package`: passed.

## Remaining Benchmark Plan

- Use an isolated task-local script under this packet, not product code.
- Benchmark datasets:
  - reported Excel file: `F:\CODING\Project\Xenix\ml\recommendations\movie_recommendations.xlsx`
  - generated wide/narrow CSV fixtures at larger row counts
  - generated Excel fixture where possible, bounded by machine time
- Metrics:
  - wall time for cold-ish and hot-cache repeated reads
  - peak Python memory via `tracemalloc`
  - process RSS where feasible
  - output shape and dtype/null/date differences
  - end-to-end time for `inspect_dataset_file`-equivalent metadata
  - end-to-end time for profile-like summaries
- Add stricter memory measurement:
  - run each case in a fresh child process
  - monitor peak RSS from parent
  - record process exit status and result payload separately
- Candidates:
  - current `pd.read_excel()` default openpyxl
  - `pd.read_excel(engine="calamine")`
  - `pl.read_excel(engine="calamine")`
  - `pl.read_excel(...).to_pandas()`
  - current `pd.read_csv()`
  - `pd.read_csv(engine="pyarrow")` if pyarrow is present in the experiment env
  - `pl.read_csv()`
  - `pl.scan_csv().select(...).collect()` for projection-heavy workflows
- Packaging checks:
  - `pdm run package` or targeted PyInstaller smoke after dependency promotion
  - inspect `dist/xenix/_internal/` for collected native libraries
  - run smoke on a clean runtime home

## Open Questions

- Is the user-facing priority still mostly Excel upload/inspection latency, or broader repeated operations after attach?
- Do we want to support `.xls` robustly, or treat legacy Excel as best-effort fallback?
- Should a registered dataset get an app-managed optimized cache, or should Xenix continue reading user-managed source files every time?
- Is preserving pandas dtype/null behavior more important than maximum read speed for early MVT workflows?
- Which product contracts may change if the internal data kernel becomes Polars-native: Agent lambda, data.clean operations, graph row extraction, and ML training inputs all need explicit boundaries.

## Next Step

- Design the Polars-native data kernel boundary before product-code changes.
- The likely shape is a `TabularDatasetReader`/`TabularFrame` service adapter that owns file read, schema projection, inspection summaries, preview rows, and profile primitives without leaking pandas or Polars objects into UI/Agent DTOs.
- Do not change product dependencies or source code until the boundary proposal and blast radius are explicit.
