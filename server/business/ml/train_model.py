#!/usr/bin/env python3
"""
Training script for machine learning models with specific parameters.
Each model is imported as a module with a Model class providing train(), evaluate(), and predict() methods.
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


def train_regression_model(model_name: str, input_file: str, feature_columns: list, target_column: str, logger, parameters: dict):
    """
    Train a regression model with specific parameters.
    
    Args:
        model_name: Name of the regression model (e.g., "regression.ridge")
        input_file: Path to training data file
        feature_columns: List of feature column names
        target_column: Target column name
        logger: Logger instance for logging progress
        parameters: Dictionary of specific parameters to use for training
        
    Returns:
        Tuple of (parameters, metrics) where metrics contains train and test scores
    """
    # Load data
    logger.info(f"Loading training data from {input_file}")
    df = pd.read_excel(input_file)
    logger.info(f"Data loaded: {len(df)} rows, {len(df.columns)} columns")
    
    # Define features and target
    X = df[feature_columns]
    y = df[target_column]
    logger.info(f"Features: {feature_columns}")
    logger.info(f"Target: {target_column}")
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    logger.info(f"Train set: {len(X_train)} samples, Test set: {len(X_test)} samples")
    
    # Import Model class directly
    logger.info(f"Importing regression model for {model_name}")
    Model = import_model(model_name)
    
    # Train model with specific parameters
    logger.info(f"Training model with parameters: {parameters}")
    
    # Create model instance with parameters using the model's create_model method
    model_instance = Model.create_model(parameters)
    
    # Fit the model
    logger.info("Fitting model to training data")
    model_instance.fit(X_train, y_train)
    logger.info("Model training completed")
    
    # Evaluate on train and test sets using the model's evaluate function
    logger.info("Evaluating model on train and test sets")
    train_metrics = Model.evaluate(model_instance, X_train, y_train)
    test_metrics = Model.evaluate(model_instance, X_test, y_test)
    
    # Combine metrics
    metrics = {
        'mse_train': train_metrics['mse'],
        'mae_train': train_metrics['mae'],
        'r2_train': train_metrics['r2'],
        'mse_test': test_metrics['mse'],
        'mae_test': test_metrics['mae'],
        'r2_test': test_metrics['r2']
    }
    
    logger.info("Model evaluation completed")
    for key, value in metrics.items():
        logger.info(f"  {key}: {value:.4f}")
    
    return parameters, metrics


def main():
    """
    Main function that reads JSON input from stdin.
    Expected JSON structure:
    {
        "inputFile": "/path/to/data.xlsx",
        "model": "ridge",
        "featureColumns": ["col1", "col2", "col3"],
        "targetColumn": "target",
        "parameters": {"alpha": 1.0, "fit_intercept": true}
    }
    """
    logger = get_logger(__name__)
    
    try:
        # Read input from stdin
        logger.info("Reading input configuration from stdin")
        input_data = json.loads(sys.stdin.read())
        
        # Extract parameters
        input_file = input_data.get('inputFile')
        model_name = input_data.get('model')
        feature_columns = input_data.get('featureColumns')
        target_column = input_data.get('targetColumn')
        parameters = input_data.get('parameters')  # Required specific parameters
        
        # Validate required parameters
        if not input_file:
            raise ValueError("inputFile is required")
        if not model_name:
            raise ValueError("model is required")
        if not feature_columns:
            raise ValueError("featureColumns is required")
        if not target_column:
            raise ValueError("targetColumn is required")
        if not parameters:
            raise ValueError("parameters is required")
        
        logger.info(f"Starting training for {model_name}")
        
        # Determine model type and call appropriate training function
        if model_name.startswith('regression.'):
            params, metrics = train_regression_model(
                model_name, input_file, feature_columns, target_column, logger, parameters
            )
        # Future: Add support for other model types
        # elif model_name.startswith('classification.'):
        #     params, metrics = train_classification_model(...)
        # elif model_name.startswith('association.'):
        #     params, metrics = train_association_model(...)
        else:
            raise ValueError(f"Unknown model type for '{model_name}'. Model name should start with 'regression.', 'classification.', etc.")
        
        # Emit result as structured JSON
        emit_result(model_name, params, metrics)
        
        logger.info("Training completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during training: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
