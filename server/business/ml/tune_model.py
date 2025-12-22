#!/usr/bin/env python3
"""
Generic hyperparameter tuning script using modular model definitions.
Each model is imported as a module with a Model class providing tune(), evaluate(), and predict() methods.
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


def main():
    """
    Main function that reads JSON input from stdin.
    Expected JSON structure:
    {
        "inputFile": "/path/to/data.xlsx",
        "model": "ridge",
        "featureColumns": ["col1", "col2", "col3"],
        "targetColumn": "target"
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
        
        # Validate required parameters
        if not input_file:
            raise ValueError("inputFile is required")
        if not model_name:
            raise ValueError("model is required")
        if not feature_columns:
            raise ValueError("featureColumns is required")
        if not target_column:
            raise ValueError("targetColumn is required")
        
        logger.info(f"Starting hyperparameter tuning for {model_name}")
        
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
        logger.info(f"Importing model for {model_name}")
        Model = import_model(model_name)
        
        # Define progress callback
        def progress_callback(percentage: float, round: int, total_rounds: int, metrics: dict, params: dict) -> None:
            """Log progress during hyperparameter tuning"""
            logger.info(f"Progress: {percentage:.1f}% - Round {round}/{total_rounds}")
            if metrics:
                logger.info(f"  Current metrics: {metrics}")
            if params:
                logger.info(f"  Current params: {params}")
        
        # Perform hyperparameter tuning using the model's tune function
        logger.info(f"Starting hyperparameter tuning with GridSearchCV")
        tune_result = Model.tune(X_train, y_train, progress_callback=progress_callback)
        
        best_params = tune_result['best_params']
        best_model = tune_result['model']
        logger.info(f"Best parameters found: {best_params}")
        logger.info(f"Best CV score: {tune_result['best_score']}")
        
        # Evaluate on train and test sets using the model's evaluate function
        logger.info("Evaluating best model on train and test sets")
        train_metrics = Model.evaluate(best_model, X_train, y_train)
        test_metrics = Model.evaluate(best_model, X_test, y_test)
        
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
        
        # Emit result as structured JSON
        emit_result(model_name, best_params, metrics)
        
        logger.info("Hyperparameter tuning completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during hyperparameter tuning: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
