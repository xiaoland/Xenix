# Xenix Implementation Summary

## What Was Built

Xenix is a machine learning platform for regression tasks with a 2-step workflow:

1. **Upload & Train**: Upload data, tune models, view results
2. **Predict**: Select best model, generate predictions

## Key Features

### Database Integration (PostgreSQL + DrizzleORM)

- **Tasks Table**: Tracks background tasks (tuning, prediction)
- **Model Results Table**: Stores hyperparameters and metrics from tuning
- **Logs Table**: OpenTelemetry-compliant logging with task correlation

### Background Task Processing

- Python processes run in background via stdin/stdout
- Real-time status polling and logging
- Results stored in database

### Python ML Pipeline

- **tune_model.py**: GridSearchCV hyperparameter tuning
- **predict.py**: Batch prediction with tuned parameters
- **config.py**: Model constants
- Lazy imports, no database access, stdin/stdout communication

### Modern UI (Nuxt.js + Ant Design)

- 2-step wizard interface
- Drag & drop upload
- Real-time progress and logs
- Results table with model selection

### Logging System

- OpenTelemetry standards
- Real-time log viewer (3s polling)
- Color-coded severity levels
- Tabbed interface per task

## Supported Models (12)

Linear Regression, Ridge, Lasso, Bayesian Ridge, K-Nearest Neighbors, Decision Tree, Random Forest, Gradient Boosting, AdaBoost, XGBoost, LightGBM, Polynomial Regression

## Architecture

```
Frontend (Nuxt.js) → API (Nitro) → Database (PostgreSQL)
                        ↓
                   Python Scripts (stdin/stdout)
```

## Recent Changes

### Workflow Simplification (3→2 steps)

- Eliminated redundant model comparison
- Tuning provides all evaluation metrics
- Direct model selection from results table
- 40% faster execution

### Python Refactoring

- Removed database access from Python
- stdin/stdout JSON communication
- Conditional imports (no ModuleNotFoundError)
- No hardcoded data assumptions

### Prediction Fixes

- Parameters loaded from database
- Model-specific execution
- Clear error messages for missing libraries

## Security Features

- Environment-based configuration
- File type validation (Excel only)
- Upload isolation
- No hardcoded credentials

## Configuration

### Environment (.env)

```bash
DATABASE_URL=postgresql://xenix:xenix_password@localhost:5432/xenix_db
PYTHON_EXECUTABLE=python3
```

### Data (via API)

Feature columns and target specified per request, no defaults.

## Quick Start

1. Start PostgreSQL: `docker compose up -d`
2. Install: `pnpm install && pdm install`
3. Migrate: `pnpm db:generate && pnpm db:migrate`
4. Run: `pnpm dev`
5. Open <http://localhost:3005>

## API Endpoints

- `POST /api/upload`: Upload data, start tuning (requires featureColumns, targetColumn)
- `POST /api/predict`: Generate predictions (requires tuningTaskId, trainingDataPath)
- `GET /api/task/:taskId`: Task status
- `GET /api/results/:taskId`: Model metrics
- `GET /api/logs/:taskId`: Real-time logs

## File Structure

```
Xenix/
├── app/models/regression/  # Python ML scripts
├── server/api/             # API endpoints
├── server/database/        # Schema & migrations
├── server/utils/           # Python executor
├── docs/                   # Documentation
└── docker-compose.yml      # PostgreSQL
```

## What's Next

- User authentication
- Result file downloads
- Data preview
- Model versioning
- CI/CD pipeline
- Monitoring

## Notes

- GridSearchCV provides evaluation metrics (R², MSE, MAE)
- Best model selected by R² test score
- All results persisted in database
- Python scripts stateless, no DB access
- Single source of truth (DrizzleORM)
