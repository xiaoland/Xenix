# @xenix/ml-backend

Standalone ML backend package for Xenix. Provides machine learning operations (training, prediction) with multiple delivery adapters.

## Features

- **Three Core Operations**:
  - `batchTrain` - Auto-tuning with GridSearchCV
  - `singleTrain` - Training with specific parameters
  - `predict` - Predictions with trained models

- **Multiple Adapters**:
  - **stdio** - Local development (stdin/stdout)
  - **Aliyun FC** - Serverless deployment
  - **HTTP** (future) - Direct API
  - **Message Queue** (future) - Async processing

- **Database Logging** - Direct writes to PostgreSQL using OpenTelemetry format

- **12 Regression Models**:
  - Linear Regression, Ridge, Lasso
  - Polynomial Regression
  - K-Nearest Neighbors
  - Decision Tree, Random Forest
  - AdaBoost, GBDT, XGBoost, LightGBM
  - Bayesian Ridge Regression

## Installation

```bash
pnpm install
```

## Development

```bash
# Build TypeScript
pnpm build

# Build and prepare FC workers
pnpm build:fc

# Watch mode
pnpm dev
```

## Usage

### As a Library

```typescript
import { batchTrain, createLogger } from '@xenix/ml-backend';

const logger = createLogger(taskId, {
  databaseUrl: process.env.DATABASE_URL,
});

const result = await batchTrain({
  inputFile: '/path/to/data.xlsx',
  model: 'regression.ridge',
  featureColumns: ['age', 'income'],
  targetColumn: 'score',
  paramGrid: { 'model__alpha': [0.1, 1.0, 10.0] },
  taskId: 123,
  logger,
});
```

### stdio Adapter (Local)

```bash
echo '{"operation":"batch-train","taskId":123,...}' | node dist/adapters/stdio/index.js
```

### Aliyun FC Deployment

```bash
# Deploy Python layer
pnpm run deploy:layer

# Deploy workers
pnpm run deploy:workers
```

## Architecture

```
packages/ml-backend/
├── src/
│   ├── core/          # Core ML functions
│   ├── adapters/      # Delivery adapters
│   ├── python/        # Python ML scripts
│   ├── utils/         # Utilities (logger, executor)
│   └── types/         # TypeScript types
├── fc-workers/        # FC worker packages (generated)
├── python-layer/      # Python dependencies
└── scripts/           # Build scripts
```

## License

MIT
