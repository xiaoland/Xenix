#!/usr/bin/env python3
"""
File-based prediction script using modular model definitions.
Takes Excel files as input for training and prediction data, outputs predictions to Excel file.
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


def predict_on_file(
    model_name: str,
    training_data_path: str,
    prediction_data_path: str,
    output_path: str,
    params: dict,
    feature_columns: list,
    target_column: str,
    logger,
):
    """
    Perform file-based prediction using a trained model.

    Args:
        model_name: Name of the model (e.g., "regression.ridge")
        training_data_path: Path to training data Excel file
        prediction_data_path: Path to prediction data Excel file
        output_path: Path to save predictions Excel file
        params: Model parameters
        feature_columns: List of feature column names
        target_column: Target column name
        logger: Logger instance for logging progress

    Returns:
        Tuple of (output_path, num_predictions)
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

    # Load prediction data
    logger.info(f"Loading prediction data from {prediction_data_path}")
    prediction_df = pd.read_excel(prediction_data_path)
    logger.info(f"Prediction data loaded: {len(prediction_df)} rows")

    # Make predictions
    predictions = predict_on_dataframe(
        model, Model, prediction_df, feature_columns, logger
    )

    # Add predictions to dataframe
    prediction_df["Predicted_Value"] = predictions.values

    # Save results
    logger.info(f"Saving predictions to {output_path}")
    prediction_df.to_excel(output_path, index=False)
    logger.info("Predictions saved successfully")

    return output_path, len(predictions)


def main():
    """
    Main function that reads JSON input from stdin.
    Expected JSON structure:
    {
        "trainingDataPath": "/path/to/training_data.xlsx",
        "predictionDataPath": "/path/to/prediction_data.xlsx",
        "outputPath": "/path/to/output.xlsx",
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
        prediction_data_path = input_data.get("predictionDataPath")
        output_path = input_data.get("outputPath")
        model_name = input_data.get("model")
        params = input_data.get("params", {})
        feature_columns = input_data.get("featureColumns")
        target_column = input_data.get("targetColumn")

        # Validate required parameters
        if not training_data_path:
            raise ValueError("trainingDataPath is required")
        if not prediction_data_path:
            raise ValueError("predictionDataPath is required")
        if not output_path:
            raise ValueError("outputPath is required")
        if not model_name:
            raise ValueError("model is required")
        if not feature_columns:
            raise ValueError("featureColumns is required")
        if not target_column:
            raise ValueError("targetColumn is required")

        logger.info(f"Starting file-based prediction using {model_name}")
        logger.info(f"Parameters: {params}")

        # Perform prediction
        output_path, num_predictions = predict_on_file(
            model_name,
            training_data_path,
            prediction_data_path,
            output_path,
            params,
            feature_columns,
            target_column,
            logger,
        )

        # Emit success log
        emit_log(
            f"File-based prediction completed successfully! Output saved to {output_path}"
        )

        # Output result information
        result_data = {
            "type": "result",
            "data": {
                "outputPath": output_path,
                "numPredictions": num_predictions,
                "model": model_name,
            },
        }
        emit_json_output(result_data)

    except Exception as e:
        logger.error(f"Error during file-based prediction: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
