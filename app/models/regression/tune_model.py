#!/usr/bin/env python3
"""
Generic hyperparameter tuning script that works with CLI arguments.
This script can be used for any regression model with GridSearchCV.
Outputs structured JSON to stdout for the Node.js executor to parse.
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

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

# Import structured output utilities
from structured_output import get_logger, emit_result

# Import ML libraries
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.linear_model import LinearRegression, Ridge, Lasso, BayesianRidge
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, AdaBoostRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("Warning: XGBoost not available. XGBoost model will be skipped.", file=sys.stderr)

try:
    from lightgbm import LGBMRegressor
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False
    print("Warning: LightGBM not available. LightGBM model will be skipped.", file=sys.stderr)


def get_model_and_param_grid(model_name):
    """Get model and parameter grid for hyperparameter tuning"""
    
    if model_name == "Linear_Regression_Hyperparameter_Tuning":
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", LinearRegression())
        ])
        param_grid = {
            "model__fit_intercept": [True, False]
        }
        
    elif model_name == "Ridge":
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", Ridge(random_state=42))
        ])
        param_grid = {
            'model__alpha': [0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
        }
        
    elif model_name == "Lasso":
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", Lasso(random_state=42))
        ])
        param_grid = {
            'model__alpha': [0.0001, 0.001, 0.01, 0.1, 1.0, 10.0]
        }
        
    elif model_name == "Bayesian_Ridge_Regression":
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", BayesianRidge())
        ])
        param_grid = {
            'model__alpha_1': [1e-6, 1e-5, 1e-4],
            'model__alpha_2': [1e-6, 1e-5, 1e-4],
            'model__lambda_1': [1e-6, 1e-5, 1e-4],
            'model__lambda_2': [1e-6, 1e-5, 1e-4]
        }
        
    elif model_name == "K-Nearest_Neighbors":
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", KNeighborsRegressor())
        ])
        param_grid = {
            'model__n_neighbors': [3, 5, 7, 9, 11],
            'model__weights': ['uniform', 'distance']
        }
        
    elif model_name == "Regression_Decision_Tree":
        base_model = DecisionTreeRegressor(random_state=42)
        param_grid = {
            'max_depth': [3, 5, 7, 10, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4]
        }
        
    elif model_name == "Random_Forest":
        base_model = RandomForestRegressor(random_state=42, n_jobs=-1)
        param_grid = {
            'n_estimators': [50, 100, 200],
            'max_depth': [5, 10, None],
            'min_samples_split': [2, 5]
        }
        
    elif model_name == "GBDT":
        base_model = GradientBoostingRegressor(random_state=42)
        param_grid = {
            'n_estimators': [50, 100, 150],
            'learning_rate': [0.01, 0.1, 0.2],
            'max_depth': [3, 5, 7]
        }
        
    elif model_name == "AdaBoost":
        base_model = AdaBoostRegressor(
            estimator=DecisionTreeRegressor(max_depth=3),
            random_state=42
        )
        param_grid = {
            'n_estimators': [50, 100, 150],
            'learning_rate': [0.01, 0.1, 1.0],
            'estimator__max_depth': [3, 5, 7]
        }
        
    elif model_name == "XGBoost" and HAS_XGB:
        base_model = XGBRegressor(
            objective="reg:squarederror",
            random_state=42,
            n_jobs=-1
        )
        param_grid = {
            'n_estimators': [50, 100, 150],
            'learning_rate': [0.01, 0.1, 0.2],
            'max_depth': [3, 5, 7]
        }
        
    elif model_name == "LightGBM" and HAS_LGBM:
        base_model = LGBMRegressor(
            objective="regression",
            random_state=42,
            n_jobs=-1,
            verbose=-1,
            verbosity=-1
        )
        param_grid = {
            'n_estimators': [50, 100, 150],
            'learning_rate': [0.01, 0.1, 0.2],
            'max_depth': [3, 5, 7]
        }
        
    elif model_name == "Polynomial_Regression":
        base_model = Pipeline([
            ("poly", PolynomialFeatures(degree=2, include_bias=False)),
            ("scaler", StandardScaler()),
            ("model", LinearRegression())
        ])
        param_grid = {
            'poly__degree': [2, 3, 4]
        }
        
    else:
        raise ValueError(f"Unknown model: {model_name}")
    
    return base_model, param_grid


def main():
    parser = argparse.ArgumentParser(description='Hyperparameter tuning for regression models')
    parser.add_argument('--input', required=True, help='Input Excel file path')
    parser.add_argument('--output-db', required=False, help='Task ID for database output (deprecated)')
    parser.add_argument('--model', required=False, help='Model name (optional, can be inferred from script)')
    
    args = parser.parse_args()
    
    # Infer model name from script name if not provided
    if args.model:
        model_name = args.model
    else:
        # Get model name from the calling script or default
        model_name = os.environ.get('MODEL_NAME', 'Linear_Regression_Hyperparameter_Tuning')
    
    # Get logger
    logger = get_logger(__name__)
    
    try:
        logger.info(f"Starting hyperparameter tuning for {model_name}")
        
        # Load data
        logger.info(f"Loading training data from {args.input}")
        df = pd.read_excel(args.input)
        logger.info(f"Data loaded: {len(df)} rows, {len(df.columns)} columns")
        
        # Import configuration
        from config import FEATURE_COLUMNS, TARGET_COLUMN
        
        # Define features and target
        X = df[FEATURE_COLUMNS]
        y = df[TARGET_COLUMN]
        logger.info(f"Features: {FEATURE_COLUMNS}")
        logger.info(f"Target: {TARGET_COLUMN}")
        
        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        logger.info(f"Train set: {len(X_train)} samples, Test set: {len(X_test)} samples")
        
        # Get model and parameter grid
        logger.info(f"Setting up {model_name} for hyperparameter tuning")
        base_model, param_grid = get_model_and_param_grid(model_name)
        logger.info(f"Parameter grid: {param_grid}")
        
        # Grid search
        logger.info("Starting GridSearchCV with 5-fold cross-validation")
        grid_search = GridSearchCV(
            estimator=base_model,
            param_grid=param_grid,
            cv=5,
            scoring='neg_mean_squared_error',
            n_jobs=-1
        )
        
        grid_search.fit(X_train, y_train)
        logger.info("GridSearchCV completed")
        
        # Best parameters
        best_params = grid_search.best_params_
        logger.info(f"Best parameters found: {best_params}")
        logger.info(f"Best CV score: {grid_search.best_score_}")
        
        # Evaluate on train and test
        logger.info("Evaluating best model on train and test sets")
        best_model = grid_search.best_estimator_
        
        y_train_pred = best_model.predict(X_train)
        y_test_pred = best_model.predict(X_test)
        
        metrics = {
            'mse_train': float(mean_squared_error(y_train, y_train_pred)),
            'mae_train': float(mean_absolute_error(y_train, y_train_pred)),
            'r2_train': float(r2_score(y_train, y_train_pred)),
            'mse_test': float(mean_squared_error(y_test, y_test_pred)),
            'mae_test': float(mean_absolute_error(y_test, y_test_pred)),
            'r2_test': float(r2_score(y_test, y_test_pred))
        }
        
        logger.info("Model evaluation completed")
        for key, value in metrics.items():
            logger.info(f"  {key}: {value:.4f}")
        
        # Save parameters to JSON
        json_filename = f"{model_name}_Params.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(best_params, f, indent=4)
        logger.info(f"Parameters saved to {json_filename}")
        
        # Emit result as structured JSON
        emit_result(model_name, best_params, metrics)
        
        logger.info("Hyperparameter tuning completed successfully!")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error during tuning: {error_msg}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
