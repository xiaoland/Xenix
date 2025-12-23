# Xenix

Machine Learning Model Training and Prediction Platform

![Xenix UI](https://github.com/user-attachments/assets/9a227c7b-8394-4558-8afa-5ced3dcd7afa)

Xenix provides an interface for teachers and mid-small enterprises to analyze their data with ease. The platform supports automated hyperparameter tuning with evaluation metrics display and batch prediction for regression tasks.

## Features

- **2-Step Workflow**: Upload & Train → View Results & Predict
- **Data Manager**: Upload and reuse datasets across multiple tasks without duplication
- **Automated Hyperparameter Tuning**: GridSearchCV-based optimization for 12 regression models
- **Evaluation Metrics Display**: Real-time display of MSE, MAE, and R² scores from tuning
- **Background Task Processing**: Long-running tasks execute asynchronously with status polling
- **Real-Time Logs**: OpenTelemetry-compliant logging with structured JSON output
- **Database Persistence**: All tasks, parameters, metrics, and results stored in SQLite
- **Modern UI**: Built with Nuxt.js and Ant Design Vue with modular components

## Supported Models

- Linear Regression (`regression.linear_regression_hyperparameter_tuning`)
- Ridge Regression (`regression.ridge`)
- Lasso Regression (`regression.lasso`)
- Bayesian Ridge Regression (`regression.bayesian_ridge_regression`)
- K-Nearest Neighbors (`regression.k_nearest_neighbors`)
- Decision Tree (`regression.regression_decision_tree`)
- Random Forest (`regression.random_forest`)
- Gradient Boosting (`regression.gbdt`)
- AdaBoost (`regression.adaboost`)
- XGBoost (`regression.xgboost`)
- LightGBM (`regression.lightgbm`)
- Polynomial Regression (`regression.polynomial_regression`)

**Note**: Model values use dotted notation with type prefix for API requests.

## Tech Stack

### Frontend

- **Framework**: Nuxt.js 4.2.2
- **UI Library**: Ant Design Vue
- **Styling**: UnoCSS + SCSS

### Backend

- **Runtime**: Node.js with Nitro
- **Database**: SQLite
- **ORM**: DrizzleORM

### Data Processing

- **Language**: Python 3.12
- **Package Manager**: PDM
- **Libraries**: scikit-learn, pandas, statsmodels, XGBoost, LightGBM

## Prerequisites

- Node.js 18+ and pnpm
- Python 3.12

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/xiaoland/Xenix.git
cd Xenix
```

### 2. Install dependencies

```bash
# Install Node.js dependencies
pnpm install
```

**Note:** Python dependencies (PDM and packages) are automatically installed on first use. The ML pipeline will:

1. Check if PDM is installed, and install it if missing
2. Check if Python dependencies are installed, and run `pdm install` if needed

You can also manually install Python dependencies:

```bash
# Install PDM (Python package manager)
pip install --user pdm

# Install Python dependencies
pdm install
```

### 3. Configure Database

```bash
# Copy environment file
cp .env.example .env

# The default configuration uses SQLite with DATABASE_URL=./xenix.db
```

Generate and apply migrations:

```bash
# Generate SQLite migrations
pnpm db:generate

# Apply migrations (SQLite will auto-create the database)
pnpm db:migrate
```

### 4. Start the development server

```bash
pnpm dev
```

The application will be available at `http://localhost:3005` (or `http://localhost:3000` if 3005 is in use).

## Usage

### Step 1: Upload & Train

1. **Upload Training Data**
   - Upload an Excel file (.xlsx or .xls) containing your training data
   - The file should have feature columns and a target variable column
   - Example: `Customer Value Data Table.xlsx`

2. **Select & Tune Models**
   - Select one or more models to tune from the 12 available options
   - Click "Start Hyperparameter Tuning" to begin Grid SearchCV optimization
   - Watch real-time logs as models train
   - Wait for tuning to complete (status updates automatically)

3. **View Results & Select Best Model**
   - See evaluation metrics table with MSE, MAE, and R² scores
   - Table automatically sorts by R² (best first)
   - Click radio button to select the model you want to use
   - Click "Continue to Prediction"

### Step 2: Predict

1. **Upload Prediction Data**
   - Upload a new Excel file with the same features (without the target variable)
   - Must have same column names as training data

2. **Generate Predictions**
   - Click "Start Prediction" to run the selected model
   - Wait for prediction to complete
   - Download the results with predictions added as a new column

## Project Structure

```
Xenix/
├── app/
│   ├── components/               # Vue components
│   │   ├── UploadStep.vue       # Upload interface
│   │   ├── TrainingStep.vue     # Model selection & tuning
│   │   ├── PredictionStep.vue   # Prediction interface
│   │   ├── ModelSelector.vue    # Model selection grid
│   │   ├── TuningResults.vue    # Results table with selection
│   │   ├── TaskLogViewer.vue    # Tabbed log interface
│   │   └── LogPanel.vue         # Terminal-style log display
│   ├── models/
│   │   └── regression/          # Python ML scripts
│   │       ├── tune_model.py    # Hyperparameter tuning (outputs JSON)
│   │       ├── predict.py       # Batch prediction
│   │       ├── structured_output.py # JSON emission utilities
│   │       └── config.py        # Configuration
│   ├── pages/
│   │   └── index.vue            # Main application page (2-step workflow)
│   └── app.vue                  # Root component
├── server/
│   ├── api/                     # API endpoints
│   │   ├── upload.post.ts       # File upload & tuning
│   │   ├── predict.post.ts      # Batch prediction
│   │   ├── task/[taskId].get.ts # Task status polling
│   │   ├── results/[taskId].get.ts # Fetch model metrics
│   │   └── logs/[taskId].get.ts # Fetch task logs
│   ├── business/                # Core business logic
│   │   └── mlPipeline.ts        # ML operations (tune, predict) with auto PDM setup
│   ├── database/
│   │   ├── schema.ts            # Database schema (tasks, model_results, logs)
│   │   ├── index.ts             # Database client
│   │   └── migrations/          # SQL migrations
│   └── utils/
│       ├── taskUtils.ts         # Task utilities
│       └── pythonExecutor.ts    # Python process manager & JSON parser
├── docker-compose.yml           # PostgreSQL container
├── drizzle.config.ts            # DrizzleORM configuration
├── pyproject.toml               # Python dependencies
└── package.json                 # Node.js dependencies
```

## API Endpoints

### Data Manager

#### POST /api/data

Upload and register a dataset for reuse across tasks.

**Request**: FormData with `file`, `name`, and optional `description` fields
**Response**: `{ success: true, dataset: {...}, message: string }`

#### GET /api/data

List all available datasets.

**Response**: `{ success: true, datasets: [...] }`

#### GET /api/data/:id

Get details of a specific dataset.

**Response**: `{ success: true, dataset: {...} }`

#### DELETE /api/data/:id

Delete a dataset.

**Response**: `{ success: true, message: string }`

See [Data Manager Documentation](docs/data-manager.md) for detailed usage.

### Training & Prediction

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

## Configuration

### Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Available variables:

- `DATABASE_URL` - SQLite database file path (required)
  - Example: `./xenix.db` or `sqlite://./xenix.db`
- `PYTHON_EXECUTABLE` - Python command to use (default: `python3`)

## Development

### Build for production

```bash
pnpm build
```

### Run production build

```bash
node .output/server/index.mjs
```

### Database management

```bash
# Open Drizzle Studio
pnpm db:studio

# Generate new migration
pnpm db:generate
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT

## Author

Lanzhijiang (<lanzhijiang@foxmail.com>)
