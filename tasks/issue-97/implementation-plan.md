# Issue 97 Implementation Plan

## Objective & Hypothesis

- Objective: extend `data.clean` with explicit, auditable preprocessing operations learned from the provided scripts while preserving no-op-by-default behavior.
- Hypothesis: the right product shape is not an automatic cleaning preset. It is a richer operation catalog where the LLM can progressively discover available operation schemas through `data.clean.metadata`, then call `data.clean` with explicit operations.

## Confirmed Direction

- `data.clean.metadata` may remain mostly schema-oriented. It does not need to teach the full decision tree in this slice.
- New capabilities should be added as explicit `data.clean` operations, not as a bundled default cleaning flow.
- `data.clean` must continue to perform no work when `operations` is absent or empty.
- Each new operation must record enough report data for auditability.
- All operations create a derived dataset only through the existing `data.clean` execution path.

## Execution Status

- 2026-05-30: implementation started after user confirmation.
- 2026-05-30: implemented metadata and execution support for:
  - `schema.normalize_column_names`
  - `missing.drop_high_missing_columns`
  - `outlier.clip_iqr`
  - `encoding.one_hot`
  - `scaling.minmax`
  - `scaling.standard`
- 2026-05-30: updated durable Agent/data-cleaning boundary docs.

## Proposed Operation Additions

### 1. `schema.normalize_column_names`

Purpose: normalize column names algorithmically without requiring explicit old-to-new mappings.

Default strategy:

- preserve Unicode letters and numbers, including Chinese business field names
- trim leading/trailing whitespace
- normalize common full-width punctuation and separators into `_`
- replace whitespace and punctuation runs with `_`
- collapse repeated `_`
- trim surrounding `_`
- lowercase ASCII letters only
- fill empty normalized names as `column_<1-based-index>`
- resolve duplicate normalized names deterministically with suffixes such as `_2`, `_3`
- report old/new mapping, changed count, generated empty-name replacements, and duplicate collisions

Non-goals:

- no Chinese-to-pinyin transliteration
- no automatic English translation
- no explicit rename mapping; explicit projection aliases belong to `data.transform` / DuckDB SQL

Suggested params:

```json
{
  "style": "snake_case",
  "ascii_lower": true
}
```

### 2. `missing.drop_high_missing_columns`

Purpose: remove columns whose missing ratio exceeds an explicit threshold.

Suggested params:

```json
{
  "threshold": 0.5,
  "columns": ["optional", "subset"]
}
```

Rules:

- `threshold` must be `0 <= threshold <= 1`.
- If `columns` is omitted, evaluate all columns.
- Drop columns with missing ratio strictly greater than `threshold`.
- Report evaluated columns, dropped columns, and per-column missing ratios.

### 3. `outlier.clip_iqr`

Purpose: cap numeric outliers using the IQR method.

Suggested params:

```json
{
  "columns": ["amount"],
  "multiplier": 1.5
}
```

Rules:

- columns must be numeric.
- `multiplier` must be positive.
- For each column, compute Q1, Q3, IQR, lower bound, and upper bound.
- Clip values outside bounds to the nearest bound.
- Report bounds and changed cell counts per column.

### 4. `encoding.one_hot`

Purpose: expand categorical columns into deterministic one-hot indicator columns.

Suggested params:

```json
{
  "columns": ["segment"],
  "drop_first": false,
  "max_categories": 50
}
```

Rules:

- columns must exist.
- generated column names should reuse the same normalization helper used by `schema.normalize_column_names`.
- reject or report columns exceeding `max_categories`.
- preserve non-encoded columns.
- report generated columns and skipped columns.

### 5. `scaling.minmax`

Purpose: scale numeric columns into a configurable numeric range.

Suggested params:

```json
{
  "columns": ["amount"],
  "feature_range": [0, 1]
}
```

Rules:

- columns must be numeric.
- constant columns should remain stable and report a warning.
- report original min/max and target range per column.

### 6. `scaling.standard`

Purpose: standardize numeric columns using mean and standard deviation.

Suggested params:

```json
{
  "columns": ["amount"]
}
```

Rules:

- columns must be numeric.
- constant columns should remain stable and report a warning.
- report original mean/std per column.

## Implementation Slices

### Slice 1: Contract And Metadata

Files:

- `src/xenix/services/data_cleaning.py`
- `tests/test_data_cleaning.py`
- `docs/20-product-tdd/runtime-boundaries.md`
- `docs/30-unit-tdd/agent-harness.md`

Work:

- Add metadata groups: `schema`, `outliers`, `encoding`, `scaling`.
- Add operation schemas and examples for all planned operations.
- Keep `data.clean` provider schema compact: operation remains `{operation, params}`.
- Add tests that verify metadata lists the new groups and operations.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_data_cleaning.py -q
```

### Slice 2: Schema And Missing-Column Operations

Files:

- `src/xenix/services/data_cleaning.py`
- `tests/test_data_cleaning.py`

Work:

- Implement shared column-name normalization helper.
- Implement `schema.normalize_column_names`.
- Implement `missing.drop_high_missing_columns`.
- Add focused service tests for mapping, duplicate resolution, empty names, missing-ratio thresholding, and report payloads.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_data_cleaning.py -q
```

### Slice 3: Outlier And Encoding Operations

Files:

- `src/xenix/services/data_cleaning.py`
- `tests/test_data_cleaning.py`

Work:

- Implement `outlier.clip_iqr`.
- Implement `encoding.one_hot`.
- Reuse normalization helper for generated indicator names.
- Add tests for numeric validation, bounds reporting, clipped cell counts, deterministic generated names, and category-limit behavior.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_data_cleaning.py -q
```

### Slice 4: Scaling Operations

Files:

- `src/xenix/services/data_cleaning.py`
- `tests/test_data_cleaning.py`

Work:

- Implement `scaling.minmax`.
- Implement `scaling.standard`.
- Add tests for numeric validation, constant-column warnings, output values, and report payloads.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_data_cleaning.py -q
```

### Slice 5: Boundary Verification

Files:

- `tests/test_agent_harness_streaming.py` only if contextual exposure or provider-facing schema changes unexpectedly.
- `tests/test_agent_harness_first_slice.py` only if tool registry assumptions change.

Work:

- Confirm no-op behavior still holds.
- Confirm legacy policy fields remain rejected.
- Confirm `data.clean.metadata` still never executes cleaning.
- Confirm provider-facing `data.clean` schema remains compact.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_data_cleaning.py tests\test_agent_harness_streaming.py tests\test_agent_harness_first_slice.py -q
.\.venv\Scripts\python.exe -m compileall src tests scripts
```

## Blast Radius Forecast

- Primary: `DataCleaningService` operation metadata and execution dispatch.
- Secondary: tool metadata returned by `data.clean.metadata`.
- Secondary: data-cleaning tests and durable docs for operation catalog.
- Low expected UI blast radius because `data.clean` remains operation-driven and schema-compact.
- No storage migration expected because cleaned outputs remain derived dataset artifacts through existing dataset/artifact records.

## Invariants

- Empty or absent `operations` remains no-op.
- Source dataset files are never mutated.
- Each non-empty operation call writes a derived dataset artifact through the existing cleaning path.
- `data.clean.metadata` returns schemas only and never executes cleaning.
- Unsupported operation names still fail with `ValidationError`.
- Existing operations retain behavior unless tests force a deliberate correction.

## Open Design Details Before Implementation

- `schema.normalize_column_names` keeps `_` as the only separator in this slice.
- `missing.drop_high_missing_columns` uses strict `>` threshold comparison.
- One-hot generated names are normalized from `<column>_<category>`; readable original values remain available through operation report context.
- Scaling uses direct Pandas arithmetic instead of scikit-learn scalers to keep service behavior transparent.

## Verification Results

- `.\.venv\Scripts\python.exe -m pytest tests\test_data_cleaning.py -q`
  - Result: 13 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_data_cleaning.py tests\test_agent_harness_streaming.py tests\test_agent_harness_first_slice.py -q`
  - Result: 46 passed.
- `.\.venv\Scripts\python.exe -m compileall src tests scripts`
  - Result: passed.
