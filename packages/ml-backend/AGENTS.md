# AGENTS.md for `packages/ml-backend`

This package contains the Python ML backend for Xenix.

## Tech Stack

- **Runtime:** Python
- **API Framework:** FastAPI
- **Package Manager:** pdm (pyproject.toml is SSoT; export with `pdm export -f requirements --without-hashes` when pip files are needed)
- **Testing:** pytest

## Project Structure

```
packages/ml-backend/
├── ml_backend/          # App code
├── main.py              # Entry point
├── server.py            # Server runner (if present)
├── scripts/             # Utilities
├── tests/               # Pytest tests
├── docs/                # Package docs
└── pyproject.toml       # PDM config
```

## Development

- Install deps: `pdm install`
- Run tests: `pytest`
- Lint/format: follow project-wide tooling if configured in `pyproject.toml`.

## Coding Guidelines

- Keep ML logic in `ml_backend/` and avoid mixing server/bootstrap code with model code.
- Prefer JSON I/O between Node and Python services.
- Add/adjust tests in `tests/` for any behavior changes.
- Keep API routes typed and validated when possible.

## Breaking Changes (v2.0)

### Overview

Major refactoring to split prediction operations and move model saving from training to prediction. **No backward compatibility** - this is a ruthless refactor for cleaner architecture.

### Operation Changes

**Before:**
- 3 operations: `batch-train`, `single-train`, `predict`
- `predict` handled both file and inline modes

**After:**
- 4 operations: `batch-train`, `single-train`, `predict-file`, `predict-inline`
- Separate operations for clarity and type safety

### Field Name Changes

| Old Name | New Name | Type Change |
|----------|----------|-------------|
| `input_file` | `train_data_path` | - |
| `target_column` | `target_columns` | string → array |
| `predict_data` | `to_predict_data` (inline) / `to_predict_data_path` (file) | - |
| `output_path` | _(removed)_ | Auto-generated |

### Model Saving Changes

**Before:**
- Training operations saved models to `{MODEL_STORAGE_PATH}/model_{task_id}_{timestamp}.pkl`
- Predict operations used existing models

**After:**
- Training operations return **metrics only** (NO model saving)
- Predict operations **train + save** fitted models to task directory
- Models saved as `{BASE_PATH}/tasks/{task_id}/model_{timestamp}.pkl`

### Result Structure Changes

**batch-train** (unchanged):
```json
{
  "metrics": {...},
  "best_params": {...}
}
```

**single-train** (removed model_path):
```json
{
  "metrics": {...}
}
```

**predict-file** (new operation):
```json
{
  "fitted_model_path": "model_20260119_120000.pkl",
  "predicted_data_path": "predictions_20260119_120000.xlsx"
}
```

**predict-inline** (new operation):
```json
{
  "fitted_model_path": "model_20260119_120000.pkl",
  "predicted_data": [...]
}
```

### File Organization Changes

**Before:**
- Mixed global directories
- Models in separate `MODEL_STORAGE_PATH`
- Outputs in `OUTPUT_PATH`

**After:**
- All files in task-specific directory: `{ML_BASE_PATH}/tasks/{task_id}/`
- Flat structure (no subdirectories)
- Auto-generated filenames with timestamps

### New Features

1. **Status File**: All operations write `status.txt` with atomic updates
2. **StatusManager**: Atomic file writes using temp file + rename pattern
3. **Path Transformation**: MLBackendService handles OSS vs local storage paths
4. **Dataset Persistence**: Prediction input data saved to datasets table

### Migration Guide

**TypeScript/Backend:**
1. Update all `mlService.batchTrain()` calls: `inputFile` → `trainDataPath`
2. Update all `mlService.singleTrain()` calls: `inputFile` → `trainDataPath`, `parameters` → `params`
3. Update all `mlService.predictFile()` calls: remove `outputPath` parameter
4. Update all `mlService.predictInline()` calls: remove `outputPath` parameter
5. Update result field access: `best_params` → `bestParams`, `predictions` → `predictedData`, `predictions_path` → `predictedDataPath`

**Python:**
1. Use new controller imports: `predict_file`, `predict_inline` (not `predict`)
2. Update input types: `PredictFileInput`, `PredictInlineInput`
3. Update output types: `PredictFileOutput`, `PredictInlineOutput`
4. Target columns now array: `[targetColumn]` instead of `targetColumn`

### Design Rationale

1. **Model Saving in Predictions**: Training is for parameter tuning/evaluation; predictions need the actual fitted model
2. **Split Predict Operations**: Type safety and clearer semantics
3. **Task-Specific Directories**: Better isolation and cleanup
4. **Auto-Generated Filenames**: Eliminates path conflicts and simplifies API
5. **Target Columns Array**: Enables future multi-target regression support
