#!/usr/bin/env python3
"""
Generic hyperparameter tuning script that works with stdin JSON input.
This script can be used for any regression model with GridSearchCV.
Outputs structured JSON to stdout for the Node.js executor to parse.
No database interactions - all data via stdin/stdout.
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

# Import basic sklearn libraries (always available)
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score


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
        from sklearn.tree import DecisionTreeRegressor
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


def get_model_and_param_grid(model_name):
    """Get model and parameter grid for hyperparameter tuning"""
    
    if model_name == "Linear_Regression_Hyperparameter_Tuning":
        LinearRegression = import_model_class(model_name)
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", LinearRegression())
        ])
        param_grid = {
            'model__fit_intercept': [True, False],
            'model__copy_X': [True, False]
        }
        
    elif model_name == "Ridge":
        Ridge = import_model_class(model_name)
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", Ridge(random_state=42))
        ])
        param_grid = {
            'model__alpha': [0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
        }
        
    elif model_name == "Lasso":
        Lasso = import_model_class(model_name)
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", Lasso(random_state=42))
        ])
        param_grid = {
            'model__alpha': [0.0001, 0.001, 0.01, 0.1, 1.0, 10.0]
        }
        
    elif model_name == "Bayesian_Ridge_Regression":
        BayesianRidge = import_model_class(model_name)
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
        KNeighborsRegressor = import_model_class(model_name)
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", KNeighborsRegressor())
        ])
        param_grid = {
            'model__n_neighbors': [3, 5, 7, 9, 11],
            'model__weights': ['uniform', 'distance']
        }
        
    elif model_name == "Regression_Decision_Tree":
        DecisionTreeRegressor = import_model_class(model_name)
        base_model = DecisionTreeRegressor(random_state=42)
        param_grid = {
            'max_depth': [3, 5, 7, 10, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4]
        }
        
    elif model_name == "Random_Forest":
        RandomForestRegressor = import_model_class(model_name)
        base_model = RandomForestRegressor(random_state=42, n_jobs=-1)
        param_grid = {
            'n_estimators': [50, 100, 200],
            'max_depth': [5, 10, None],
            'min_samples_split': [2, 5]
        }
        
    elif model_name == "GBDT":
        GradientBoostingRegressor = import_model_class(model_name)
        base_model = GradientBoostingRegressor(random_state=42)
        param_grid = {
            'n_estimators': [50, 100, 150],
            'learning_rate': [0.01, 0.1, 0.2],
            'max_depth': [3, 5, 7]
        }
        
    elif model_name == "AdaBoost":
        AdaBoostRegressor = import_model_class(model_name)
        from sklearn.tree import DecisionTreeRegressor
        base_model = AdaBoostRegressor(
            estimator=DecisionTreeRegressor(max_depth=3),
            random_state=42
        )
        param_grid = {
            'n_estimators': [50, 100, 150],
            'learning_rate': [0.01, 0.1, 1.0],
            'estimator__max_depth': [3, 5, 7]
        }
        
    elif model_name == "XGBoost":
        XGBRegressor = import_model_class(model_name)
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
        
    elif model_name == "LightGBM":
        LGBMRegressor = import_model_class(model_name)
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
        LinearRegression = import_model_class(model_name)
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
    """
    Main function that reads JSON input from stdin.
    Expected JSON structure:
    {
        "inputFile": "/path/to/data.xlsx",
        "model": "Ridge",
        "featureColumns": ["col1", "col2", "col3"],
        "targetColumn": "target"
    }
    """
    # Get logger
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
