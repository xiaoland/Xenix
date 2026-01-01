# Prediction System

Xenix supports two prediction modes: **file-based** (batch Excel processing) and **inline** (JSON array input/output).

## Architecture Overview

```
Frontend (Vue) → API Endpoints → Backend Functions → Python Scripts → Results
```

## File-Based Prediction

Upload Excel files for batch predictions with results saved to Excel.

### File-Based Prediction Flow

1. **Frontend**: User uploads prediction data file via [PredictionStep.vue](app/components/ml/prediction/PredictionStep.vue)
2. **API**: [by-file.post.ts](server/api/predict/by-file.post.ts) validates input and creates task
3. **Backend**: [predictFile()](server/business/ml/index.ts#L422) executes Python script
4. **Python**: [predict_on_file.py](server/business/ml/predict_on_file.py) loads data, trains model, predicts, saves Excel

### File-Based Prediction Input/Output

- **Input**: Training Excel + Prediction Excel
- **Output**: Prediction Excel with `Predicted_Value` column
- **Result**: Task stores output file path

## Inline Prediction

Input data directly in UI table, get JSON predictions instantly.

### Inline Prediction Flow

1. **Frontend**: User inputs data in editable table via [PredictionStep.vue](app/components/ml/prediction/PredictionStep.vue)
2. **API**: [inline.post.ts](server/api/predict/inline.post.ts) validates JSON array and creates task
3. **Backend**: [predictInline()](server/business/ml/index.ts#L464) executes Python script
4. **Python**: [predict_on_json.py](server/business/ml/predict_on_json.py) converts JSON to DataFrame, predicts, returns JSON

### Inline Prediction Input/Output

- **Input**: Training Excel + JSON array `[{"col1": 1.2, "col2": 3.4}]`
- **Output**: JSON array `[10.5, 12.3]`
- **Result**: Task stores predictions in `task.result.predictions`

## Shared Components

### Helper Functions

[predict_helpers.py](server/business/ml/predict_helpers.py) provides:

- `load_and_train_model()` - Loads training data and trains model
- `predict_on_dataframe()` - Makes predictions on DataFrame

### Task Architecture

Both modes use consistent task-based execution:

- Tasks created in database with type "predict"
- Background execution via `setImmediate()`
- Status polling via `useTaskPolling` composable
- Results stored in `task.result`

### Model Support

Supports all regression models:

- Linear, Ridge, Lasso, Bayesian Ridge
- Decision Tree, Random Forest, GBDT
- XGBoost, LightGBM, Polynomial
- AdaBoost, K-Nearest Neighbors

## API Endpoints

| Endpoint               | Method | Purpose               |
| ---------------------- | ------ | --------------------- |
| `/api/predict/by-file` | POST   | File-based prediction |
| `/api/predict/inline`  | POST   | JSON-based prediction |

## Frontend Integration

[PredictionService](app/services/predictionService.ts) provides:

- `start()` - File-based prediction
- `predictInline()` - JSON-based prediction

[PredictionStep.vue](app/components/ml/prediction/PredictionStep.vue) features:

- Mode selector (file vs inline)
- Dynamic table for inline input
- Task status polling and logging
- Results display and download
