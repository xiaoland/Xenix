# Model Comparison Refactoring

## Overview

This document describes the refactoring of the model comparison system to eliminate JSON file dependencies and properly integrate with the database-driven architecture.

## Problems Solved

### 1. File Path Error
**Issue**: `compare_models.py` hardcoded the data filename as "Customer Value Data Table.xlsx"

**Solution**: Script now accepts `--input` argument with the actual uploaded file path from the upload endpoint.

### 2. JSON Parameter Files Not Found
**Issue**: Script tried to load tuning parameters from JSON files (e.g., `Ridge_Params.json`) that don't exist in production.

**Solution**: Parameters are now loaded directly from the `model_results` database table using task IDs from the tuning step.

### 3. Design Issues
**Issue**: 
- Comparison tried to compare all 12 models regardless of user selection
- No way to specify which models to compare
- Tuning results stored locally in JSON instead of database

**Solution**:
- `/api/compare` endpoint now accepts list of models to compare
- Only models that completed tuning are compared
- All parameters retrieved from database, not files

## Architecture Changes

### Before
```
tune_model.py → Save params to JSON file
                       ↓
compare_models.py → Load params from JSON files → Compare all 12 models
```

**Problems:**
- JSON files not committed to git
- Hard to track which params belong to which data/session
- All models compared even if not tuned
- File path hardcoded

### After
```
tune_model.py → Emit result to stdout → Node.js → Save to DB (model_results)
                                                         ↓
                                                    task_id stored
                                                         ↓
compare_models.py ← Load params from DB by task_id ← Node.js ← UI (selected models + file path)
```

**Benefits:**
- Single source of truth: Database only
- Parameters tied to specific tuning tasks
- Only selected models compared
- Proper file path handling
- No file system dependencies

## API Changes

### `/api/compare` Endpoint

**Before:**
```typescript
POST /api/compare
// No request body
```

**After:**
```typescript
POST /api/compare
{
  "inputFile": "/uploads/data_abc123.xlsx",
  "models": ["Ridge", "Random_Forest", "XGBoost"],
  "taskIds": {
    "Ridge": "task_001",
    "Random_Forest": "task_002",
    "XGBoost": "task_003"
  }
}
```

### Python Script Arguments

**Before:**
```bash
python compare_models.py --output-db task_456
```

**After:**
```bash
python compare_models.py \
  --input /uploads/data_abc123.xlsx \
  --models Ridge,Random_Forest,XGBoost \
  --task-ids Ridge=task_001,Random_Forest=task_002,XGBoost=task_003
```

## Database Integration

### New Function: `load_params_from_db(task_id)`

Queries the `model_results` table to retrieve tuned parameters:

```python
def load_params_from_db(task_id, logger=None):
    """Load params from database using task ID"""
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute(
        "SELECT params FROM model_results WHERE task_id = %s ORDER BY created_at DESC LIMIT 1",
        (task_id,)
    )
    result = cursor.fetchone()
    
    return result['params'] if result else {}
```

### Fallback Behavior

If no parameters found in database (task ID not provided or query fails):
- Falls back to default parameters
- Logs a warning
- Continues with comparison using defaults

## Frontend Changes

### State Management

Added `uploadedFilePath` to track the uploaded training data:

```typescript
const uploadedFilePath = ref<string>('');
```

Populated on successful upload:

```typescript
if (response.success && response.inputFile) {
  uploadedFilePath.value = response.inputFile;
}
```

### Comparison Logic

Now passes required data to backend:

```typescript
const startComparison = async () => {
  const tunedModels = Object.keys(tuningStatus.value)
    .filter(model => tuningStatus.value[model] === 'completed');
  
  const taskIds: Record<string, string> = {};
  tunedModels.forEach(model => {
    if (tuningTasks.value[model]) {
      taskIds[model] = tuningTasks.value[model];
    }
  });
  
  await $fetch('/api/compare', {
    method: 'POST',
    body: {
      inputFile: uploadedFilePath.value,
      models: tunedModels,
      taskIds,
    },
  });
};
```

## Migration Notes

### Deprecated Files

The following files are now deprecated and can be removed in future cleanup:

- `app/models/regression/Model_Compare_By_JSON.py` - Old JSON-based comparison script
- `app/models/regression/db_utils.py` - Direct database access (replaced by structured JSON output)
- `app/models/regression/log_handler.py` - Direct database logging (replaced by structured JSON output)

### No Breaking Changes

All changes are backward compatible with the database schema. Existing `model_results` rows can be queried using the new approach.

## Testing

To test the changes:

1. Upload training data (file path stored)
2. Select 2-3 models and run tuning (task IDs stored)
3. Click "Compare All Models"
4. Verify:
   - No "JSON file not found" warnings in logs
   - No "file not found" errors
   - Only selected models are compared
   - Parameters loaded from database
   - Comparison completes successfully

## Example Logs

**Expected output:**
```
[19:39:24] [INFO] Starting model comparison for models: Ridge, Random_Forest
[19:39:24] [INFO] Loading model parameters from database
[19:39:24] [INFO] Loading params for Ridge from task task_001
[19:39:24] [INFO] Loading params for Random_Forest from task task_002
[19:39:24] [INFO] Loading training data from /uploads/data_abc123.xlsx
[19:39:24] [INFO] Data loaded: 1000 rows
[19:39:25] [INFO] Building 2 models for comparison
[19:39:25] [INFO] Training model: Ridge
[19:39:26] [INFO] Ridge training completed
[19:39:26] [INFO] Ridge - R²_test: 0.8234
[19:39:26] [INFO] Training model: RandomForest
[19:39:28] [INFO] RandomForest training completed
[19:39:28] [INFO] RandomForest - R²_test: 0.8567
[19:39:28] [INFO] Best Model: RandomForest
```

## Conclusion

This refactoring eliminates file system dependencies and properly integrates the comparison system with the database-driven architecture. All model parameters are now stored and retrieved from the database, making the system more maintainable and scalable.
