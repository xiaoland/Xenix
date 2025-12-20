#!/usr/bin/env python3
"""
Model comparison script that loads parameters from JSON files and compares models.
This version supports CLI arguments and database output.
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

# Import database utilities
try:
    from db_utils import update_task_status, store_comparison_result
    HAS_DB = True
except ImportError:
    HAS_DB = False
    print("Warning: Database utilities not available")

# Import logging setup
try:
    from log_handler import setup_logger
    HAS_LOGGING = True
except ImportError:
    HAS_LOGGING = False
    import logging
    print("Warning: Custom logging handler not available, using default")

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
    print("Warning: XGBoost not available. XGBoost model will be skipped.")

try:
    from lightgbm import LGBMRegressor
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False
    print("Warning: LightGBM not available. LightGBM model will be skipped.")


def load_params(json_filename, logger=None):
    """Load params from JSON file; return empty dict if not found"""
    if os.path.exists(json_filename):
        with open(json_filename, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        msg = f"⚠️ JSON file not found, using default params: {json_filename}"
        if logger:
            logger.warning(msg)
        else:
            print(msg)
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
    parser.add_argument('--input', default='Customer Value Data Table.xlsx', 
                       help='Input Excel file path (default: Customer Value Data Table.xlsx)')
    parser.add_argument('--output-db', required=False, help='Task ID for database output')
    
    args = parser.parse_args()
    task_id = args.output_db
    
    # Setup logger with trace ID
    if HAS_LOGGING and task_id:
        logger = setup_logger(__name__, task_id)
    else:
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting model comparison")
        
        if task_id and HAS_DB:
            update_task_status(task_id, 'running')
        
        # JSON files mapping
        json_files = {
            "LinearRegression": "Linear_Regression_Hyperparameter_Tuning_Params.json",
            "Ridge": "Ridge_Params.json",
            "Lasso": "Lasso_Params.json",
            "BayesianRidge": "Bayesian_Ridge_Regression_Params.json",
            "KNN": "K-Nearest_Neighbors_Params.json",
            "DecisionTree": "Regression_Decision_Tree_Params.json",
            "RandomForest": "Random_Forest_Params.json",
            "GBDT": "GBDT_Params.json",
            "AdaBoost": "AdaBoost_Params.json",
            "XGBoost": "XGBoost_Params.json",
            "LightGBM": "LightGBM_Params.json",
            "PolynomialRegression": "Polynomial_Regression_Params.json"
        }
        
        # Load all JSON parameter files
        logger.info("Loading model parameters from JSON files")
        model_params = {name: load_params(path, logger) for name, path in json_files.items()}
        
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
        
        # Build models
        models = {}
        
        # 1. Linear Regression
        params = add_prefix_for_pipeline(model_params["LinearRegression"])
        lin_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", LinearRegression())
        ])
        lin_model.set_params(**params)
        models["LinearRegression"] = lin_model
        
        # 2. Ridge Regression
        params = add_prefix_for_pipeline(model_params["Ridge"])
        ridge_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", Ridge(random_state=42))
        ])
        ridge_model.set_params(**params)
        models["Ridge"] = ridge_model
        
        # 3. Lasso Regression
        params = add_prefix_for_pipeline(model_params["Lasso"])
        lasso_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", Lasso(random_state=42))
        ])
        lasso_model.set_params(**params)
        models["Lasso"] = lasso_model
        
        # 4. Bayesian Ridge Regression
        params = add_prefix_for_pipeline(model_params["BayesianRidge"])
        bayes_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", BayesianRidge())
        ])
        bayes_model.set_params(**params)
        models["BayesianRidge"] = bayes_model
        
        # 5. KNN Regression
        params = add_prefix_for_pipeline(model_params["KNN"])
        knn_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", KNeighborsRegressor())
        ])
        knn_model.set_params(**params)
        models["KNN"] = knn_model
        
        # 6. Decision Tree
        models["DecisionTree"] = DecisionTreeRegressor(
            **model_params["DecisionTree"],
            random_state=42
        )
        
        # 7. Random Forest
        models["RandomForest"] = RandomForestRegressor(
            **model_params["RandomForest"],
            random_state=42,
            n_jobs=-1
        )
        
        # 8. GBDT (Gradient Boosting)
        models["GBDT"] = GradientBoostingRegressor(
            **model_params["GBDT"],
            random_state=42
        )
        
        # 9. AdaBoost
        ada_json = model_params["AdaBoost"]
        tree_params = {}
        ada_params_clean = {}
        
        for k, v in ada_json.items():
            if k.startswith("estimator__"):
                tree_params[k.replace("estimator__", "")] = v
            else:
                ada_params_clean[k] = v
        
        models["AdaBoost"] = AdaBoostRegressor(
            estimator=DecisionTreeRegressor(**tree_params) if tree_params else None,
            **ada_params_clean,
            random_state=42
        )
        
        # 10. XGBoost
        if HAS_XGB:
            xgb_params = model_params["XGBoost"]
            models["XGBoost"] = XGBRegressor(
                **xgb_params,
                objective="reg:squarederror",
                random_state=42,
                n_jobs=-1
            )
        
        # 11. LightGBM
        if HAS_LGBM:
            lgb_params = model_params["LightGBM"]
            models["LightGBM"] = LGBMRegressor(
                **lgb_params,
                objective="regression",
                random_state=42,
                n_jobs=-1,
                verbose=-1,
                verbosity=-1,
                force_row_wise=True
            )
        
        # 12. Polynomial Regression
        poly_params = model_params["PolynomialRegression"]
        degree = poly_params.get("degree", 2)
        
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
        
        # Store in database
        if task_id and HAS_DB:
            logger.info("Storing comparison results in database")
            store_comparison_result(task_id, results, best_model)
            update_task_status(task_id, 'completed')
        
        logger.info("Model comparison completed successfully!")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error during comparison: {error_msg}", exc_info=True)
        
        if task_id and HAS_DB:
            update_task_status(task_id, 'failed', error_msg)
        
        sys.exit(1)


if __name__ == "__main__":
    main()
