"""File-based prediction controller"""

import os
import joblib
from datetime import datetime

from ..types import PredictFileInput, PredictFileOutput
from ..services import get_model
from ..utils import read_data, write_predictions
from ..utils.logger import TaskLogger
from ..config import Config


def predict_file(input_data: PredictFileInput, logger: TaskLogger) -> PredictFileOutput:
    """
    File-based prediction with model saving

    Trains model on training data, makes predictions on file data, saves both
    the fitted model and prediction results to files.

    Args:
        input_data: File-based prediction input parameters
        logger: Task logger instance

    Returns:
        File-based prediction output with file paths
    """
    logger.log(f"Starting file-based prediction for model {input_data.model}", "INFO", {
        "model": input_data.model,
        "features": input_data.feature_columns,
        "targets": input_data.target_columns,
        "train_data": input_data.train_data_path
    })

    try:
        # Read training data
        logger.log(f"Reading training data from {input_data.train_data_path}", "INFO")
        train_df = read_data(input_data.train_data_path)
        logger.log(f"Training data loaded: {len(train_df)} rows, {len(train_df.columns)} columns", "INFO")

        # Read prediction data from file
        logger.log(f"Reading prediction data from {input_data.to_predict_data_path}", "INFO")
        predict_df = read_data(input_data.to_predict_data_path)
        logger.log(f"Prediction data loaded: {len(predict_df)} rows", "INFO")

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

        # Save predictions to task directory
        predictions_filename = f"predictions_{timestamp}.xlsx"
        # predictions_path = os.path.join(Config.BASE_PATH, predictions_filename)

        predictions_path = write_predictions(predict_df_with_predictions, predictions_filename)
        logger.log(f"Predictions saved to {predictions_filename}", "INFO")

        # Return output with relative paths
        output = PredictFileOutput(
            fitted_model_path=model_filename,
            predicted_data_path=predictions_path
        )

        logger.log("File-based prediction completed successfully", "INFO")
        return output

    except Exception as e:
        logger.log(f"File-based prediction failed: {str(e)}", "ERROR", {"error": str(e)})
        raise
