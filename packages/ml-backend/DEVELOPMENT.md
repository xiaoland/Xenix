# ML Backend Development Guide

## Quick Start

### Prerequisites

- Node.js 18+
- pnpm 8+
- Python 3.8+

### Setup

```bash
# From root directory
pnpm install

# Build ml-backend
pnpm -F @xenix/ml-backend build

# Run locally
node dist/index.js < input.json
```

## Overview

ML Backend provides:

- **Batch Training**: GridSearchCV hyperparameter optimization
- **Single Training**: Manual parameter configuration
- **Prediction**: Batch prediction on new data
- **Adapters**: Local (Stdio) and Aliyun FC execution

## Structure

```
src/
├── core/           # Core ML functions
│   ├── batch-train.ts
│   ├── single-train.ts
│   └── predict.ts
├── adapters/       # Execution adapters
│   ├── stdio/index.ts      # Local spawning
│   └── aliyun-fc/index.ts  # FC invocation
├── types/          # Type definitions
│   ├── index.ts
│   ├── input.ts
│   └── output.ts
├── utils/          # Utilities
│   ├── python-executor.ts
│   ├── logger.ts
│   └── ...
└── python/         # Python scripts
    ├── auto_tune_model.py
    ├── manual_tune_model.py
    ├── predict.py
    └── requirements.txt
```

## Development

### Build

```bash
# Build TypeScript
pnpm -F @xenix/ml-backend build

# Build in watch mode
pnpm -F @xenix/ml-backend build:watch
```

### Run Locally

```bash
# Build first
pnpm -F @xenix/ml-backend build

# Create input JSON file
cat > input.json << EOF
{
  "type": "batch-train",
  "task_id": "test-task",
  "input_file": "data.csv",
  "model": "linear_regression",
  "feature_columns": ["X1", "X2"],
  "target_column": "y",
  "param_grid": {
    "fit_intercept": [true, false]
  }
}
EOF

# Run
node dist/index.js < input.json
```

### Test

```bash
pnpm -F @xenix/ml-backend test
pnpm -F @xenix/ml-backend test:watch
```

## Core Functions

### Batch Training

GridSearchCV hyperparameter optimization:

```typescript
import { batchTrain } from '@xenix/ml-backend'

const result = await batchTrain({
  taskId: 'task-123',
  inputFile: '/path/to/data.csv',
  model: 'linear_regression',
  featureColumns: ['X1', 'X2', 'X3'],
  targetColumn: 'y',
  paramGrid: {
    fit_intercept: [true, false],
    normalize: [true, false],
  }
})

// Returns: { task_id, best_params, metrics, model_path, timestamp }
```

### Single Training

Manual parameter configuration:

```typescript
import { singleTrain } from '@xenix/ml-backend'

const result = await singleTrain({
  taskId: 'task-124',
  inputFile: '/path/to/data.csv',
  model: 'linear_regression',
  featureColumns: ['X1', 'X2', 'X3'],
  targetColumn: 'y',
  params: {
    fit_intercept: true,
    normalize: false,
  }
})

// Returns: { task_id, params, metrics, model_path, timestamp }
```

### Prediction

Batch prediction on new data:

```typescript
import { predict } from '@xenix/ml-backend'

const result = await predict({
  taskId: 'task-125',
  modelPath: '/path/to/model.pkl',
  inputFile: '/path/to/new-data.csv',
  outputFile: '/path/to/predictions.csv'
})

// Returns: { task_id, predictions_file, record_count, timestamp }
```

## Adapters

### Stdio Adapter (Local Development)

Spawns local Node.js process:

```typescript
import { SpawnAdapter } from '@xenix/ml-backend'

const adapter = new SpawnAdapter()
const result = await adapter.batchTrain(config)
```

Features:

- Local process spawning
- stdin/stdout JSON communication
- Synchronous (waits for result)
- Good for development/testing

### Aliyun FC Adapter (Production)

Invokes Aliyun FC function:

```typescript
import { AliyunFCAdapter } from '@xenix/ml-backend'

const adapter = new AliyunFCAdapter()
const result = await adapter.batchTrain(config)
```

Features:

- Asynchronous invocation
- FC environment with Python
- OSS access for files
- Database direct write
- Good for production

## Python Executor

Spawns Python subprocess with JSON communication:

```typescript
import { executePython } from '@xenix/ml-backend/utils'

const result = await executePython<OutputType>({
  scriptPath: 'ml/auto_tune_model.py',
  input: {
    task_id: 'task-123',
    input_file: 'data.csv',
    model: 'linear_regression',
    param_grid: { /* ... */ }
  },
  timeout: 300000, // 5 minutes
  onLog: (log) => console.log(log)
})
```

## Python Scripts

Located in `ml/` directory (sibling to TypeScript).

### auto_tune_model.py

Executes GridSearchCV for hyperparameter optimization:

```bash
# Input via stdin (JSON)
{
  "task_id": "task-123",
  "input_file": "data.csv",
  "model": "linear_regression",
  "feature_columns": ["X1", "X2"],
  "target_column": "y",
  "param_grid": { "fit_intercept": [true, false] }
}

# Output via stdout (JSON lines)
{"type": "log", "data": {"message": "Loading data...", "level": "INFO"}}
{"type": "result", "data": {"best_params": {...}, "metrics": {...}}}
```

### manual_tune_model.py

Trains with specific parameters (no grid search):

```bash
# Similar input but with fixed params instead of param_grid
```

### predict.py

Loads trained model and applies to new data:

```bash
# Input
{
  "task_id": "task-125",
  "model_path": "model.pkl",
  "input_file": "new_data.csv",
  "output_file": "predictions.csv"
}

# Output
{"type": "result", "data": {"predictions_file": "predictions.csv", "record_count": 150}}
```

## Logging

Pluggable logging with two implementations:

```typescript
import { DatabaseLogger, ConsoleLogger } from '@xenix/ml-backend/utils'

// Database logging
const logger = new DatabaseLogger(db, taskId)

// Console logging
const logger = new ConsoleLogger()

await logger.log('Training started', 'INFO', { model: 'lr' })
```

## Common Tasks

### Add New Model Support

1. Create Python script in `ml/`:

```python
# ml/my_model.py
import json
import sys

def train(task_id, input_file, params):
    # Your model training logic
    return {
        'best_params': params,
        'metrics': {
            'r2_score': 0.85,
            'rmse': 0.15
        },
        'model_path': 'path/to/model.pkl'
    }

if __name__ == '__main__':
    input_data = json.loads(sys.stdin.read())
    result = train(**input_data)
    print(json.dumps({'type': 'result', 'data': result}))
```

1. Reference in TypeScript:

```typescript
const result = await executePython({
  scriptPath: 'ml/my_model.py',
  input: config
})
```

### Add Custom Error Handling

```typescript
try {
  const result = await batchTrain(config)
} catch (error) {
  if (error.code === 'TIMEOUT') {
    // Handle timeout
  } else if (error.code === 'PYTHON_ERROR') {
    // Handle Python script error
  }
}
```

### Monitor Long-Running Tasks

```typescript
const result = await batchTrain(config, {
  onLog: (log) => {
    console.log(`[${log.level}] ${log.message}`)
    // Save to database, send to frontend, etc.
  }
})
```

## Environment Variables

Key environment variables:

```bash
# Python location
PYTHON_PATH=/usr/bin/python3

# Execution timeout (milliseconds)
ML_TIMEOUT=300000

# Aliyun FC (when using AliyunFCAdapter)
ALIYUN_FC_ENDPOINT=https://xxx.fc.aliyuncs.com
ALIYUN_FC_FUNCTION_NAME=ml-backend-train

# Aliyun OSS
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET=xenix-data
OSS_ACCESS_KEY_ID=xxx
OSS_ACCESS_KEY_SECRET=xxx
```

## Build & Deployment

### Development

```bash
pnpm -F @xenix/ml-backend build
pnpm -F @xenix/ml-backend test
```

### Production

```bash
# Build with Aliyun FC configuration
pnpm build:fc

# Package for FC
pnpm package:fc

# Deploy to Aliyun FC
pnpm deploy:ml-backend
```

See [DEPLOYMENT.md](../../DEPLOYMENT.md) for detailed deployment instructions.

## Testing

```bash
# Run tests
pnpm -F @xenix/ml-backend test

# Watch mode
pnpm -F @xenix/ml-backend test:watch

# Coverage
pnpm -F @xenix/ml-backend test:coverage
```

## Troubleshooting

### Python Not Found

```bash
# Check Python path
which python3

# Set PYTHON_PATH in .env
PYTHON_PATH=/usr/bin/python3
```

### Timeout Errors

```bash
# Increase timeout in .env
ML_TIMEOUT=600000  # 10 minutes
```

### Memory Issues

```bash
# Check available memory
free -h

# Reduce dataset size or run on more powerful machine
```

### Module Import Errors

```bash
# Ensure ml/ directory is at project root
ls ml/auto_tune_model.py

# Install Python dependencies
pip install -r ml/requirements.txt
```

## Resources

- [Root DEVELOPMENT.md](../../DEVELOPMENT.md)
- [ML Backend Architecture](./ARCHITECTURE.md)
- [scikit-learn Documentation](https://scikit-learn.org/)
- [XGBoost Documentation](https://xgboost.readthedocs.io/)
- [LightGBM Documentation](https://lightgbm.readthedocs.io/)
