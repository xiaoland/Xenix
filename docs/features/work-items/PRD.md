# Work Items Feature

## Status: ✅ Active

## Overview

ML workflow items representing a complete machine learning pipeline: Prepare → Tune → Predict.

## User Stories

- As a user, I want to create a new ML workflow item
- As a user, I want to follow a 3-step workflow: Prepare, Tune, Predict
- As a user, I want to see the status of each step
- As a user, I want to view results after prediction

## Acceptance Criteria

1. Work item creation with name and associated project
2. Three-step workflow with clear navigation
3. Prepare step: Select dataset and target column
4. Tune step: Configure and run hyperparameter tuning
5. Predict step: Run predictions and view results
6. Progress persistence between sessions

## Workflow Steps

### 1. Prepare

- Upload or select existing dataset
- Select target column for prediction
- Preview data statistics

### 2. Tune

- Select ML algorithms
- Configure hyperparameter ranges
- Run tuning jobs (background tasks)
- Compare model performance

### 3. Predict

- Select best performing model
- Run predictions
- View and export results

## Technical Notes

- Each step has dedicated components in `features/ml/`
- Background tasks for long-running operations
- Results stored and accessible after completion

## Related

- Frontend: `packages/frontend/src/features/work-items/`, `features/ml/`
- Backend: `/api/work-items`, `/api/tasks` endpoints
