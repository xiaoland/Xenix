#!/usr/bin/env python3
"""
JSON-based inline prediction script using modular model definitions.
Takes training data from Excel file and prediction data as JSON array.
Returns predictions as JSON array (no file output).
Reads all configuration from stdin JSON (no database interactions).
Outputs structured JSON to stdout.
"""

import sys
import warnings
import pandas as pd
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

# Import structured output utilities
from structured_io import (
    get_logger,
    emit_log,
    read_json_input,
    emit_json_output,
)

# Import helper functions
from predict_helpers import load_and_train_model, predict_on_dataframe


def predict_on_json(
    model_name: str,
    training_data_path: str,
    prediction_data: list,
    params: dict,
    feature_columns: list,
    target_column: str,
    logger,
):
    """
    Perform JSON-based inline prediction using a trained model.

    Args:
        model_name: Name of the model (e.g., "regression.ridge")
        training_data_path: Path to training data Excel file
        prediction_data: List of dictionaries containing prediction data
        params: Model parameters
        feature_columns: List of feature column names
        target_column: Target column name
        logger: Logger instance for logging progress

    Returns:
        List of predictions
    """
    # Load training data and train model
    model, Model = load_and_train_model(
        model_name,
        training_data_path,
        feature_columns,
        target_column,
        params,
        logger,
    )

    # Convert prediction data JSON to DataFrame
    logger.info("Converting prediction data JSON to DataFrame")
    prediction_df = pd.DataFrame(prediction_data)
    logger.info(f"Prediction data converted: {len(prediction_df)} rows")

    # Validate that all feature columns are present
    missing_columns = set(feature_columns) - set(prediction_df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing feature columns in prediction data: {missing_columns}"
        )

    # Make predictions
    predictions = predict_on_dataframe(
        model, Model, prediction_df, feature_columns, logger
    )

    # Convert predictions to list
    predictions_list = predictions.tolist()
    logger.info(f"Returning {len(predictions_list)} predictions as JSON array")

    return predictions_list


def main():
    """
    Main function that reads JSON input from stdin.
    Expected JSON structure:
    {
        "trainingDataPath": "/path/to/training_data.xlsx",
        "predictionData": [
            {"col1": 1.0, "col2": 2.0, "col3": 3.0},
            {"col1": 4.0, "col2": 5.0, "col3": 6.0}
        ],
        "model": "regression.ridge",
        "params": {"model__alpha": 1.0},
        "featureColumns": ["col1", "col2", "col3"],
        "targetColumn": "target"
    }
    """
    logger = get_logger(__name__)

    try:
        # Read input from stdin
        logger.info("Reading input configuration from stdin")
        input_data = read_json_input()

        # Extract parameters
        training_data_path = input_data.get("trainingDataPath")
        prediction_data = input_data.get("predictionData")
        model_name = input_data.get("model")
        params = input_data.get("params", {})
        feature_columns = input_data.get("featureColumns")
        target_column = input_data.get("targetColumn")

        # Validate required parameters
        if not training_data_path:
            raise ValueError("trainingDataPath is required")
        if not prediction_data:
            raise ValueError("predictionData is required")
        if not isinstance(prediction_data, list):
            raise ValueError("predictionData must be an array")
        if not model_name:
            raise ValueError("model is required")
        if not feature_columns:
            raise ValueError("featureColumns is required")
        if not target_column:
            raise ValueError("targetColumn is required")

        logger.info(f"Starting JSON-based prediction using {model_name}")
        logger.info(f"Parameters: {params}")
        logger.info(f"Prediction data rows: {len(prediction_data)}")

        # Perform prediction
        predictions = predict_on_json(
            model_name,
            training_data_path,
            prediction_data,
            params,
            feature_columns,
            target_column,
            logger,
        )

        # Emit success log
        emit_log(
            f"JSON-based prediction completed successfully! Generated {len(predictions)} predictions"
        )

        # Output result information with predictions
        result_data = {
            "type": "result",
            "data": {
                "predictions": predictions,
                "model": model_name,
                "numPredictions": len(predictions),
            },
        }
        emit_json_output(result_data)

    except Exception as e:
        logger.error(f"Error during JSON-based prediction: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
