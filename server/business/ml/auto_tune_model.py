#!/usr/bin/env python3
"""
Auto-tune script for hyperparameter search using modular model definitions.
Each model is imported as a module with a Model class providing auto_tune() method.
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
from structured_output import get_logger, emit_result

# Import base utilities
from base import import_model

# Import basic sklearn libraries
from sklearn.model_selection import train_test_split


def auto_tune_regression_model(
    model_name: str,
    input_file: str,
    feature_columns: list,
    target_column: str,
    logger,
    param_grid_dict: dict = None,
):
    """
    Auto-tune a regression model using hyperparameter search.

    Args:
        model_name: Name of the regression model (e.g., "regression.ridge")
        input_file: Path to training data file
        feature_columns: List of feature column names
        target_column: Target column name
        logger: Logger instance for logging progress
        param_grid_dict: Optional custom parameter grid dictionary

    Returns:
        Tuple of (best_params, metrics) where metrics contains train and test scores
    """
    logger.info(f"Starting auto-tune for model: {model_name}")
    logger.info(f"Input file: {input_file}")
    logger.info(f"Feature columns ({len(feature_columns)}): {feature_columns}")
    logger.info(f"Target column: {target_column}")

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

    # Create param grid if provided
    param_grid = None
    if param_grid_dict:
        logger.info(f"Custom parameter grid provided: {param_grid_dict}")
        # Convert dict to ParamGrid model if the model has a ParamGrid class
        if hasattr(Model, "ParamGrid"):
            param_grid = Model.ParamGrid(**param_grid_dict)
        else:
            logger.warning(f"Model {model_name} does not have ParamGrid class, using dict")
            param_grid = param_grid_dict

    # Perform auto-tuning
    logger.info("Starting hyperparameter search...")
    tune_result = Model.auto_tune(X_train, y_train, param_grid=param_grid)

    best_params = tune_result["best_params"]
    logger.info(f"Best parameters found: {best_params}")

    # Get the tuned model
    model = tune_result["model"]

    # Evaluate on training set
    logger.info("Evaluating on training set...")
    train_metrics = Model.evaluate(model, X_train, y_train)
    logger.info(f"Training metrics: {train_metrics}")

    # Evaluate on test set
    logger.info("Evaluating on test set...")
    test_metrics = Model.evaluate(model, X_test, y_test)
    logger.info(f"Test metrics: {test_metrics}")

    # Combine metrics
    metrics = {
        "mse_train": train_metrics.get("mse"),
        "mae_train": train_metrics.get("mae"),
        "r2_train": train_metrics.get("r2"),
        "mse_test": test_metrics.get("mse"),
        "mae_test": test_metrics.get("mae"),
        "r2_test": test_metrics.get("r2"),
    }

    logger.info("Auto-tuning completed successfully")
    return best_params, metrics


def main():
    """Main entry point for the auto-tune script."""
    try:
        # Parse command line arguments
        if len(sys.argv) < 2:
            raise ValueError("Configuration JSON required as argument")

        config = json.loads(sys.argv[1])

        # Extract parameters
        model_name = config.get("model")
        input_file = config.get("inputFile")
        feature_columns = config.get("featureColumns")
        target_column = config.get("targetColumn")
        param_grid_dict = config.get("paramGrid")

        if not all([model_name, input_file, feature_columns, target_column]):
            raise ValueError("Missing required parameters")

        # Get logger
        logger = get_logger()

        # Run auto-tuning
        best_params, metrics = auto_tune_regression_model(
            model_name=model_name,
            input_file=input_file,
            feature_columns=feature_columns,
            target_column=target_column,
            logger=logger,
            param_grid_dict=param_grid_dict,
        )

        # Emit result
        emit_result(
            {
                "params": best_params,
                "metrics": metrics,
            }
        )

    except Exception as e:
        logger = get_logger()
        logger.error(f"Auto-tune failed: {str(e)}")
        emit_result({"error": str(e)}, success=False)
        sys.exit(1)


if __name__ == "__main__":
    main()
