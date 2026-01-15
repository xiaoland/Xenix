"""Batch training controller - delegates to model services"""

import os
import joblib
from datetime import datetime

from ..types import BatchTrainInput, BatchTrainOutput
from ..services import get_model
from ..utils import log, read_data
from ..config import Config


def batch_train(input_data: BatchTrainInput) -> BatchTrainOutput:
    """
    Batch training with GridSearchCV hyperparameter tuning

    Delegates to the appropriate model service for training

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

        log(f"Training data loaded: {len(df)} rows, {len(df.columns)} columns", "INFO")

        # Get model service
        model_service = get_model(input_data.model)

        log(f"Using model service: {model_service.__class__.__name__}", "INFO")

        # Delegate training to model service
        result = model_service.batch_train(df, input_data)

        log(f"Best parameters found: {result['best_params']}", "INFO")
        log(f"Model metrics: {result['metrics']}", "INFO")

        # Save model
        Config.ensure_directories()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_filename = f"model_{input_data.task_id}_{timestamp}.pkl"
        model_path = os.path.join(Config.MODEL_STORAGE_PATH, model_filename)

        joblib.dump(result['model'], model_path)
        log(f"Model saved to {model_path}", "INFO")

        # Return result
        output = BatchTrainOutput(
            task_id=input_data.task_id,
            best_params=result['best_params'],
            metrics=result['metrics'],
            model_path=model_path,
            timestamp=datetime.now().isoformat()
        )

        log("Batch training completed successfully", "INFO")
        return output

    except Exception as e:
        log(f"Batch training failed: {str(e)}", "ERROR", {"error": str(e)})
        raise
