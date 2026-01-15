# ML Backend Extraction Plan

**Date:** 2026-01-14
**Branch:** `claude/extract-ml-backend-package-hKj2o`
**Goal:** Extract a standalone `packages/ml-backend` from `packages/backend` to support flexible deployment to Aliyun FC and other platforms.

---

## 1. Executive Summary

This plan outlines the extraction of ML functionality from `packages/backend` into a new standalone `packages/ml-backend` package. The new package will provide a clean interface for ML operations (batch-train, single-train, predict) that can be delivered through multiple adapters (Aliyun FC, stdin/stdout, HTTP, etc.), while maintaining the existing functionality and improving deployment flexibility.

**Key Objectives:**
- Create a standalone, reusable ML backend package
- Support multiple delivery methods (serverless functions, local execution, etc.)
- Maintain existing functionality while improving architecture
- Enable independent deployment and scaling of ML operations
- Implement direct database logging from ML operations

---

## 2. Current State Analysis

### 2.1 Current Architecture

```
packages/backend/
├── src/
│   ├── business/ml/              # TypeScript orchestration + Python ML core
│   │   ├── index.ts              # High-level ML functions
│   │   ├── types.ts              # TypeScript interfaces
│   │   ├── auto_tune_model.py    # GridSearchCV hyperparameter tuning
│   │   ├── manual_tune_model.py  # Training with specific parameters
│   │   ├── predict.py            # Batch file-based prediction
│   │   ├── predict_on_json.py    # Inline JSON prediction
│   │   ├── predict_helpers.py    # Shared prediction utilities
│   │   ├── structured_io.py      # JSON communication layer
│   │   ├── scan_models.py        # Model discovery
│   │   ├── base.py               # Dynamic model importing
│   │   └── regression/           # 12 regression model implementations
│   ├── services/                 # Business logic (TaskService, ModelService, etc.)
│   ├── routes/                   # API endpoints
│   ├── repositories/             # Data access layer
│   ├── utils/                    # pythonExecutor, logger, etc.
│   └── ...
├── python-workers/               # Standalone FC workers
│   ├── auto_tune/
│   ├── manual_tune/
│   └── predict/
└── scripts/                      # Build scripts (copy-ml-to-workers.js, etc.)
```

### 2.2 Current ML Operations

**Three Core Operations:**

1. **Auto-Tune** (GridSearchCV)
   - Input: dataset, model, feature columns, target column, param grid
   - Output: best params, fitted model, metrics (MSE, MAE, R²)
   - Script: `auto_tune_model.py`

2. **Manual-Tune** (Single parameter set)
   - Input: dataset, model, feature columns, target column, specific params
   - Output: metrics, fitted model
   - Script: `manual_tune_model.py`

3. **Predict**
   - Input: training data, prediction data, model, params, features
   - Output: predictions, fitted model
   - Scripts: `predict.py` (file-based), `predict_on_json.py` (inline JSON)

### 2.3 Current Execution Patterns

**Pattern A: Local Development**
```typescript
setImmediate(() => {
  autoTune({...}).catch((error) => {...});
});
```

**Pattern B: Production (Aliyun FC)**
```typescript
await fcInvokeService.invokeAsync({
  functionName: 'auto-tune-worker',
  payload: {...},
});
```

### 2.4 Current Data Flow

```
API Request → Create Task (pending)
          ↓
    [Local Path]         [FC Path]
    executePythonTask()  fcInvokeService.invokeAsync()
          ↓                    ↓
    Spawn Python         FC Handler
    Read stdin/stdout    Run ML script
          ↓                    ↓
    Parse JSON output    Parse JSON output
          ↓                    ↓
    Update DB            Update DB
```

### 2.5 Problems with Current Architecture

1. **Tight Coupling**: ML logic is embedded in backend, hard to deploy independently
2. **Code Duplication**: ML scripts copied to multiple worker directories
3. **Limited Flexibility**: Hard to add new delivery methods (HTTP API, message queue, etc.)
4. **Deployment Complexity**: Must deploy entire backend to update ML code
5. **No Versioning**: ML operations and backend API versioned together
6. **Testing Difficulty**: Hard to test ML operations in isolation

---

## 3. Target Architecture

### 3.1 New Package Structure

```
packages/
├── shared/              # Existing shared types/schemas
├── backend/             # HTTP API, task orchestration, business logic
├── ml-backend/          # NEW: ML computation package
│   ├── src/
│   │   ├── index.ts                 # Main entry point
│   │   ├── core/                    # Core ML interface
│   │   │   ├── interface.ts         # ML operation interfaces
│   │   │   ├── batch-train.ts       # Batch training implementation
│   │   │   ├── single-train.ts      # Single training implementation
│   │   │   └── predict.ts           # Prediction implementation
│   │   ├── adapters/                # Delivery adapters
│   │   │   ├── aliyun-fc/           # Aliyun Function Compute adapter
│   │   │   │   ├── auto-tune.ts     # FC handler for auto-tune
│   │   │   │   ├── manual-tune.ts   # FC handler for manual-tune
│   │   │   │   └── predict.ts       # FC handler for predict
│   │   │   ├── stdio/               # stdin/stdout adapter
│   │   │   │   └── index.ts         # Local execution adapter
│   │   │   └── http/                # HTTP API adapter (future)
│   │   │       └── index.ts         # HTTP server for ML operations
│   │   ├── python/                  # Python ML scripts
│   │   │   ├── auto_tune_model.py
│   │   │   ├── manual_tune_model.py
│   │   │   ├── predict.py
│   │   │   ├── predict_on_json.py
│   │   │   ├── predict_helpers.py
│   │   │   ├── structured_io.py
│   │   │   ├── scan_models.py
│   │   │   ├── base.py
│   │   │   └── regression/          # Model implementations
│   │   │       ├── base.py
│   │   │       ├── ridge.py
│   │   │       ├── lasso.py
│   │   │       ├── ... (12 models)
│   │   ├── utils/                   # Utilities
│   │   │   ├── python-executor.ts   # Python process management
│   │   │   ├── logger.ts            # Database logger
│   │   │   └── structured-io.ts     # JSON parsing utilities
│   │   └── types/                   # TypeScript types
│   │       └── index.ts
│   ├── python-layer/                # Python dependencies for FC
│   │   └── requirements.txt
│   ├── s.yaml                       # FC deployment config
│   ├── package.json
│   ├── tsconfig.json
│   └── tsup.config.ts
└── frontend/            # Existing frontend
```

### 3.2 Clear Separation of Concerns

**packages/ml-backend Responsibilities:**
- ML computation (training, prediction)
- Python script execution
- Model management (loading, training, evaluation)
- Structured logging (to database)
- Multiple delivery adapters

**packages/backend Responsibilities:**
- HTTP API endpoints
- Task management and orchestration
- Dataset management
- User authentication/authorization
- Work item management
- Job queue management (BullMQ)
- Storage management (local/OSS)

**packages/shared Responsibilities:**
- Common types and schemas
- Validation schemas (Zod)
- Constants and enums

---

## 4. Interface Design

### 4.1 Core ML Interface

The `packages/ml-backend` will provide three main functions with a unified interface:

```typescript
// packages/ml-backend/src/core/interface.ts

export interface MLLogger {
  log(message: string, level: string, attributes?: Record<string, any>): Promise<void>;
}

export interface BatchTrainInput {
  inputFile: string;           // Path to training data (Excel)
  model: string;               // Model name (e.g., 'regression.ridge')
  featureColumns: string[];    // Feature column names
  targetColumn: string;        // Target column name
  paramGrid: Record<string, any[]>;  // Parameter grid for GridSearchCV
  taskId: number;              // Task ID for logging
  logger: MLLogger;            // Logger instance
}

export interface BatchTrainOutput {
  bestParams: Record<string, any>;  // Best parameters found
  fittedModel: any;                 // Serialized model (base64)
  metrics: {
    mse: number;
    mae: number;
    r2: number;
  };
}

export interface SingleTrainInput {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  params: Record<string, any>;  // Single parameter set
  taskId: number;
  logger: MLLogger;
}

export interface SingleTrainOutput {
  metrics: {
    mse: number;
    mae: number;
    r2: number;
  };
  fittedModel: any;  // Serialized model
}

export interface PredictInput {
  trainData: string;           // Path to training data
  predictData: string | any[]; // Path to prediction data OR inline JSON data
  outputPath: string;          // Where to save predictions
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  logger: MLLogger;
}

export interface PredictOutput {
  predictedData: any[];  // Predictions (can be file path or array)
  fittedModel: any;      // Serialized model
  metrics?: {            // Optional metrics if test data available
    mse: number;
    mae: number;
    r2: number;
  };
}

// Core ML functions
export async function batchTrain(input: BatchTrainInput): Promise<BatchTrainOutput>;
export async function singleTrain(input: SingleTrainInput): Promise<SingleTrainOutput>;
export async function predict(input: PredictInput): Promise<PredictOutput>;
```

### 4.2 Adapter Interface

Each adapter will implement a handler for the specific delivery method:

```typescript
// Adapter interface
export interface MLAdapter<TInput, TOutput> {
  handle(input: TInput): Promise<TOutput>;
}

// Example: Aliyun FC Adapter
export class AliyunFCAdapter implements MLAdapter<FCEvent, FCResponse> {
  async handle(event: FCEvent): Promise<FCResponse> {
    // Parse event
    // Call core ML function
    // Format response
  }
}

// Example: stdio Adapter
export class StdioAdapter implements MLAdapter<any, any> {
  async handle(input: any): Promise<any> {
    // Read from stdin
    // Call core ML function
    // Write to stdout
  }
}
```

---

## 5. Adapter Strategy

### 5.1 Supported Adapters

**1. Aliyun Function Compute (FC) Adapter**
- **Purpose**: Serverless deployment on Aliyun
- **Input**: FC event with payload (taskId, inputFile, model, etc.)
- **Output**: FC response with status/result
- **Features**:
  - NAS mount for file access (`/mnt/oss`)
  - Environment variables for config
  - Async invocation support
  - Python layer for ML dependencies

**2. stdio Adapter**
- **Purpose**: Local development and testing
- **Input**: JSON via stdin
- **Output**: Structured JSON via stdout
- **Features**:
  - Direct Python script execution
  - Line-by-line output parsing
  - Real-time log streaming
  - Process management

**3. HTTP Adapter** (Future)
- **Purpose**: Direct HTTP API for ML operations
- **Input**: HTTP POST with JSON body
- **Output**: HTTP JSON response
- **Features**:
  - RESTful API
  - Authentication support
  - Request validation
  - Rate limiting

**4. Message Queue Adapter** (Future)
- **Purpose**: Async job processing via message queue
- **Input**: Job message from queue (BullMQ, RabbitMQ, etc.)
- **Output**: Job completion/failure status
- **Features**:
  - Retry mechanism
  - Dead letter queue
  - Priority queuing
  - Load balancing

### 5.2 Adapter Selection Strategy

```typescript
// packages/ml-backend/src/index.ts
export function createAdapter(type: 'aliyun-fc' | 'stdio' | 'http' | 'mq'): MLAdapter {
  switch (type) {
    case 'aliyun-fc':
      return new AliyunFCAdapter();
    case 'stdio':
      return new StdioAdapter();
    case 'http':
      return new HttpAdapter();
    case 'mq':
      return new MessageQueueAdapter();
    default:
      throw new Error(`Unknown adapter type: ${type}`);
  }
}
```

---

## 6. Database Logger Implementation

### 6.1 Logger Interface

```typescript
// packages/ml-backend/src/utils/logger.ts

export interface LoggerConfig {
  databaseUrl: string;
  serviceName?: string;
  serviceVersion?: string;
}

export class DatabaseLogger implements MLLogger {
  private db: Database;
  private traceId: string;

  constructor(config: LoggerConfig, taskId: number) {
    this.db = createDatabaseConnection(config.databaseUrl);
    this.traceId = `task.${taskId}`;
  }

  async log(
    message: string,
    level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL',
    attributes?: Record<string, any>
  ): Promise<void> {
    const severityNumber = this.getSeverityNumber(level);

    await this.db.insert(schema.logs).values({
      timestamp: Date.now() * 1000000, // Nanoseconds
      observedTimestamp: Date.now() * 1000000,
      traceId: this.traceId,
      severityText: level,
      severityNumber,
      body: message,
      attributes: attributes || {},
      resource: {
        'service.name': 'xenix-ml-backend',
        'service.version': '1.0.0',
      },
    });
  }

  private getSeverityNumber(level: string): number {
    const levels = {
      DEBUG: 1,
      INFO: 9,
      WARNING: 13,
      ERROR: 17,
      CRITICAL: 21,
    };
    return levels[level] || 9;
  }
}
```

### 6.2 Logger Usage in Python

The Python scripts will continue using the existing `structured_io.py` module, but we'll enhance it to support direct database writes:

```python
# packages/ml-backend/src/python/structured_io.py

import os
import psycopg2
from datetime import datetime

class DatabaseLogger:
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.trace_id = f"task.{task_id}"
        self.db_url = os.environ.get('DATABASE_URL')
        self.conn = None

        if self.db_url:
            self.conn = psycopg2.connect(self.db_url)

    def log(self, message: str, level: str = 'INFO', **attributes):
        # Emit structured JSON for stdout parsing (existing behavior)
        emit_log(message, level, **attributes)

        # Also write directly to database if connection available
        if self.conn:
            self._write_to_db(message, level, attributes)

    def _write_to_db(self, message: str, level: str, attributes: dict):
        severity_number = {
            'DEBUG': 1,
            'INFO': 9,
            'WARNING': 13,
            'ERROR': 17,
            'CRITICAL': 21,
        }.get(level, 9)

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO logs (
                timestamp, observed_timestamp, trace_id,
                severity_text, severity_number, body, attributes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            int(datetime.now().timestamp() * 1e9),
            int(datetime.now().timestamp() * 1e9),
            self.trace_id,
            level,
            severity_number,
            message,
            json.dumps(attributes)
        ))
        self.conn.commit()
```

---

## 7. Migration Strategy

### 7.1 File Movements

**From `packages/backend/src/business/ml/` to `packages/ml-backend/src/python/`:**
- `auto_tune_model.py`
- `manual_tune_model.py`
- `predict.py`
- `predict_on_json.py`
- `predict_helpers.py`
- `structured_io.py`
- `scan_models.py`
- `base.py`
- `regression/` (entire directory with 12 models)

**From `packages/backend/src/utils/pythonExecutor.ts` to `packages/ml-backend/src/utils/python-executor.ts`:**
- Python execution logic
- Structured output parsing
- Process management

**From `packages/backend/src/business/ml/index.ts` to `packages/ml-backend/src/core/`:**
- Core ML functions (autoTune, manualTune, predict)
- Split into separate files (batch-train.ts, single-train.ts, predict.ts)

**From `packages/backend/src/business/ml/types.ts` to `packages/ml-backend/src/types/`:**
- TypeScript interfaces
- Update to match new interface design

**From `packages/backend/python-workers/` to `packages/ml-backend/src/adapters/aliyun-fc/`:**
- Transform handlers to use new adapter pattern
- Remove duplication of ML scripts

### 7.2 Update Strategy

**Step 1: Create New Package Structure**
- Create `packages/ml-backend/` directory
- Set up package.json, tsconfig.json, tsup.config.ts
- Create directory structure (src/, python/, adapters/, etc.)

**Step 2: Copy Python Scripts**
- Copy all Python files from `packages/backend/src/business/ml/` to `packages/ml-backend/src/python/`
- Update import paths in Python files if needed

**Step 3: Extract Core TypeScript Functions**
- Create new core interface in `packages/ml-backend/src/core/interface.ts`
- Implement batch-train, single-train, predict functions
- Copy and adapt pythonExecutor logic

**Step 4: Create Adapters**
- Implement stdio adapter for local development
- Implement Aliyun FC adapters
- Create adapter factory

**Step 5: Update Backend Package**
- Install ml-backend as dependency: `"@xenix/ml-backend": "workspace:*"`
- Update imports to use ml-backend package
- Remove duplicated Python scripts and TypeScript code
- Update routes to use new interface
- Update FCInvokeService to call new FC functions

**Step 6: Update Build Scripts**
- Remove `scripts/copy-ml-to-workers.js` (no longer needed)
- Update `scripts/build-python-layer.js` to use ml-backend
- Update deployment scripts

**Step 7: Update Deployment Config**
- Update `s.yaml` to deploy from ml-backend package
- Configure environment variables for new functions

---

## 8. Implementation Steps

### Phase 1: Setup Package Structure (Steps 1-3)

#### Step 1: Create ml-backend Package Directory
```bash
mkdir -p packages/ml-backend
cd packages/ml-backend
```

#### Step 2: Initialize Package
Create `package.json`:
```json
{
  "name": "@xenix/ml-backend",
  "version": "0.0.1",
  "type": "module",
  "private": true,
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    },
    "./adapters/stdio": "./dist/adapters/stdio/index.js",
    "./adapters/aliyun-fc": "./dist/adapters/aliyun-fc/index.js"
  },
  "scripts": {
    "dev": "tsup --watch",
    "build": "tsup",
    "build:fc": "pnpm run build && pnpm run copy:python && pnpm run copy:workers",
    "copy:python": "node scripts/copy-python.js",
    "copy:workers": "node scripts/copy-to-workers.js",
    "deploy:layer": "s deploy xenix-ml-python-layer --use-local",
    "deploy:workers": "s deploy --all --use-local",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@xenix/shared": "workspace:*",
    "drizzle-orm": "^0.45.1",
    "pg": "^8.13.1",
    "pino": "^9.7.0",
    "zod": "^3.24.1"
  },
  "devDependencies": {
    "@serverless-devs/s": "^3.1.10",
    "@types/node": "^25.0.3",
    "@types/pg": "^8.11.10",
    "fs-extra": "^11.3.3",
    "tsup": "^8.5.1",
    "typescript": "^5.7.3",
    "vitest": "^2.1.8"
  }
}
```

#### Step 3: Create Directory Structure
```bash
mkdir -p src/{core,adapters/{stdio,aliyun-fc},python/regression,utils,types}
mkdir -p python-layer
mkdir -p scripts
```

### Phase 2: Extract Python Scripts (Steps 4-6)

#### Step 4: Copy Python ML Scripts
Copy all Python files from backend:
```bash
# From packages/backend/src/business/ml/ to packages/ml-backend/src/python/
cp packages/backend/src/business/ml/*.py packages/ml-backend/src/python/
cp -r packages/backend/src/business/ml/regression packages/ml-backend/src/python/
```

Files to copy:
- `auto_tune_model.py`
- `manual_tune_model.py`
- `predict.py`
- `predict_on_json.py`
- `predict_helpers.py`
- `structured_io.py`
- `scan_models.py`
- `base.py`
- `regression/*.py` (all 12+ model files)

#### Step 5: Create Python Requirements
Create `packages/ml-backend/python-layer/requirements.txt`:
```txt
pandas>=2.3.3
numpy>=1.26.0
openpyxl>=3.1.5
scikit-learn>=1.8.0
statsmodels>=0.14.6
xgboost>=2.1.3
lightgbm>=4.6.0
pydantic>=2.12.5
psycopg2-binary>=2.9.10
```

#### Step 6: Update Python Import Paths
No changes needed if all Python files stay in the same relative directory structure.

### Phase 3: Create Core TypeScript Interface (Steps 7-10)

#### Step 7: Create Type Definitions
Create `packages/ml-backend/src/types/index.ts`:
```typescript
export interface MLLogger {
  log(message: string, level: string, attributes?: Record<string, any>): Promise<void>;
}

export interface BatchTrainInput {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  paramGrid: Record<string, any[]>;
  taskId: number;
  logger: MLLogger;
}

export interface BatchTrainOutput {
  bestParams: Record<string, any>;
  fittedModel: any;
  metrics: {
    mse: number;
    mae: number;
    r2: number;
  };
}

// ... (continue with other interfaces from section 4.1)
```

#### Step 8: Extract Python Executor
Copy and adapt `packages/backend/src/utils/pythonExecutor.ts` to `packages/ml-backend/src/utils/python-executor.ts`:
- Keep execution logic
- Update imports to use local types
- Make it more generic (remove backend-specific dependencies)

#### Step 9: Create Database Logger
Create `packages/ml-backend/src/utils/logger.ts`:
- Implement DatabaseLogger class (see section 6.1)
- Support both direct DB writes and structured JSON output

#### Step 10: Implement Core ML Functions
Create three files:
- `packages/ml-backend/src/core/batch-train.ts` - Implement batchTrain()
- `packages/ml-backend/src/core/single-train.ts` - Implement singleTrain()
- `packages/ml-backend/src/core/predict.ts` - Implement predict()

Each function should:
1. Accept the standard input interface
2. Create a Python executor instance
3. Call the appropriate Python script
4. Parse structured output
5. Return the standard output interface

### Phase 4: Create Adapters (Steps 11-14)

#### Step 11: Create stdio Adapter
Create `packages/ml-backend/src/adapters/stdio/index.ts`:
```typescript
import { batchTrain, singleTrain, predict } from '../../core';
import { DatabaseLogger } from '../../utils/logger';

export async function handleStdio() {
  // Read JSON from stdin
  const input = await readStdin();

  // Determine operation type
  const { operation, ...params } = input;

  // Create logger
  const logger = new DatabaseLogger(
    { databaseUrl: process.env.DATABASE_URL! },
    params.taskId
  );

  // Execute operation
  let result;
  switch (operation) {
    case 'batch-train':
      result = await batchTrain({ ...params, logger });
      break;
    case 'single-train':
      result = await singleTrain({ ...params, logger });
      break;
    case 'predict':
      result = await predict({ ...params, logger });
      break;
    default:
      throw new Error(`Unknown operation: ${operation}`);
  }

  // Write result to stdout
  console.log(JSON.stringify({ type: 'result', data: result }));
}

function readStdin(): Promise<any> {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.on('data', chunk => data += chunk);
    process.stdin.on('end', () => resolve(JSON.parse(data)));
  });
}
```

#### Step 12: Create Aliyun FC Auto-Tune Adapter
Create `packages/ml-backend/src/adapters/aliyun-fc/auto-tune.ts`:
```typescript
import { batchTrain } from '../../core/batch-train';
import { DatabaseLogger } from '../../utils/logger';

export async function handler(event: any, context: any) {
  const { taskId, inputFile, model, featureColumns, targetColumn, paramGrid } = event;

  const logger = new DatabaseLogger(
    { databaseUrl: process.env.DATABASE_URL! },
    taskId
  );

  try {
    const result = await batchTrain({
      inputFile,
      model,
      featureColumns,
      targetColumn,
      paramGrid,
      taskId,
      logger,
    });

    return {
      statusCode: 200,
      body: JSON.stringify(result),
    };
  } catch (error) {
    await logger.log(`Error: ${error.message}`, 'ERROR');
    return {
      statusCode: 500,
      body: JSON.stringify({ error: error.message }),
    };
  }
}
```

#### Step 13: Create Aliyun FC Manual-Tune Adapter
Similar to auto-tune, create `packages/ml-backend/src/adapters/aliyun-fc/manual-tune.ts`.

#### Step 14: Create Aliyun FC Predict Adapter
Similar to auto-tune, create `packages/ml-backend/src/adapters/aliyun-fc/predict.ts`.

### Phase 5: Create Build System (Steps 15-17)

#### Step 15: Create tsup Config
Create `packages/ml-backend/tsup.config.ts`:
```typescript
import { defineConfig } from 'tsup';

export default defineConfig({
  entry: [
    'src/index.ts',
    'src/adapters/stdio/index.ts',
    'src/adapters/aliyun-fc/auto-tune.ts',
    'src/adapters/aliyun-fc/manual-tune.ts',
    'src/adapters/aliyun-fc/predict.ts',
  ],
  format: ['esm'],
  dts: true,
  clean: true,
  sourcemap: true,
  target: 'node18',
  external: ['pg-native'],
});
```

#### Step 16: Create Python Copy Script
Create `packages/ml-backend/scripts/copy-python.js`:
```javascript
import fs from 'fs-extra';
import path from 'path';

const pythonSource = path.join(process.cwd(), 'src', 'python');
const destinations = [
  path.join(process.cwd(), 'dist', 'python'),
];

for (const dest of destinations) {
  fs.copySync(pythonSource, dest);
  console.log(`Copied Python scripts to ${dest}`);
}
```

#### Step 17: Create Worker Copy Script
Create `packages/ml-backend/scripts/copy-to-workers.js`:
```javascript
import fs from 'fs-extra';
import path from 'path';

const workers = ['auto-tune', 'manual-tune', 'predict'];
const pythonSource = path.join(process.cwd(), 'src', 'python');
const adapterSource = path.join(process.cwd(), 'dist', 'adapters', 'aliyun-fc');

for (const worker of workers) {
  const workerDir = path.join(process.cwd(), 'fc-workers', worker);

  // Copy Python scripts
  const pythonDest = path.join(workerDir, 'python');
  fs.copySync(pythonSource, pythonDest);

  // Copy adapter handler
  const handlerFile = `${worker}.js`;
  const indexFile = path.join(workerDir, 'index.js');
  fs.copyFileSync(
    path.join(adapterSource, handlerFile),
    indexFile
  );

  console.log(`✓ ${worker} worker prepared`);
}
```

### Phase 6: Create Deployment Config (Step 18)

#### Step 18: Create s.yaml
Create `packages/ml-backend/s.yaml`:
```yaml
edition: 3.0.0
name: xenix-ml-backend
access: default

vars:
  region: cn-hangzhou

resources:
  # Python Layer
  xenix-ml-python-layer:
    component: fc3
    props:
      region: ${vars.region}
      layerName: xenix-ml-python-deps
      code: ./python-layer
      description: Python ML dependencies for Xenix
      compatibleRuntime:
        - python3.10

  # Auto-tune Worker
  ml-auto-tune-worker:
    component: fc3
    props:
      region: ${vars.region}
      functionName: ml-auto-tune-worker
      runtime: python3.10
      handler: index.handler
      memorySize: 4096
      timeout: 600
      code: ./fc-workers/auto-tune
      layers:
        - ${resources.xenix-ml-python-layer.output.arn}
      environmentVariables:
        PYTHONPATH: /opt/python
        DATABASE_URL: ${env.DATABASE_URL}
      nasConfig:
        userId: 10003
        groupId: 10003
        mountPoints:
          - serverAddr: ${env.OSS_NAS_SERVER_ADDR}
            nasDir: /xenix-oss
            fcDir: /mnt/oss

  # Manual-tune Worker
  ml-manual-tune-worker:
    component: fc3
    props:
      region: ${vars.region}
      functionName: ml-manual-tune-worker
      runtime: python3.10
      handler: index.handler
      memorySize: 4096
      timeout: 600
      code: ./fc-workers/manual-tune
      layers:
        - ${resources.xenix-ml-python-layer.output.arn}
      environmentVariables:
        PYTHONPATH: /opt/python
        DATABASE_URL: ${env.DATABASE_URL}
      nasConfig:
        userId: 10003
        groupId: 10003
        mountPoints:
          - serverAddr: ${env.OSS_NAS_SERVER_ADDR}
            nasDir: /xenix-oss
            fcDir: /mnt/oss

  # Predict Worker
  ml-predict-worker:
    component: fc3
    props:
      region: ${vars.region}
      functionName: ml-predict-worker
      runtime: python3.10
      handler: index.handler
      memorySize: 4096
      timeout: 600
      code: ./fc-workers/predict
      layers:
        - ${resources.xenix-ml-python-layer.output.arn}
      environmentVariables:
        PYTHONPATH: /opt/python
        DATABASE_URL: ${env.DATABASE_URL}
      nasConfig:
        userId: 10003
        groupId: 10003
        mountPoints:
          - serverAddr: ${env.OSS_NAS_SERVER_ADDR}
            nasDir: /xenix-oss
            fcDir: /mnt/oss
```

### Phase 7: Update Backend Package (Steps 19-23)

#### Step 19: Add ml-backend Dependency
Update `packages/backend/package.json`:
```json
{
  "dependencies": {
    "@xenix/ml-backend": "workspace:*",
    // ... existing dependencies
  }
}
```

Run `pnpm install` to link the workspace package.

#### Step 20: Update Backend ML Index
Update `packages/backend/src/business/ml/index.ts`:
```typescript
// Remove all implementation, re-export from ml-backend
export {
  batchTrain,
  singleTrain,
  predict,
} from '@xenix/ml-backend';

// Or create wrapper functions if needed
import { batchTrain as mlBatchTrain } from '@xenix/ml-backend';
import { DatabaseLogger } from '@xenix/ml-backend/utils/logger';

export async function autoTune(options: AutoTuneOptions): Promise<void> {
  const logger = new DatabaseLogger(
    { databaseUrl: process.env.DATABASE_URL! },
    options.taskId
  );

  return mlBatchTrain({
    ...options,
    logger,
  });
}
```

#### Step 21: Update FCInvokeService
Update `packages/backend/src/services/FCInvokeService.ts`:
```typescript
// Update function names to match new ml-backend workers
async invokeAutoTune(payload: any) {
  return this.invokeAsync({
    functionName: 'ml-auto-tune-worker',  // Changed from 'auto-tune-worker'
    payload,
  });
}

async invokeManualTune(payload: any) {
  return this.invokeAsync({
    functionName: 'ml-manual-tune-worker',  // Changed from 'manual-tune-worker'
    payload,
  });
}

async invokePredict(payload: any) {
  return this.invokeAsync({
    functionName: 'ml-predict-worker',  // Changed from 'predict-worker'
    payload,
  });
}
```

#### Step 22: Remove Duplicated Files
Remove files that are now in ml-backend:
```bash
# DO NOT remove these yet, keep for reference until testing is complete
# rm -rf packages/backend/src/business/ml/*.py
# rm -rf packages/backend/src/business/ml/regression
# rm -rf packages/backend/python-workers
```

#### Step 23: Update Backend Build Scripts
Update `packages/backend/package.json` scripts:
```json
{
  "scripts": {
    "build": "tsup",
    "build:fc": "pnpm run build:shared && tsup --config tsup.config.fc.ts && pnpm run copy:assets",
    // Remove: "copy:ml": "node scripts/copy-ml-to-workers.js",
    // Remove: "build:workers": "pnpm run copy:ml",
    // Remove: "deploy:workers": "s deploy auto-tune-worker manual-tune-worker predict-worker --use-local",
    // Add: "deploy:ml": "cd ../ml-backend && pnpm run deploy:workers",
  }
}
```

Remove `packages/backend/scripts/copy-ml-to-workers.js` (no longer needed).

### Phase 8: Update Root Package (Step 24)

#### Step 24: Update Root Scripts
Update root `package.json`:
```json
{
  "scripts": {
    "dev": "pnpm --parallel --filter \"@xenix/*\" dev",
    "dev:ml-backend": "pnpm --filter \"@xenix/ml-backend\" dev",
    "build": "pnpm --filter \"@xenix/*\" build",
    "build:ml-backend": "pnpm --filter \"@xenix/ml-backend\" build",
    // ... existing scripts
  }
}
```

### Phase 9: Testing (Steps 25-27)

#### Step 25: Test Local Development
```bash
# Terminal 1: Start backend
cd packages/backend
pnpm dev

# Terminal 2: Test ML operations
curl -X POST http://localhost:3000/api/tune/auto-tune \
  -H "Content-Type: application/json" \
  -d '{
    "datasetId": 1,
    "model": "regression.ridge",
    "featureColumns": ["age", "income"],
    "targetColumn": "score",
    "paramGrid": {"model__alpha": [0.1, 1.0, 10.0]}
  }'
```

#### Step 26: Test FC Deployment
```bash
# Build and deploy ml-backend workers
cd packages/ml-backend
pnpm run build:fc
pnpm run deploy:layer
pnpm run deploy:workers

# Test FC invocation from backend
cd packages/backend
# Make API call that triggers FC invocation
```

#### Step 27: Verify Logs
```bash
# Check database logs
psql $DATABASE_URL -c "SELECT * FROM logs WHERE trace_id LIKE 'task.%' ORDER BY timestamp DESC LIMIT 10;"

# Check FC logs
s logs -f ml-auto-tune-worker
```

### Phase 10: Cleanup (Steps 28-30)

#### Step 28: Remove Old Files from Backend
After confirming everything works:
```bash
cd packages/backend
rm -rf src/business/ml/*.py
rm -rf src/business/ml/regression
rm -rf python-workers
rm scripts/copy-ml-to-workers.js
```

#### Step 29: Update Backend s.yaml
Update `packages/backend/s.yaml`:
- Remove old worker definitions (auto-tune-worker, manual-tune-worker, predict-worker)
- Keep only xenix-backend and xenix-python-layer (if still needed for backend Python utilities)

#### Step 30: Update Documentation
Update relevant documentation files:
- `docs/structure.md` - Add ml-backend package
- `docs/DEPLOYMENT.md` - Update deployment instructions
- `README.md` - Update architecture diagram

---

## 9. Testing Strategy

### 9.1 Unit Tests

**Python Tests:**
- Test each model's `auto_tune()`, `manual_tune()`, `evaluate()`, `predict()` methods
- Test `structured_io.py` logging functions
- Test model loading and dynamic imports

**TypeScript Tests:**
- Test core functions (batchTrain, singleTrain, predict)
- Test Python executor
- Test database logger
- Test each adapter

### 9.2 Integration Tests

**Local Integration:**
- Test stdio adapter with real Python scripts
- Test full end-to-end flow (API → ML → DB)
- Test with real datasets

**FC Integration:**
- Test FC handlers in local FC environment
- Test with NAS mount simulation
- Test async invocation

### 9.3 End-to-End Tests

**Full System Test:**
1. Upload dataset via backend API
2. Create auto-tune task
3. Verify FC invocation
4. Check logs in database
5. Verify task completion
6. Check result accuracy

---

## 10. Risk Assessment and Mitigation

### 10.1 Risks

1. **Breaking Changes**: Existing functionality may break during extraction
   - **Mitigation**: Keep old code until full testing is complete

2. **Performance Regression**: New architecture may be slower
   - **Mitigation**: Benchmark before and after, optimize if needed

3. **Deployment Complexity**: More packages to deploy
   - **Mitigation**: Create unified deployment script, document process

4. **Database Connection Issues**: Direct DB writes from Python may cause connection pool exhaustion
   - **Mitigation**: Implement connection pooling, fallback to JSON output

5. **Import Path Issues**: TypeScript/Python import paths may break
   - **Mitigation**: Test thoroughly, use absolute paths where possible

### 10.2 Rollback Plan

If issues are encountered:
1. Keep old backend code intact (don't delete until confirmed working)
2. Can revert backend to use old code path
3. Can disable FC invocation and use local execution
4. Can rollback FC deployments using Aliyun console

---

## 11. Success Criteria

### 11.1 Functional Requirements

- ✅ All existing ML operations work (auto-tune, manual-tune, predict)
- ✅ Local development uses stdio adapter
- ✅ Production uses Aliyun FC adapter
- ✅ Logs are written to database
- ✅ All 12 regression models work correctly
- ✅ Model scanning and metadata sync works
- ✅ File-based and inline prediction work

### 11.2 Non-Functional Requirements

- ✅ Performance is equal to or better than before
- ✅ Code is cleaner and more maintainable
- ✅ ml-backend can be deployed independently
- ✅ Documentation is updated
- ✅ All tests pass
- ✅ No breaking changes to frontend

### 11.3 Architecture Requirements

- ✅ Clear separation between backend and ml-backend
- ✅ ml-backend has no dependencies on backend
- ✅ ml-backend can be used standalone
- ✅ Adapters are swappable
- ✅ Interface is well-defined and typed

---

## 12. Timeline Estimation

**Phase 1-2 (Setup & Python)**: 2-3 hours
**Phase 3 (Core TypeScript)**: 3-4 hours
**Phase 4 (Adapters)**: 2-3 hours
**Phase 5 (Build System)**: 1-2 hours
**Phase 6 (Deployment)**: 1 hour
**Phase 7 (Backend Updates)**: 2-3 hours
**Phase 8-10 (Testing & Cleanup)**: 3-4 hours

**Total**: ~15-20 hours

---

## 13. Future Enhancements

### 13.1 Additional Adapters

- HTTP adapter for direct ML API
- Message queue adapter for async processing
- gRPC adapter for high-performance communication
- WebSocket adapter for streaming predictions

### 13.2 Model Storage

- Save trained models to OSS/S3
- Model versioning
- Model registry
- Model serving infrastructure

### 13.3 Monitoring

- Prometheus metrics
- Distributed tracing
- Performance monitoring
- Cost tracking

### 13.4 Advanced Features

- Batch prediction optimization
- Model ensembling
- A/B testing for models
- AutoML integration
- GPU support for training

---

## 14. Dependencies

### 14.1 Required Dependencies

**packages/ml-backend:**
- Runtime: Node.js 18+, Python 3.10+
- TypeScript: `typescript`, `tsup`
- Database: `drizzle-orm`, `pg`
- Logging: `pino`
- Shared: `@xenix/shared`
- ML: pandas, numpy, scikit-learn, xgboost, lightgbm (in Python layer)

### 14.2 Development Dependencies

- Testing: `vitest`
- Build: `tsup`, `fs-extra`
- Deployment: `@serverless-devs/s`

---

## 15. Approval and Sign-off

This plan is ready for implementation. The user stated that approval is optional, so we can proceed with implementation immediately after plan creation.

**Plan Status**: ✅ Ready for Implementation

**Next Steps**:
1. Create RESULT.md to track progress
2. Begin Phase 1: Setup Package Structure
3. Update RESULT.md after each phase completion
