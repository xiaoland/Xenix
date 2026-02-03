# ML Feature

## Status: ✅ Active

## Overview

Machine learning-specific components and functionality for the Prepare → Tune → Predict workflow.

## User Stories

- As a user, I want to select columns for ML training
- As a user, I want to choose from multiple ML algorithms
- As a user, I want to tune hyperparameters automatically
- As a user, I want to compare model performance
- As a user, I want to run predictions and export results

## Components

### Prepare Step

- **PrepareStep.vue** - Main prepare step container
- **ColumnSelector.vue** - Select target and feature columns

### Tune Step

- **TuningStep.vue** - Main tuning step container
- **TaskParamsModal.vue** - Configure tuning parameters
- **ModelTuningTable.vue** - Display tuning results table
- **ModelTuningRow.vue** - Individual model row
- **ModelParamForm.vue** - Model parameter configuration
- **ManualTuneDialog.vue** - Manual hyperparameter tuning

### Prediction Step

- **PredictionStep.vue** - Main prediction step container
- **PredictionResult.vue** - Display prediction results

## Supported Algorithms

### Regression

- Linear Regression
- Polynomial Regression
- K-Nearest Neighbors (KNN)
- Decision Trees
- Random Forest
- AdaBoost
- Gradient Boosting (GBDT)
- XGBoost
- LightGBM
- Bayesian Ridge

## Technical Notes

- Python backend handles actual ML computation
- Models serialized and stored after training
- Predictions run against saved models
- Results exportable to CSV

## Related

- Frontend: `packages/frontend/src/features/ml/`
- Backend: `/api/ml`, Python ML scripts
