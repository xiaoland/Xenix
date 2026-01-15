# ML Backend Architecture

> **Package**: `@xenix/ml-backend`
> **Purpose**: Standalone ML operations (training, prediction) executable locally or via Aliyun FC

## Overview

Core ML functionality package used by the main backend. Provides training and prediction operations with pluggable I/O adapters (stdio for local, FC for cloud).

```
Input (Node.js backend)
  ↓
ml-backend interface:
  - batchTrain() - GridSearchCV
  - singleTrain() - Manual params
  - predict() - Batch prediction
  ↓
Adapter selector:
  ├─ stdio - stdin/stdout communication
  └─ aliyun-fc - environment detection
  ↓
Python executor
  ↓
Python scripts (scikit-learn, XGBoost, etc.)
  ↓
Output (CSV, JSON, database)
```

## Structure

```
src/
├── index.ts              # Core function exports
├── core/                 # ML operation implementations
│   ├── batch-train.ts    # GridSearchCV auto-tuning
│   ├── single-train.ts   # Manual parameter training
│   └── predict.ts        # Batch prediction
├── adapters/             # I/O strategy (stdin/FC)
│   ├── stdio/index.ts    # stdin/stdout protocol
│   └── aliyun-fc/index.ts # FC environment setup
├── types/
│   ├── index.ts
│   ├── input.ts          # Input types
│   ├── output.ts         # Output types
│   └── ...
├── utils/
│   ├── python-executor.ts # Spawn Python subprocess
│   ├── logger.ts         # Database + console logging
│   └── ...
├── python/               # Python scripts (side-by-side)
│   ├── auto_tune_model.py
│   ├── manual_tune_model.py
│   ├── predict.py
│   └── requirements.txt
└── __tests__/
```

## Core Functions

**Batch Training (Auto-Tuning)**

- Executes GridSearchCV for hyperparameter optimization
- Receives: input file path, model name, feature columns, target, parameter grid
- Returns: best parameters, metrics (r2, rmse, mae, cv_scores), model path

Type definition:

```typescript
export interface BatchTrainOutput {
  task_id: string;
  best_params: Record<string, any>;
  metrics: { r2_score?: number; rmse?: number; mae?: number; cv_scores?: number[] };
  model_path: string;
  timestamp: string;
}
```

**Single Training (Manual)**

- Trains with specific parameters (no tuning)
- Receives: same as batch but with fixed parameters instead of grid
- Returns: trained model, metrics

**Prediction**

- Loads trained model and applies to new data
- Receives: training data path, prediction data, model name, parameters
- Returns: predictions file path, record count

## Python Executor

Spawns Python subprocess with JSON communication via stdin/stdout:

- Input: JSON object via stdin (task configuration)
- Output: Structured JSON lines (logs, status, result)
- Error handling: Capture stderr and exit code, propagate to backend
- Timeout: Configurable (default 300 seconds)
- Event callbacks: onLog for capturing real-time logs during execution

```

## Adapters

Two adapter implementations for different execution environments:

### 1. Stdio Adapter

Local process spawning with stdin/stdout JSON communication. Synchronous operation (waits for result). Used in development environment via SpawnAdapter in backend.

### 2. Aliyun FC Adapter

Detects Aliyun FC environment (checks for FC-specific variables). Uses OSS mount point at `/mnt/oss` for model and data storage. Python available in FC runtime. Used in production deployment via AliyunFCAdapter in backend.

## Logging

Pluggable logging strategy with two implementations:

Interface:
```typescript
export interface MLLogger {
  log(message: string, level: string, context?: Record<string, any>): Promise<void>;
}
```

- **DatabaseLogger**: Writes logs to task_logs table for persistence and audit
- **ConsoleLogger**: Writes to stdout for development environments
- **Configuration**: createLogger() selects implementation based on config.type

## Python Scripts

Located in `ml/` directory (sibling to TypeScript). Three primary scripts handle model operations:

- **auto_tune_model.py**: Executes GridSearchCV hyperparameter tuning. Receives model name, feature columns, target column, and parameter grid via stdin; outputs best parameters and metrics via stdout (JSON lines).
- **manual_tune_model.py**: Trains model with fixed parameters (no grid search).
- **predict.py**: Loads trained model and applies to new data for batch predictions.

All scripts communicate via stdin/stdout JSON lines protocol.

## Data Flow

**Batch Training Workflow**: Backend receives POST request → calls batchTrain() → executes auto_tune_model.py via SpawnAdapter → Python runs GridSearchCV → outputs structured logs and results → backend saves to database → frontend polls for completion.

**Prediction in Aliyun FC**: Backend receives prediction request → invokes AliyunFCAdapter asynchronously → FC environment loads model from OSS → executes predict.py → saves predictions to OSS and database → backend returns 202 Accepted → frontend polls task status.

## Development & Deployment

For development and deployment instructions, see:

- [DEVELOPMENT.md](../../DEVELOPMENT.md) - Building and testing locally
- [DEPLOYMENT.md](../../DEPLOYMENT.md) - Aliyun FC deployment and configuration

Key environment variables:

- `PYTHON_PATH`: Python executable location (e.g., `/usr/bin/python3`)
- `ML_TIMEOUT`: Maximum execution time in milliseconds (default 300000)
- `OSS_ENDPOINT`, `OSS_BUCKET`, `OSS_ACCESS_KEY_ID`: OSS configuration for model and data storage

## Known Limitations

⚠️ Large datasets: Memory-bounded by Node.js/Python process
⚠️ Long training: May timeout on very large datasets
⚠️ Error handling: Python stderr might not propagate fully
⚠️ Logging: Database logger requires table schema
