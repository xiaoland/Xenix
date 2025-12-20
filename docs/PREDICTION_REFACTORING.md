# Prediction System Refactoring

This document explains the changes made to fix issues with the prediction system and make it more robust.

## Problem Statement

The original `predict.py` script had several issues:

1. **Import errors**: Script imported all ML libraries (XGBoost, LightGBM) regardless of which model was needed
   - Error: `ModuleNotFoundError: No module named 'xgboost'`
   - Occurred even when user only wanted to use Ridge regression

2. **JSON file dependency**: Script tried to load parameters from JSON files
   - Files didn't exist (were from old workflow)
   - Violated single source of truth principle

3. **No model selection**: Script would attempt to import libraries for all 12 models
   - Wasteful and error-prone
   - No way to predict with just the selected model

## Solution

### 1. Conditional Imports

Changed from importing all libraries upfront:

```python
# OLD - Always fails if xgboost not installed
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
```

To conditional imports:

```python
# NEW - Only fails if actually needed
try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

# In build_model():
elif model_name == "XGBoost":
    if not XGBOOST_AVAILABLE:
        raise ValueError("XGBoost is not installed. Please install it with: pip install xgboost")
    model = XGBRegressor(...)
```

**Benefits:**
- No error if XGBoost not installed (unless user tries to use it)
- Clear error message with installation instructions
- Only imports what's actually needed

### 2. Database Parameter Loading

Changed from JSON files:

```python
# OLD - JSON files that don't exist
def load_params_from_json(json_filename):
    if os.path.exists(json_filename):
        with open(json_filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}
```

To database queries:

```python
# NEW - Load from PostgreSQL model_results table
def load_params_from_db(task_id):
    """Load parameters from database"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        db_url = os.environ.get('DATABASE_URL')
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(
            "SELECT params FROM model_results WHERE task_id = %s LIMIT 1",
            (task_id,)
        )
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return result['params'] if result and result['params'] else {}
    except Exception as e:
        print(f"⚠️ Failed to load params from database: {e}", file=sys.stderr)
        return {}
```

**Benefits:**
- Single source of truth (database only)
- Parameters from actual tuning run
- Consistent with overall architecture

### 3. Model-Specific Execution

Added `--model` argument to only execute selected model:

```python
# NEW - CLI arguments
parser.add_argument('--model', required=True, help='Model name to use')
parser.add_argument('--task-id', required=True, help='Task ID from tuning to load parameters')
parser.add_argument('--training-data', required=True, help='Training data file path')
```

**Workflow:**

```
1. User tunes Ridge → task_001 with params saved to DB
2. User selects Ridge from results table
3. User uploads prediction data
4. Frontend sends to API:
   - model: "Ridge"
   - tuningTaskId: "task_001"
   - trainingDataPath: "/uploads/training_data.xlsx"
5. predict.py:
   - Loads Ridge params from DB (task_001)
   - Only imports sklearn (no xgboost/lightgbm)
   - Re-trains Ridge on training data
   - Makes predictions on new data
```

## Updated API Endpoint

`POST /api/predict` now requires:

```typescript
{
  file: File,                    // Prediction data
  model: string,                 // Model name (e.g., "Ridge")
  tuningTaskId: string,          // Task ID from tuning step
  trainingDataPath: string       // Path to original training data
}
```

## Updated Frontend

`index.vue` now:

1. Stores `uploadedFilePath` when training data is uploaded
2. Maps selected model to its tuning `taskId`
3. Passes all required data to `/api/predict`

```typescript
const startPrediction = async () => {
  // Find task ID for selected model
  const selectedModelTaskId = tuningTasks.value[selectedBestModel.value];
  
  const formData = new FormData();
  formData.append('file', predictionFileList.value[0].originFileObj);
  formData.append('model', selectedBestModel.value);
  formData.append('tuningTaskId', selectedModelTaskId);
  formData.append('trainingDataPath', uploadedFilePath.value);
  
  const response = await $fetch('/api/predict', {
    method: 'POST',
    body: formData,
  });
};
```

## Benefits Summary

✅ **No import errors**: Only imports libraries needed for selected model
✅ **Database-driven**: Parameters from `model_results` table (not JSON files)
✅ **Selective execution**: Only one model built and trained
✅ **Better error handling**: Clear messages for missing dependencies
✅ **Proper workflow**: Uses actual tuning results for predictions

## Example Scenarios

### Scenario 1: User selects Ridge (no XGBoost installed)

**Before:** ❌ Script fails at import time
```
ModuleNotFoundError: No module named 'xgboost'
```

**After:** ✅ Script runs successfully
```
- Only imports sklearn
- Loads Ridge params from DB
- Trains Ridge model
- Makes predictions
```

### Scenario 2: User selects XGBoost (XGBoost installed)

**Before:** ⚠️ Script loads params from missing JSON file
```
⚠️ JSON file not found, using default params: XGBoost_Params.json
```

**After:** ✅ Script loads params from database
```
- Imports xgboost
- Loads XGBoost params from DB (task_id)
- Trains XGBoost with tuned params
- Makes predictions
```

### Scenario 3: User selects XGBoost (XGBoost NOT installed)

**After:** ⚠️ Clear error message
```
ValueError: XGBoost is not installed. Please install it with: pip install xgboost
```

## Migration Notes

No migration needed for existing users. The system now:
- Ignores any old JSON parameter files
- Always loads from database
- Only uses selected model
- Provides clear error messages

## Testing

To test the prediction system:

1. Upload training data
2. Tune a model (e.g., Ridge)
3. Wait for completion
4. Select model from results table
5. Upload prediction data
6. Start prediction

Expected behavior:
- No import errors
- Parameters loaded from database
- Only selected model executed
- Predictions generated successfully

## Related Commits

- `1b7a401` - Fix predict.py to only use selected model and load params from database
- `57cc022` - Simplify workflow: remove comparison step, add results API endpoint
- `b4f950e` - Refactor Python scripts to emit structured JSON instead of direct database access
