"""Single training with specific parameters"""

import os
import joblib
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import numpy as np

from ..types import SingleTrainInput, SingleTrainOutput
from ..models import get_model
from ..utils import log, read_data
from ..config import Config


def single_train(input_data: SingleTrainInput) -> SingleTrainOutput:
    """
    Single training with specific parameters (no tuning)

    Args:
        input_data: Single training input parameters

    Returns:
        Single training output with metrics
    """
    log(f"Starting single training for model {input_data.model}", "INFO", {
        "model": input_data.model,
        "features": input_data.feature_columns,
        "target": input_data.target_column,
        "params": input_data.params
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

        # Get model with specified parameters
        model = get_model(input_data.model, input_data.params)

        log(f"Training model with params: {input_data.params}", "INFO")

        # Train model
        model.fit(X_train, y_train)

        # Evaluate on test set
        y_pred = model.predict(X_test)

        metrics = {
            "r2": float(r2_score(y_test, y_pred)),
            "mse": float(mean_squared_error(y_test, y_pred)),
            "mae": float(mean_absolute_error(y_test, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred)))
        }

        log(f"Model metrics: R²={metrics['r2']:.4f}, RMSE={metrics['rmse']:.4f}, MAE={metrics['mae']:.4f}", "INFO")

        # Save model
        Config.ensure_directories()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_filename = f"model_{input_data.task_id}_{timestamp}.pkl"
        model_path = os.path.join(Config.MODEL_STORAGE_PATH, model_filename)

        joblib.dump(model, model_path)
        log(f"Model saved to {model_path}", "INFO")

        # Return result
        output = SingleTrainOutput(
            task_id=input_data.task_id,
            metrics=metrics,
            model_path=model_path,
            timestamp=datetime.now().isoformat()
        )

        log("Single training completed successfully", "INFO")
        return output

    except Exception as e:
        log(f"Single training failed: {str(e)}", "ERROR", {"error": str(e)})
        raise
