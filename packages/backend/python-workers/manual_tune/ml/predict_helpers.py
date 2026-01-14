#!/usr/bin/env python3
"""
Shared helper functions for prediction functionality.
"""

import pandas as pd
from base import import_model


def load_and_train_model(
    model_name: str,
    training_data_path: str,
    feature_columns: list,
    target_column: str,
    params: dict,
    logger,
):
    """
    Load training data and train a model with given parameters.

    Args:
        model_name: Name of the model (e.g., "regression.ridge")
        training_data_path: Path to training data file
        feature_columns: List of feature column names
        target_column: Target column name
        params: Model parameters
        logger: Logger instance for logging progress

    Returns:
        Tuple of (trained_model, Model_class)
    """
    # Import Model class
    logger.info(f"Importing model: {model_name}")
    Model = import_model(model_name)

    # Load training data
    logger.info(f"Loading training data from {training_data_path}")
    training_df = pd.read_excel(training_data_path)
    logger.info(f"Training data loaded: {len(training_df)} rows")

    X_train = training_df[feature_columns]
    y_train = training_df[target_column]

    # Create model with parameters
    logger.info(f"Creating {model_name} with parameters: {params}")
    params_model = Model.__modelparam__.model_validate(params)
    model = Model.create_model(params_model)

    # Train the model
    logger.info("Training model on full training dataset")
    model.fit(X_train, y_train)
    logger.info("Model training completed")

    return model, Model


def predict_on_dataframe(model, Model, df: pd.DataFrame, feature_columns: list, logger):
    """
    Make predictions on a dataframe using a trained model.

    Args:
        model: Trained model instance
        Model: Model class with predict method
        df: DataFrame to make predictions on
        feature_columns: List of feature column names
        logger: Logger instance for logging progress

    Returns:
        Array of predictions
    """
    logger.info(f"Making predictions on {len(df)} rows")
    X_pred = df[feature_columns]
    predictions = Model.predict(model, X_pred)
    logger.info(f"Predictions generated for {len(predictions)} samples")
    return predictions
