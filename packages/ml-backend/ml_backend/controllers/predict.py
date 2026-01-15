"""Prediction controller - delegates to model services"""

import pandas as pd
from datetime import datetime
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import numpy as np

from ..types import PredictInput, PredictOutput
from ..services import get_model
from ..utils import log, read_data, write_predictions


def predict(input_data: PredictInput) -> PredictOutput:
    """
    Make predictions using a trained model

    Delegates to the appropriate model service for prediction

    Args:
        input_data: Prediction input parameters

    Returns:
        Prediction output with predictions path and metrics
    """
    log(f"Starting prediction for model {input_data.model}", "INFO", {
        "model": input_data.model,
        "features": input_data.feature_columns,
        "train_data": input_data.train_data
    })

    try:
        # Read training data
        log(f"Reading training data from {input_data.train_data}", "INFO")
        train_df = read_data(input_data.train_data)

        # Read prediction data
        if isinstance(input_data.predict_data, str):
            # File path
            log(f"Reading prediction data from {input_data.predict_data}", "INFO")
            predict_df = read_data(input_data.predict_data)
        else:
            # Inline JSON array
            log(f"Using inline prediction data ({len(input_data.predict_data)} records)", "INFO")
            predict_df = pd.DataFrame(input_data.predict_data)

        # Get model service
        model_service = get_model(input_data.model)

        log(f"Using model service: {model_service.__class__.__name__}", "INFO")

        # Delegate prediction to model service
        predict_df_with_predictions = model_service.predict(train_df, predict_df, input_data)

        log(f"Generated predictions for {len(predict_df_with_predictions)} records", "INFO")

        # Write predictions to file
        predictions_path = write_predictions(predict_df_with_predictions, input_data.output_path)
        log(f"Predictions saved to {predictions_path}", "INFO")

        # Calculate metrics if target column exists in predict data
        metrics = None
        if input_data.target_column in predict_df.columns:
            y_true = predict_df[input_data.target_column]
            y_pred = predict_df_with_predictions[f'predicted_{input_data.target_column}']

            metrics = {
                "r2": float(r2_score(y_true, y_pred)),
                "mse": float(mean_squared_error(y_true, y_pred)),
                "mae": float(mean_absolute_error(y_true, y_pred)),
                "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred)))
            }
            log(f"Prediction metrics: R²={metrics['r2']:.4f}, RMSE={metrics['rmse']:.4f}", "INFO")

        # Return result
        output = PredictOutput(
            task_id=input_data.task_id,
            predictions_path=predictions_path,
            record_count=len(predict_df_with_predictions),
            metrics=metrics,
            timestamp=datetime.now().isoformat()
        )

        log("Prediction completed successfully", "INFO")
        return output

    except Exception as e:
        log(f"Prediction failed: {str(e)}", "ERROR", {"error": str(e)})
        raise
