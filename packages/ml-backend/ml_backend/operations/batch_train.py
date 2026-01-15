"""Batch training with GridSearchCV (auto-tuning)"""

import os
import joblib
from datetime import datetime
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import numpy as np

from ..types import BatchTrainInput, BatchTrainOutput
from ..models import get_model, get_param_grid
from ..utils import log, read_data
from ..config import Config


def batch_train(input_data: BatchTrainInput) -> BatchTrainOutput:
    """
    Batch training with GridSearchCV hyperparameter tuning

    Args:
        input_data: Batch training input parameters

    Returns:
        Batch training output with best parameters and metrics
    """
    log(f"Starting batch training for model {input_data.model}", "INFO", {
        "model": input_data.model,
        "features": input_data.feature_columns,
        "target": input_data.target_column
    })

    try:
        # Read training data
        log(f"Reading training data from {input_data.input_file}", "INFO")
        df = read_data(input_data.input_file)

        # Prepare features and target
        X = df[input_data.feature_columns]
        y = df[input_data.target_column]

        # Split data for validation
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        log(f"Training data shape: {X_train.shape}, Test data shape: {X_test.shape}", "INFO")

        # Get base model
        base_model = get_model(input_data.model)

        # Merge user-provided param_grid with defaults
        default_grid = get_param_grid(input_data.model)
        param_grid = {**default_grid, **input_data.param_grid}

        log(f"Running GridSearchCV with param_grid: {param_grid}", "INFO")

        # Run GridSearchCV
        grid_search = GridSearchCV(
            estimator=base_model,
            param_grid=param_grid,
            cv=5,
            scoring='r2',
            n_jobs=-1,
            verbose=1
        )

        grid_search.fit(X_train, y_train)

        # Get best model
        best_model = grid_search.best_estimator_
        best_params = grid_search.best_params_

        log(f"Best parameters found: {best_params}", "INFO")

        # Evaluate on test set
        y_pred = best_model.predict(X_test)

        metrics = {
            "r2": float(r2_score(y_test, y_pred)),
            "mse": float(mean_squared_error(y_test, y_pred)),
            "mae": float(mean_absolute_error(y_test, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
            "cv_score_mean": float(grid_search.best_score_),
            "cv_scores": [float(s) for s in grid_search.cv_results_['mean_test_score']]
        }

        log(f"Model metrics: R²={metrics['r2']:.4f}, RMSE={metrics['rmse']:.4f}, MAE={metrics['mae']:.4f}", "INFO")

        # Save model
        Config.ensure_directories()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_filename = f"model_{input_data.task_id}_{timestamp}.pkl"
        model_path = os.path.join(Config.MODEL_STORAGE_PATH, model_filename)

        joblib.dump(best_model, model_path)
        log(f"Model saved to {model_path}", "INFO")

        # Return result
        output = BatchTrainOutput(
            task_id=input_data.task_id,
            best_params=best_params,
            metrics=metrics,
            model_path=model_path,
            timestamp=datetime.now().isoformat()
        )

        log("Batch training completed successfully", "INFO")
        return output

    except Exception as e:
        log(f"Batch training failed: {str(e)}", "ERROR", {"error": str(e)})
        raise
