#!/usr/bin/env python3
"""
Model comparison script that loads parameters from JSON files and compares models.
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
from structured_output import get_logger, emit_comparison_result

# Import ML libraries
from sklearn.model_selection import train_test_split
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


def load_params_from_db(task_id, logger=None):
    """Load params from database using task ID"""
    if not task_id:
        return {}
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Get database URL from environment
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            if logger:
                logger.warning("DATABASE_URL not set, using default params")
            return {}
        
        # Connect and query
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(
            "SELECT params FROM model_results WHERE task_id = %s ORDER BY created_at DESC LIMIT 1",
            (task_id,)
        )
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result and result['params']:
            return result['params']
        else:
            if logger:
                logger.info(f"No params found in DB for task {task_id}, using defaults")
            return {}
    except Exception as e:
        if logger:
            logger.warning(f"Failed to load params from DB for task {task_id}: {e}")
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


def main():
    parser = argparse.ArgumentParser(description='Compare regression models')
    parser.add_argument('--input', required=True, 
                       help='Input Excel file path')
    parser.add_argument('--models', required=True,
                       help='Comma-separated list of models to compare')
    parser.add_argument('--task-ids', required=False, default='',
                       help='Comma-separated model=taskId mappings (e.g., Ridge=task_001,Lasso=task_002)')
    parser.add_argument('--output-db', required=False, help='Task ID for database output (deprecated)')
    
    args = parser.parse_args()
    
    # Parse models list
    models_to_compare = [m.strip() for m in args.models.split(',') if m.strip()]
    
    # Parse task IDs mapping
    task_id_map = {}
    if args.task_ids:
        for mapping in args.task_ids.split(','):
            if '=' in mapping:
                model_name, task_id = mapping.split('=', 1)
                task_id_map[model_name.strip()] = task_id.strip()
    
    # Get logger
    logger = get_logger(__name__)
    
    try:
        logger.info(f"Starting model comparison for models: {', '.join(models_to_compare)}")
        
        # Load parameters from database using task IDs
        logger.info("Loading model parameters from database")
        model_params = {}
        for model_name in models_to_compare:
            task_id = task_id_map.get(model_name)
            if task_id:
                logger.info(f"Loading params for {model_name} from task {task_id}")
                params = load_params_from_db(task_id, logger)
            else:
                logger.info(f"No task ID provided for {model_name}, using default params")
                params = {}
            model_params[model_name] = params
        
        # Read data
        logger.info(f"Loading training data from {args.input}")
        df = pd.read_excel(args.input)
        logger.info(f"Data loaded: {len(df)} rows")
        
        # Import configuration
        from config import FEATURE_COLUMNS, TARGET_COLUMN
        
        X = df[FEATURE_COLUMNS]
        y = df[TARGET_COLUMN]
        
        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Build models (only for selected models)
        models = {}
        
        for model_name in models_to_compare:
            params = model_params.get(model_name, {})
            
            if model_name == "Linear_Regression_Hyperparameter_Tuning" or model_name == "LinearRegression":
                params_pipeline = add_prefix_for_pipeline(params)
                lin_model = Pipeline([
                    ("scaler", StandardScaler()),
                    ("model", LinearRegression())
                ])
                lin_model.set_params(**params_pipeline)
                models["LinearRegression"] = lin_model
            
            elif model_name == "Ridge":
                params_pipeline = add_prefix_for_pipeline(params)
                ridge_model = Pipeline([
                    ("scaler", StandardScaler()),
                    ("model", Ridge(random_state=42))
                ])
                ridge_model.set_params(**params_pipeline)
                models["Ridge"] = ridge_model
            
            elif model_name == "Lasso":
                params_pipeline = add_prefix_for_pipeline(params)
                lasso_model = Pipeline([
                    ("scaler", StandardScaler()),
                    ("model", Lasso(random_state=42))
                ])
                lasso_model.set_params(**params_pipeline)
                models["Lasso"] = lasso_model
            
            elif model_name == "Bayesian_Ridge_Regression" or model_name == "BayesianRidge":
                params_pipeline = add_prefix_for_pipeline(params)
                bayes_model = Pipeline([
                    ("scaler", StandardScaler()),
                    ("model", BayesianRidge())
                ])
                bayes_model.set_params(**params_pipeline)
                models["BayesianRidge"] = bayes_model
            
            elif model_name == "K-Nearest_Neighbors" or model_name == "KNN":
                params_pipeline = add_prefix_for_pipeline(params)
                knn_model = Pipeline([
                    ("scaler", StandardScaler()),
                    ("model", KNeighborsRegressor())
                ])
                knn_model.set_params(**params_pipeline)
                models["KNN"] = knn_model
            
            elif model_name == "Regression_Decision_Tree" or model_name == "DecisionTree":
                models["DecisionTree"] = DecisionTreeRegressor(
                    **params,
                    random_state=42
                )
            
            elif model_name == "Random_Forest" or model_name == "RandomForest":
                models["RandomForest"] = RandomForestRegressor(
                    **params,
                    random_state=42,
                    n_jobs=-1
                )
            
            elif model_name == "GBDT":
                models["GBDT"] = GradientBoostingRegressor(
                    **params,
                    random_state=42
                )
            
            elif model_name == "AdaBoost":
                tree_params = {}
                ada_params_clean = {}
                
                for k, v in params.items():
                    if k.startswith("estimator__"):
                        tree_params[k.replace("estimator__", "")] = v
                    else:
                        ada_params_clean[k] = v
                
                models["AdaBoost"] = AdaBoostRegressor(
                    estimator=DecisionTreeRegressor(**tree_params) if tree_params else None,
                    **ada_params_clean,
                    random_state=42
                )
            
            elif model_name == "XGBoost" and HAS_XGB:
                models["XGBoost"] = XGBRegressor(
                    **params,
                    objective="reg:squarederror",
                    random_state=42,
                    n_jobs=-1
                )
            
            elif model_name == "LightGBM" and HAS_LGBM:
                models["LightGBM"] = LGBMRegressor(
                    **params,
                    objective="regression",
                    random_state=42,
                    n_jobs=-1,
                    verbose=-1,
                    verbosity=-1,
                    force_row_wise=True
                )
            
            elif model_name == "Polynomial_Regression" or model_name == "PolynomialRegression":
                degree = params.get("poly__degree") or params.get("degree", 2)
                poly_model = Pipeline([
                    ("poly", PolynomialFeatures(degree=degree, include_bias=False)),
                    ("scaler", StandardScaler()),
                    ("model", LinearRegression())
                ])
                models["PolynomialRegression"] = poly_model
        
        # Train & evaluate models
        logger.info(f"Building {len(models)} models for comparison")
        results = []
        
        for name, model in models.items():
            logger.info(f"Training model: {name}")
            try:
                model.fit(X_train, y_train)
                logger.info(f"{name} training completed")
                
                y_train_pred = model.predict(X_train)
                y_test_pred = model.predict(X_test)
                
                result = {
                    "Model": name,
                    "MSE_train": float(mean_squared_error(y_train, y_train_pred)),
                    "MAE_train": float(mean_absolute_error(y_train, y_train_pred)),
                    "R2_train": float(r2_score(y_train, y_train_pred)),
                    "MSE_test": float(mean_squared_error(y_test, y_test_pred)),
                    "MAE_test": float(mean_absolute_error(y_test, y_test_pred)),
                    "R2_test": float(r2_score(y_test, y_test_pred))
                }
                results.append(result)
                logger.info(f"{name} - R²_test: {result['R2_test']:.4f}")
            except Exception as e:
                logger.warning(f"Failed to train {name}: {e}")
        
        # Sort by R2_test (descending)
        results.sort(key=lambda x: x["R2_test"], reverse=True)
        
        # Best model
        best_model = results[0]["Model"] if results else None
        
        logger.info("=== Regression Models Comparison ===")
        for result in results:
            logger.info(f"{result['Model']}: R²_test={result['R2_test']:.4f}")
        
        if best_model:
            logger.info(f"Best Model: {best_model}")
        
        # Save to Excel
        results_df = pd.DataFrame(results)
        output_file = "Model_Comparison_Results.xlsx"
        results_df.to_excel(output_file, index=False)
        logger.info(f"Results saved to {output_file}")
        
        # Emit comparison result as structured JSON
        emit_comparison_result(results, best_model)
        
        logger.info("Model comparison completed successfully!")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error during comparison: {error_msg}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
