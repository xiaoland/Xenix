# Data Manager API Documentation

The Data Manager provides centralized dataset management for reusing uploaded data across multiple training and prediction tasks.

## Features

- Upload and register datasets for reuse
- List all available datasets
- Get detailed information about a specific dataset
- Delete datasets when no longer needed
- Reference datasets by ID in training and prediction tasks
- Backward compatible with direct file uploads

## API Endpoints

### POST /api/data

Upload and register a new dataset.

**Request:**
- Content-Type: `multipart/form-data`
- Fields:
  - `file` (File, required): Excel file (.xlsx, .xls)
  - `name` (string, required): User-friendly name for the dataset
  - `description` (string, optional): Description of the dataset

**Response:**
```json
{
  "success": true,
  "dataset": {
    "datasetId": "dataset_1234567890_abc123",
    "name": "Customer Data Q4 2024",
    "description": "Customer data for Q4 analysis",
    "fileName": "customers.xlsx",
    "fileSize": 102400,
    "columns": ["customer_id", "age", "income", "purchases"],
    "rowCount": 1000
  },
  "message": "Dataset uploaded successfully"
}
```

### GET /api/data

List all available datasets.

**Response:**
```json
{
  "success": true,
  "datasets": [
    {
      "id": 1,
      "datasetId": "dataset_1234567890_abc123",
      "name": "Customer Data Q4 2024",
      "description": "Customer data for Q4 analysis",
      "filePath": "/path/to/datasets/customers_1234567890.xlsx",
      "fileName": "customers.xlsx",
      "fileSize": 102400,
      "columns": ["customer_id", "age", "income", "purchases"],
      "rowCount": 1000,
      "createdAt": "2024-12-21T10:00:00.000Z",
      "updatedAt": "2024-12-21T10:00:00.000Z"
    }
  ]
}
```

### GET /api/data/[id]

Get details of a specific dataset.

**Response:**
```json
{
  "success": true,
  "dataset": {
    "id": 1,
    "datasetId": "dataset_1234567890_abc123",
    "name": "Customer Data Q4 2024",
    "description": "Customer data for Q4 analysis",
    "filePath": "/path/to/datasets/customers_1234567890.xlsx",
    "fileName": "customers.xlsx",
    "fileSize": 102400,
    "columns": ["customer_id", "age", "income", "purchases"],
    "rowCount": 1000,
    "createdAt": "2024-12-21T10:00:00.000Z",
    "updatedAt": "2024-12-21T10:00:00.000Z"
  }
}
```

### DELETE /api/data/[id]

Delete a dataset.

**Response:**
```json
{
  "success": true,
  "message": "Dataset deleted successfully"
}
```

## Using Datasets with Training (POST /api/upload)

You can now reference an existing dataset instead of uploading a file each time.

**Option 1: Use existing dataset (recommended)**
```
POST /api/upload
Content-Type: multipart/form-data

datasetId: dataset_1234567890_abc123
model: Ridge
featureColumns: ["age", "income"]
targetColumn: purchases
```

**Option 2: Upload file directly (backward compatible)**
```
POST /api/upload
Content-Type: multipart/form-data

file: [file data]
model: Ridge
featureColumns: ["age", "income"]
targetColumn: purchases
```

## Using Datasets with Prediction (POST /api/predict)

Similar to training, you can reference datasets for both training and prediction data.

**Request using dataset references:**
```
POST /api/predict
Content-Type: multipart/form-data

datasetId: dataset_9876543210_xyz789  # Prediction data
trainingDatasetId: dataset_1234567890_abc123  # Training data
model: Ridge
tuningTaskId: task_1234567890_abc123
featureColumns: ["age", "income"]
targetColumn: purchases
```

**Request using file upload (backward compatible):**
```
POST /api/predict
Content-Type: multipart/form-data

file: [prediction file data]
trainingDataPath: /path/to/training/file.xlsx
model: Ridge
tuningTaskId: task_1234567890_abc123
featureColumns: ["age", "income"]
targetColumn: purchases
```

## Benefits

1. **No File Duplication**: Upload once, use multiple times
2. **Efficient Storage**: Avoid storing the same data repeatedly
3. **Better Organization**: Name and describe datasets for easy identification
4. **Metadata Tracking**: Automatically extract and store column names and row counts
5. **Backward Compatible**: Existing workflows continue to work without changes

## Database Schema

### datasets table

```sql
CREATE TABLE datasets (
  id SERIAL PRIMARY KEY,
  dataset_id VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  file_path TEXT NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  file_size BIGINT,
  columns JSONB,
  row_count INTEGER,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);
```

### tasks table (updated)

```sql
-- Added dataset_id field to track which dataset was used
ALTER TABLE tasks ADD COLUMN dataset_id VARCHAR(255);
```

## Migration

The database migration is automatically generated and applied. To run migrations manually:

```bash
npm run db:generate  # Generate migration
npm run db:migrate   # Apply migration
```

## Example Workflow

1. **Upload a training dataset:**
   ```bash
   curl -X POST http://localhost:3000/api/data \
     -F "file=@training_data.xlsx" \
     -F "name=Training Dataset Q4" \
     -F "description=Customer data for Q4 model training"
   ```

2. **Start training using the dataset:**
   ```bash
   curl -X POST http://localhost:3000/api/upload \
     -F "datasetId=dataset_1234567890_abc123" \
     -F "model=Ridge" \
     -F "featureColumns=[\"age\",\"income\"]" \
     -F "targetColumn=purchases"
   ```

3. **Upload prediction dataset:**
   ```bash
   curl -X POST http://localhost:3000/api/data \
     -F "file=@prediction_data.xlsx" \
     -F "name=Prediction Dataset Q1 2025"
   ```

4. **Run prediction using both datasets:**
   ```bash
   curl -X POST http://localhost:3000/api/predict \
     -F "datasetId=dataset_9876543210_xyz789" \
     -F "trainingDatasetId=dataset_1234567890_abc123" \
     -F "model=Ridge" \
     -F "tuningTaskId=task_1234567890_abc123" \
     -F "featureColumns=[\"age\",\"income\"]" \
     -F "targetColumn=purchases"
   ```
