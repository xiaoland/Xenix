# Python Scripts Refactoring - stdin/stdout Communication

## Overview

Refactored Python ML scripts to eliminate all database interactions and use stdin/stdout for data exchange, addressing architectural concerns about having two sources of truth for the database schema.

## Problems Addressed

1. ❌ **Database interactions in Python** - Scripts used psycopg2 to query PostgreSQL directly
2. ❌ **Hard-coded SQL** - Difficult to maintain, creates two sources of truth (DrizzleORM + psycopg2)
3. ❌ **Import inefficiency** - All models imported regardless of which one is used
4. ❌ **Default feature columns** - Hardcoded assumptions about data structure

## Solutions Implemented

### 1. No Database Access in Python

**Before:**
```python
import psycopg2
def load_params_from_db(task_id):
    conn = psycopg2.connect(DATABASE_URL)
    cursor.execute("SELECT params FROM model_results WHERE task_id = %s", (task_id,))
    return result
```

**After:**
```python
# No database imports
# Parameters passed via stdin from Node.js
input_data = json.loads(sys.stdin.read())
params = input_data.get('params')  # Already loaded by Node.js from DB
```

### 2. stdin/stdout Communication

**Python Scripts (`tune_model.py`, `predict.py`):**
- Read configuration from stdin as JSON
- Output structured results to stdout as JSON
- No CLI arguments (except script path)

**Node.js Executor (`pythonExecutor.ts`):**
```typescript
// Old approach
spawn(pythonCmd, [script, '--input', file, '--model', model, ...])

// New approach
const pythonProcess = spawn(pythonCmd, [script])
pythonProcess.stdin.write(JSON.stringify(stdinData))
pythonProcess.stdin.end()
```

### 3. Lazy Imports

**Before:**
```python
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ...
from sklearn.ensemble import RandomForest, GradientBoosting, AdaBoost
from xgboost import XGBRegressor  # ❌ Error if not installed
from lightgbm import LGBMRegressor  # ❌ Error if not installed
```

**After:**
```python
def import_model_class(model_name):
    """Import only the needed model"""
    if model_name == "Ridge":
        from sklearn.linear_model import Ridge
        return Ridge
    elif model_name == "XGBoost":
        try:
            from xgboost import XGBRegressor
            return XGBRegressor
        except ImportError:
            raise ImportError("XGBoost not installed")
```

### 4. No Default Feature Columns

**Before (`config.py`):**
```python
FEATURE_COLUMNS = ['Historical Loan Amount', 'Number of Loans', ...]  # ❌ Hardcoded
TARGET_COLUMN = 'Customer Value'  # ❌ Data-specific assumption
```

**After (`config.py`):**
```python
AVAILABLE_MODELS = [...]  # Just constants, no data assumptions
# Feature columns must be provided via stdin
```

## Data Flow

### Training (Hyperparameter Tuning)

```
1. Frontend uploads data.xlsx
2. Frontend provides: featureColumns=["col1","col2"], targetColumn="target"
3. API endpoint (/api/upload):
   - Validates inputs
   - Creates task in database
   - Constructs stdin JSON:
     {
       "inputFile": "/uploads/data.xlsx",
       "model": "Ridge",
       "featureColumns": ["col1", "col2"],
       "targetColumn": "target"
     }
4. Python script (tune_model.py):
   - Reads stdin
   - Imports only Ridge (not XGBoost/LightGBM)
   - Trains model with GridSearchCV
   - Emits results to stdout as JSON:
     {
       "type": "result",
       "data": {
         "model": "Ridge",
         "params": {"model__alpha": 1.0},
         "metrics": {"mse_test": 0.02, "r2_test": 0.95, ...}
       }
     }
5. Node.js executor:
   - Parses stdout JSON
   - Stores in database via DrizzleORM
```

### Prediction

```
1. User selects trained model (e.g., Ridge from task_123)
2. Frontend uploads prediction.xlsx
3. API endpoint (/api/predict):
   - Loads params from database: SELECT params FROM model_results WHERE task_id='task_123'
   - Constructs stdin JSON:
     {
       "trainingDataPath": "/uploads/train.xlsx",
       "predictionDataPath": "/uploads/predict.xlsx",
       "outputPath": "/uploads/predict_result.xlsx",
       "model": "Ridge",
       "params": {"model__alpha": 1.0},  // From database
       "featureColumns": ["col1", "col2"],
       "targetColumn": "target"
     }
4. Python script (predict.py):
   - Reads stdin
   - Imports only Ridge
   - Trains model with provided params
   - Makes predictions
   - Saves to output file
   - Emits completion to stdout
5. Node.js executor:
   - Updates task status to completed
```

## Benefits

### Single Source of Truth
- ✅ Database schema: DrizzleORM only (Node.js)
- ✅ No SQL queries in Python
- ✅ No psycopg2 or SQLAlchemy needed

### Flexibility
- ✅ Works with any dataset structure
- ✅ No hardcoded column names
- ✅ Each request can specify different features

### Performance
- ✅ Lazy imports: Only loads required libraries
- ✅ No "ModuleNotFoundError" for unused models
- ✅ Smaller memory footprint

### Maintainability
- ✅ Clear separation: ML in Python, persistence in Node.js
- ✅ Python scripts are stateless
- ✅ Easier to test (no DB mocking needed in Python)
- ✅ Single migration point for schema changes (DrizzleORM)

## API Changes

### POST /api/upload

**New required fields:**
- `featureColumns` (JSON string): Array of feature column names
- `targetColumn` (string): Name of target column

**Example:**
```javascript
formData.append('file', fileBlob)
formData.append('model', 'Ridge')
formData.append('featureColumns', JSON.stringify(['col1', 'col2', 'col3']))
formData.append('targetColumn', 'target')
```

### POST /api/predict

**New required fields:**
- `featureColumns` (JSON string): Same as training
- `targetColumn` (string): Same as training

**Example:**
```javascript
formData.append('file', predictionFileBlob)
formData.append('model', 'Ridge')
formData.append('tuningTaskId', 'task_123')
formData.append('trainingDataPath', '/uploads/train_abc.xlsx')
formData.append('featureColumns', JSON.stringify(['col1', 'col2', 'col3']))
formData.append('targetColumn', 'target')
```

## Testing

### Validation Performed

✅ Python syntax checked (`py_compile` successful)
✅ No import errors
✅ stdin/stdout communication implemented
✅ Lazy imports working
✅ No database dependencies in Python

### Example Test

```bash
# Test tune_model.py with stdin
echo '{"inputFile":"data.xlsx","model":"Ridge","featureColumns":["col1"],"targetColumn":"target"}' | \
  python3 tune_model.py

# Output should be structured JSON on stdout:
{"type":"log","data":{"severity_text":"INFO","body":"Starting tuning"}}
{"type":"result","data":{"model":"Ridge","params":{...},"metrics":{...}}}
```

## Migration Notes

### Frontend Changes Required

1. **Collect column information:**
   - Either auto-detect from uploaded Excel file (read first row)
   - Or provide UI for user to select features and target

2. **Update API calls:**
   ```javascript
   // Add to upload request
   featureColumns: JSON.stringify(['col1', 'col2'])
   targetColumn: 'target'
   
   // Add to predict request (same columns as training)
   featureColumns: JSON.stringify(['col1', 'col2'])
   targetColumn: 'target'
   ```

### Backward Compatibility

❌ **Breaking change** - Old API calls without `featureColumns` and `targetColumn` will be rejected with 400 error.

## Files Modified

1. `app/models/regression/tune_model.py` - Complete rewrite for stdin
2. `app/models/regression/predict.py` - Complete rewrite for stdin
3. `app/models/regression/config.py` - Removed defaults
4. `server/utils/pythonExecutor.ts` - Changed to stdin-based
5. `server/api/upload.post.ts` - Accept columns, pass via stdin
6. `server/api/predict.post.ts` - Load params from DB, pass via stdin

## Deprecated Files

- `app/models/regression/tune_model_old.py` - Old version with CLI args
- `app/models/regression/predict_old.py` - Old version with DB access
- Can be deleted after verification

## Summary

This refactoring addresses all architectural concerns:
- ✅ No database access in Python (single source of truth)
- ✅ Configuration via stdin (flexible, testable)
- ✅ Lazy imports (performance, no module errors)
- ✅ No hardcoded data assumptions (works with any dataset)

The system now follows a clean architecture with clear boundaries:
- **Frontend**: User interface + data specification
- **Node.js**: API, database operations, task orchestration
- **Python**: Pure ML computation (stateless, DB-agnostic)
