#!/usr/bin/env python3
"""
Batch prediction script using the best model from hyperparameter tuning.
This script loads the trained model parameters, trains the model on all available data,
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

# Import ML libraries
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression, Ridge, Lasso, BayesianRidge
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, AdaBoostRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor


def load_params_from_json(json_filename):
    """Load parameters from JSON file"""
    if os.path.exists(json_filename):
        with open(json_filename, "r", encoding="utf-8") as f:
            return json.load(f)
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
        model = XGBRegressor(
            **params,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=-1
        )
        
    elif model_name == "LightGBM":
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
    parser.add_argument('--task-id', required=False, help='Task ID for database tracking')
    parser.add_argument('--training-data', default='Customer Value Data Table.xlsx', 
                       help='Training data file (default: Customer Value Data Table.xlsx)')
    
    args = parser.parse_args()
    
    try:
        # Map model names to JSON files
        json_files = {
            "Linear_Regression_Hyperparameter_Tuning": "Linear_Regression_Hyperparameter_Tuning_Params.json",
            "LinearRegression": "Linear_Regression_Hyperparameter_Tuning_Params.json",
            "Ridge": "Ridge_Params.json",
            "Lasso": "Lasso_Params.json",
            "BayesianRidge": "Bayesian_Ridge_Regression_Params.json",
            "Bayesian_Ridge_Regression": "Bayesian_Ridge_Regression_Params.json",
            "KNN": "K-Nearest_Neighbors_Params.json",
            "K-Nearest_Neighbors": "K-Nearest_Neighbors_Params.json",
            "DecisionTree": "Regression_Decision_Tree_Params.json",
            "Regression_Decision_Tree": "Regression_Decision_Tree_Params.json",
            "RandomForest": "Random_Forest_Params.json",
            "Random_Forest": "Random_Forest_Params.json",
            "GBDT": "GBDT_Params.json",
            "AdaBoost": "AdaBoost_Params.json",
            "XGBoost": "XGBoost_Params.json",
            "LightGBM": "LightGBM_Params.json",
            "PolynomialRegression": "Polynomial_Regression_Params.json",
            "Polynomial_Regression": "Polynomial_Regression_Params.json",
        }
        
        # Load model parameters
        json_file = json_files.get(args.model)
        if not json_file:
            raise ValueError(f"Unknown model: {args.model}")
        
        params = load_params_from_json(json_file)
        print(f"Loaded parameters for {args.model}: {params}")
        
        # Load training data
        print(f"Loading training data from {args.training_data}")
        df = pd.read_excel(args.training_data)
        
        # Define features and target
        # TODO: Make this configurable
        feature_cols = ['Historical Loan Amount', 'Number of Loans', 'Education', 
                       'Monthly Income', 'Gender']
        target_col = 'Customer Value'
        
        X = df[feature_cols]
        y = df[target_col]
        
        # Build and train model on ALL data
        print(f"Training {args.model} on all data...")
        model = build_model(args.model, params)
        model.fit(X, y)
        
        # Load prediction data
        print(f"Loading prediction data from {args.input}")
        pred_df = pd.read_excel(args.input)
        
        # Extract features
        X_pred = pred_df[feature_cols]
        
        # Make predictions
        print("Making predictions...")
        y_pred = model.predict(X_pred)
        
        # Add predictions to dataframe
        pred_df['Predicted Customer Value'] = y_pred
        
        # Save output
        print(f"Saving predictions to {args.output}")
        pred_df.to_excel(args.output, index=False)
        
        print("Prediction completed successfully!")
        
    except Exception as e:
        print(f"Error during prediction: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
