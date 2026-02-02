# ML Pipeline Module

## Purpose

Documentation for the machine learning workflow implementation.

## Overview

The ML pipeline follows a 3-step workflow:

```
Prepare → Tune → Predict
```

## Step 1: Prepare

**Purpose**: Select and configure training data

**Process**:

1. Upload or select existing dataset
2. Select target column (what to predict)
3. Select feature columns (input variables)
4. Preview data statistics

**Output**: Prepared dataset configuration

## Step 2: Tune

**Purpose**: Find optimal hyperparameters for ML models

**Process**:

1. Select algorithms to evaluate
2. Configure hyperparameter search space
3. Run parallel tuning jobs
4. Compare model performance

**Supported Algorithms**:

- Linear/Polynomial Regression
- KNN, Decision Trees
- Random Forest, AdaBoost, GBDT
- XGBoost, LightGBM
- Bayesian Ridge

**Output**: Trained models with performance metrics

## Step 3: Predict

**Purpose**: Generate predictions using trained models

**Process**:

1. Select best performing model
2. Upload or select prediction data
3. Run batch prediction
4. View and export results

**Output**: Prediction results (CSV exportable)

## Background Tasks

Long-running operations run as background tasks:

- **Tuning tasks**: Hyperparameter search
- **Training tasks**: Model training
- **Prediction tasks**: Batch predictions

Tasks are monitored via the Tasks feature.

## Python Integration

ML computation handled by Python scripts:

```
business/ml/
  tune_model.py      # Hyperparameter tuning
  train_model.py     # Model training
  predict.py         # Batch prediction
  regression/        # Algorithm implementations
```

Python executor bridges Node.js and Python:

```typescript
import { executePython } from "../utils/pythonExecutor";
const result = await executePython("tune_model.py", params);
```

## Related

- Feature docs: `docs/features/ml/`, `docs/features/work-items/`
- Python code: `packages/backend/src/business/ml/`
- ML backend: `packages/ml-backend/`
