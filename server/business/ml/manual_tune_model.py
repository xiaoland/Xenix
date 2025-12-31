#!/usr/bin/env python3
"""
Manual tune script for training with specific parameters using modular model definitions.
Each model is imported as a module with a Model class providing manual_tune() method.
Outputs structured JSON to stdout for the Node.js executor to parse.
"""

import json
import sys
import warnings
import pandas as pd
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

# Import structured output utilities
from structured_io import get_logger, emit_result, read_json_input

# Import base utilities
from base import import_model

# Import basic sklearn libraries
from sklearn.model_selection import train_test_split


def manual_tune_regression_model(
    model_name: str,
    input_file: str,
    feature_columns: list,
    target_column: str,
    logger,
    parameters: dict | None = None,
):
    """
    Manual tune a regression model with specific parameters.

    Args:
        model_name: Name of the regression model (e.g., "regression.ridge")
        input_file: Path to training data file
        feature_columns: List of feature column names
        target_column: Target column name
        logger: Logger instance for logging progress
        parameters: Specific parameter values to use

    Returns:
        Tuple of (parameters, metrics) where metrics contains train and test scores
    """
    logger.info(f"Starting manual tune for model: {model_name}")
    logger.info(f"Input file: {input_file}")
    logger.info(f"Feature columns ({len(feature_columns)}): {feature_columns}")
    logger.info(f"Target column: {target_column}")
    logger.info(f"Parameters: {parameters}")

    # Load data
    logger.info("Loading data...")
    df = pd.read_excel(input_file, engine="openpyxl")
    logger.info(f"Data loaded. Shape: {df.shape}")

    # Prepare features and target
    X = df[feature_columns]
    y = df[target_column]

    # Split data
    logger.info("Splitting data into train/test sets...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    logger.info(f"Training set size: {len(X_train)}, Test set size: {len(X_test)}")

    # Import model class
    logger.info(f"Importing model: {model_name}")
    Model = import_model(model_name)

    # Create params model if provided
    params = None
    if parameters:
        # Convert dict to Params model if the model has a Params class
        params = Model.__modelparam__(**parameters)

    # Perform manual tuning using the manual_tune method from base class
    logger.info("Training model with specified parameters using manual_tune method...")
    result = Model.manual_tune(X_train, y_train, X_test, y_test, params=params)

    logger.info("Manual tuning completed successfully")
    return parameters or {}, result["metrics"]


def main():
    """Main entry point for the manual tune script."""
    try:
        # Read JSON configuration from stdin
        config = read_json_input()

        # Extract parameters
        model_name = config.get("model")
        input_file = config.get("inputFile")
        feature_columns = config.get("featureColumns")
        target_column = config.get("targetColumn")
        parameters = config.get("parameters")

        if not all([model_name, input_file, feature_columns, target_column]):
            raise ValueError("Missing required parameters")

        # Get logger
        logger = get_logger()

        # Run manual tuning
        params, metrics = manual_tune_regression_model(
            model_name=model_name,
            input_file=input_file,
            feature_columns=feature_columns,
            target_column=target_column,
            logger=logger,
            parameters=parameters,
        )

        # Emit result
        emit_result(
            {
                "params": params,
                "metrics": metrics,
            }
        )

    except Exception as e:
        logger = get_logger()
        logger.error(f"Manual tune failed: {str(e)}")
        emit_result({"error": str(e)}, success=False)
        sys.exit(1)


if __name__ == "__main__":
    main()
