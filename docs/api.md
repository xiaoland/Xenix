# API Documentation

## Data Manager

### POST /api/data

Upload and register a dataset for reuse across tasks.

**Request**: FormData with `file`, `name`, and optional `description` fields
**Response**: `{ success: true, dataset: {...}, message: string }`

### GET /api/data

List all available datasets.

**Response**: `{ success: true, datasets: [...] }`

### GET /api/data/:id

Get details of a specific dataset.

**Response**: `{ success: true, dataset: {...} }`

### DELETE /api/data/:id

Delete a dataset.

**Response**: `{ success: true, message: string }`

## Training & Prediction

### POST /api/upload

Upload training data and start hyperparameter tuning for a specific model.

**Request**: FormData with either:

- `file` and `model` fields (direct upload)
- `datasetId` and `model` fields (use existing dataset)

**Response**: `{ success: true, taskId: string, inputFile: string, message: string }`

### POST /api/predict

Generate predictions using a selected model.

**Request**: FormData with either:

- `file`, `trainingDataPath`, `model`, and `outputFile` fields (direct upload)
- `datasetId`, `trainingDatasetId`, `model`, and `tuningTaskId` fields (use datasets)

**Response**: `{ success: true, taskId: string, message: string }`

### GET /api/task/:taskId

Check the status and results of a background task.

**Response**:

```json
{
  "success": true,
  "task": {
    "taskId": "string",
    "type": "tuning|prediction",
    "status": "pending|running|completed|failed",
    "error": "string|null"
  }
}
```

### GET /api/results/:taskId

Fetch evaluation metrics for a completed tuning task.

**Response**:

```json
{
  "success": true,
  "results": {
    "model": "string",
    "params": {/* best parameters */},
    "mse_train": "number",
    "mae_train": "number",
    "r2_train": "number",
    "mse_test": "number",
    "mae_test": "number",
    "r2_test": "number"
  }
}
```

### GET /api/logs/:taskId

Fetch real-time logs for a task (OpenTelemetry-compliant).

**Response**:

```json
{
  "success": true,
  "logs": [
    {
      "id": 1,
      "timestamp": 1734675467000000000,
      "severity": "INFO",
      "message": "Starting hyperparameter tuning",
      "attributes": {}
    }
  ]
}
```
