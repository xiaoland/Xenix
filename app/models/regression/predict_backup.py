#!/usr/bin/env python3
"""
Batch prediction script using trained model parameters.
Reads all configuration from stdin JSON (no database interactions).
Outputs structured JSON to stdout.
"""
import json
import sys
import warnings
import pandas as pd
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

# Import structured output utilities
from structured_output import get_logger, emit_log

# Import basic sklearn libraries
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures


def import_model_class(model_name):
    """Lazy import model classes only when needed"""
    if model_name == "Linear_Regression_Hyperparameter_Tuning":
        from sklearn.linear_model import LinearRegression
        return LinearRegression
    elif model_name == "Ridge":
        from sklearn.linear_model import Ridge
        return Ridge
    elif model_name == "Lasso":
        from sklearn.linear_model import Lasso
        return Lasso
    elif model_name == "Bayesian_Ridge_Regression":
        from sklearn.linear_model import BayesianRidge
        return BayesianRidge
    elif model_name == "K-Nearest_Neighbors":
        from sklearn.neighbors import KNeighborsRegressor
        return KNeighborsRegressor
    elif model_name == "Regression_Decision_Tree":
        from sklearn.tree import DecisionTreeRegressor
        return DecisionTreeRegressor
    elif model_name == "Random_Forest":
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor
    elif model_name == "GBDT":
        from sklearn.ensemble import GradientBoostingRegressor
        return GradientBoostingRegressor
    elif model_name == "AdaBoost":
        from sklearn.ensemble import AdaBoostRegressor
        return AdaBoostRegressor
    elif model_name == "XGBoost":
        try:
            from xgboost import XGBRegressor
            return XGBRegressor
        except ImportError:
            raise ImportError("XGBoost is not installed. Please install it with: pip install xgboost")
    elif model_name == "LightGBM":
        try:
            from lightgbm import LGBMRegressor
            return LGBMRegressor
        except ImportError:
            raise ImportError("LightGBM is not installed. Please install it with: pip install lightgbm")
    elif model_name == "Polynomial_Regression":
        from sklearn.linear_model import LinearRegression
        return LinearRegression
    else:
        raise ValueError(f"Unknown model: {model_name}")


def build_model_from_params(model_name, params):
    """Build a model instance with the given parameters"""
    ModelClass = import_model_class(model_name)
    
    # Extract parameters based on model type
    if model_name in ["Linear_Regression_Hyperparameter_Tuning", "Ridge", "Lasso", "Bayesian_Ridge_Regression", "K-Nearest_Neighbors"]:
        # These use pipeline with scaler
        model_params = {k.replace('model__', ''): v for k, v in params.items() if k.startswith('model__')}
        base_model = ModelClass(**model_params) if model_params else ModelClass()
        return Pipeline([
            ("scaler", StandardScaler()),
            ("model", base_model)
        ])
    
    elif model_name == "Polynomial_Regression":
        # Polynomial regression with pipeline
        poly_degree = params.get('poly__degree', 2)
        return Pipeline([
            ("poly", PolynomialFeatures(degree=poly_degree, include_bias=False)),
            ("scaler", StandardScaler()),
            ("model", LinearRegression())
        ])
    
    elif model_name == "AdaBoost":
        # AdaBoost with DecisionTree estimator
        from sklearn.tree import DecisionTreeRegressor
        estimator_depth = params.get('estimator__max_depth', 3)
        ada_params = {k: v for k, v in params.items() if not k.startswith('estimator__')}
        return ModelClass(
            estimator=DecisionTreeRegressor(max_depth=estimator_depth),
            **ada_params
        )
    
    else:
        # Other models (Decision Tree, Random Forest, GBDT, XGBoost, LightGBM)
        return ModelClass(**params)


def main():
    """
    Main function that reads JSON input from stdin.
    Expected JSON structure:
    {
        "trainingDataPath": "/path/to/training_data.xlsx",
        "predictionDataPath": "/path/to/prediction_data.xlsx",
        "outputPath": "/path/to/output.xlsx",
        "model": "Ridge",
        "params": {"model__alpha": 1.0},
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
        training_data_path = input_data.get('trainingDataPath')
        prediction_data_path = input_data.get('predictionDataPath')
        output_path = input_data.get('outputPath')
        model_name = input_data.get('model')
        params = input_data.get('params', {})
        feature_columns = input_data.get('featureColumns')
        target_column = input_data.get('targetColumn')
        
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
        
        logger.info(f"Starting batch prediction using {model_name}")
        logger.info(f"Parameters: {params}")
        
        # Load training data and train model with best parameters
        logger.info(f"Loading training data from {training_data_path}")
        training_df = pd.read_excel(training_data_path)
        logger.info(f"Training data loaded: {len(training_df)} rows")
        
        X_train = training_df[feature_columns]
        y_train = training_df[target_column]
        
        # Build model with tuned parameters
        logger.info(f"Building {model_name} with tuned parameters")
        model = build_model_from_params(model_name, params)
        
        # Train the model
        logger.info("Training model on full training dataset")
        model.fit(X_train, y_train)
        logger.info("Model training completed")
        
        # Load prediction data
        logger.info(f"Loading prediction data from {prediction_data_path}")
        prediction_df = pd.read_excel(prediction_data_path)
        logger.info(f"Prediction data loaded: {len(prediction_df)} rows")
        
        # Make predictions
        logger.info("Generating predictions")
        X_pred = prediction_df[feature_columns]
        predictions = model.predict(X_pred)
        
        # Add predictions to dataframe
        prediction_df['Predicted_Value'] = predictions
        logger.info(f"Predictions generated for {len(predictions)} samples")
        
        # Save results
        logger.info(f"Saving predictions to {output_path}")
        prediction_df.to_excel(output_path, index=False)
        logger.info("Predictions saved successfully")
        
        # Emit success status
        emit_log("info", f"Batch prediction completed successfully! Output saved to {output_path}")
        
        # Output result information
        result_info = {
            "type": "prediction_result",
            "data": {
                "output_path": output_path,
                "num_predictions": len(predictions),
                "model": model_name
            }
        }
        print(json.dumps(result_info), flush=True)
        
    except Exception as e:
        logger.error(f"Error during batch prediction: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
