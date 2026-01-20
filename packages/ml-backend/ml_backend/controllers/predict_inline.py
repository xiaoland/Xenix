"""Inline prediction controller"""

import os
import joblib
import pandas as pd
from datetime import datetime

from ..types import PredictInlineInput, PredictInlineOutput
from ..services import get_model
from ..utils import read_data
from ..utils.logger import TaskLogger
from ..config import Config


def predict_inline(input_data: PredictInlineInput, logger: TaskLogger) -> PredictInlineOutput:
    """
    Inline prediction with model saving

    Trains model on training data, makes predictions on inline JSON data, saves
    the fitted model and returns predictions as JSON.

    Args:
        input_data: Inline prediction input parameters
        logger: Task logger instance

    Returns:
        Inline prediction output with model path and prediction data
    """
    logger.log(f"Starting inline prediction for model {input_data.model}", "INFO", {
        "model": input_data.model,
        "features": input_data.feature_columns,
        "targets": input_data.target_columns,
        "train_data": input_data.train_data_path,
        "inline_records": len(input_data.to_predict_data)
    })

    try:
        # Read training data
        logger.log(f"Reading training data from {input_data.train_data_path}", "INFO")
        train_df = read_data(input_data.train_data_path)
        logger.log(f"Training data loaded: {len(train_df)} rows, {len(train_df.columns)} columns", "INFO")

        # Convert inline JSON data to DataFrame
        logger.log(f"Converting inline data ({len(input_data.to_predict_data)} records) to DataFrame", "INFO")
        predict_df = pd.DataFrame(input_data.to_predict_data)
        logger.log(f"Prediction data ready: {len(predict_df)} rows", "INFO")

        # Get model service
        model_service = get_model(input_data.model)
        logger.log(f"Using model service: {model_service.__class__.__name__}", "INFO")

        # Train model and get fitted instance
        logger.log("Training model on full training dataset", "INFO")
        model = model_service.train_and_get_model(train_df, input_data)

        # Make predictions
        logger.log("Making predictions", "INFO")
        predict_df_with_predictions = model_service.predict_with_model(
            model, predict_df, input_data
        )
        logger.log(f"Generated predictions for {len(predict_df_with_predictions)} records", "INFO")

        # Save fitted model to task directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_filename = f"model_{timestamp}.pkl"
        model_path = os.path.join(Config.BASE_PATH, model_filename)

        joblib.dump(model, model_path)
        logger.log(f"Model saved to {model_filename}", "INFO")

        # Convert predictions DataFrame to list of dicts for JSON output
        predictions_list = predict_df_with_predictions.to_dict(orient='records')
        logger.log(f"Converted predictions to JSON format ({len(predictions_list)} records)", "INFO")

        # Return output with relative model path and inline prediction data
        output = PredictInlineOutput(
            fitted_model_path=model_filename,
            predicted_data=predictions_list
        )

        logger.log("Inline prediction completed successfully", "INFO")
        return output

    except Exception as e:
        logger.log(f"Inline prediction failed: {str(e)}", "ERROR", {"error": str(e)})
        raise
