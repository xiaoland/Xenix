#!/usr/bin/env python3
"""
Batch prediction script using the best model from hyperparameter tuning.
This script loads the trained model parameters from database, trains the model on training data,
and makes predictions on new data.
"""
import argparse
import json
import os
import sys
import warnings
import pandas as pd
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")

# Add parent directory to path to import from other modules
sys.path.append(str(Path(__file__).parent))

# Import basic ML libraries
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression, Ridge, Lasso, BayesianRidge
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, AdaBoostRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures

# Import optional libraries with error handling
try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    
try:
    from lightgbm import LGBMRegressor
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False


def load_params_from_db(task_id):
    """Load parameters from database"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Get database URL from environment
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("⚠️ DATABASE_URL not set, using default parameters", file=sys.stderr)
            return {}
        
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query model_results table for parameters
        cursor.execute(
            "SELECT params FROM model_results WHERE task_id = %s LIMIT 1",
            (task_id,)
        )
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result and result['params']:
            return result['params']
        return {}
    except Exception as e:
        print(f"⚠️ Failed to load params from database: {e}", file=sys.stderr)
        return {}


def add_prefix_for_pipeline(params, prefix="model"):
    """Add model__ prefix for pipeline parameters"""
    if not params:
        return params
    new_params = {}
    for k, v in params.items():
        if "__" not in k:
            new_params[f"{prefix}__{k}"] = v
        else:
            new_params[k] = v
    return new_params


def build_model(model_name, params):
    """Build a model based on name and parameters"""
    
    if model_name == "LinearRegression" or model_name == "Linear_Regression_Hyperparameter_Tuning":
        params = add_prefix_for_pipeline(params)
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", LinearRegression())
        ])
        model.set_params(**params)
        
    elif model_name == "Ridge":
        params = add_prefix_for_pipeline(params)
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", Ridge(random_state=42))
        ])
        model.set_params(**params)
        
    elif model_name == "Lasso":
        params = add_prefix_for_pipeline(params)
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", Lasso(random_state=42))
        ])
        model.set_params(**params)
        
    elif model_name == "BayesianRidge" or model_name == "Bayesian_Ridge_Regression":
        params = add_prefix_for_pipeline(params)
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", BayesianRidge())
        ])
        model.set_params(**params)
        
    elif model_name == "KNN" or model_name == "K-Nearest_Neighbors":
        params = add_prefix_for_pipeline(params)
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", KNeighborsRegressor())
        ])
        model.set_params(**params)
        
    elif model_name == "DecisionTree" or model_name == "Regression_Decision_Tree":
        model = DecisionTreeRegressor(**params, random_state=42)
        
    elif model_name == "RandomForest" or model_name == "Random_Forest":
        model = RandomForestRegressor(**params, random_state=42, n_jobs=-1)
        
    elif model_name == "GBDT":
        model = GradientBoostingRegressor(**params, random_state=42)
        
    elif model_name == "AdaBoost":
        tree_params = {}
        ada_params_clean = {}
        for k, v in params.items():
            if k.startswith("estimator__"):
                tree_params[k.replace("estimator__", "")] = v
            else:
                ada_params_clean[k] = v
        model = AdaBoostRegressor(
            estimator=DecisionTreeRegressor(**tree_params),
            **ada_params_clean,
            random_state=42
        )
        
    elif model_name == "XGBoost":
        if not XGBOOST_AVAILABLE:
            raise ValueError("XGBoost is not installed. Please install it with: pip install xgboost")
        model = XGBRegressor(
            **params,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=-1
        )
        
    elif model_name == "LightGBM":
        if not LIGHTGBM_AVAILABLE:
            raise ValueError("LightGBM is not installed. Please install it with: pip install lightgbm")
        model = LGBMRegressor(
            **params,
            objective="regression",
            random_state=42,
            n_jobs=-1,
            verbose=-1,
            verbosity=-1,
            silent=True
        )
        
    elif model_name == "PolynomialRegression" or model_name == "Polynomial_Regression":
        degree = params.get("degree", 2)
        model = Pipeline([
            ("poly", PolynomialFeatures(degree=degree, include_bias=False)),
            ("scaler", StandardScaler()),
            ("model", LinearRegression())
        ])
        
    else:
        raise ValueError(f"Unknown model: {model_name}")
    
    return model


def main():
    parser = argparse.ArgumentParser(description='Batch prediction using trained model')
    parser.add_argument('--input', required=True, help='Input Excel file for prediction')
    parser.add_argument('--output', required=True, help='Output Excel file with predictions')
    parser.add_argument('--model', required=True, help='Model name to use')
    parser.add_argument('--task-id', required=True, help='Task ID from tuning to load parameters')
    parser.add_argument('--training-data', required=True, help='Training data file path')
    
    args = parser.parse_args()
    
    try:
        print(f"Starting prediction with model: {args.model}")
        
        # Load model parameters from database using task ID
        print(f"Loading parameters from database for task: {args.task_id}")
        params = load_params_from_db(args.task_id)
        
        if not params:
            print(f"⚠️ No parameters found in database for task {args.task_id}, using default parameters")
            params = {}
        else:
            print(f"Loaded parameters: {params}")
        
        # Load training data
        print(f"Loading training data from {args.training_data}")
        if not os.path.exists(args.training_data):
            raise FileNotFoundError(f"Training data file not found: {args.training_data}")
        
        df = pd.read_excel(args.training_data)
        print(f"Training data loaded: {len(df)} rows")
        
        # Import configuration
        from config import FEATURE_COLUMNS, TARGET_COLUMN, PREDICTION_COLUMN
        
        # Define features and target
        X = df[FEATURE_COLUMNS]
        y = df[TARGET_COLUMN]
        
        # Build and train model on ALL data
        print(f"Training {args.model} on all data...")
        model = build_model(args.model, params)
        model.fit(X, y)
        print("Model training completed")
        
        # Load prediction data
        print(f"Loading prediction data from {args.input}")
        if not os.path.exists(args.input):
            raise FileNotFoundError(f"Prediction data file not found: {args.input}")
        
        pred_df = pd.read_excel(args.input)
        print(f"Prediction data loaded: {len(pred_df)} rows")
        
        # Extract features
        X_pred = pred_df[FEATURE_COLUMNS]
        
        # Make predictions
        print("Making predictions...")
        y_pred = model.predict(X_pred)
        
        # Add predictions to dataframe
        pred_df[PREDICTION_COLUMN] = y_pred
        
        # Save output
        print(f"Saving predictions to {args.output}")
        pred_df.to_excel(args.output, index=False)
        
        print("✅ Prediction completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during prediction: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
