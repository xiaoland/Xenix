"""
Configuration file for Xenix ML models.
This file contains utility functions and constants.
NO default feature columns - they must be provided via stdin for data-specific requirements.
"""

# Constants for model identification
AVAILABLE_MODELS = [
    "regression.Linear_Regression_Hyperparameter_Tuning",
    "regression.Ridge",
    "regression.Lasso",
    "regression.Bayesian_Ridge_Regression",
    "regression.K-Nearest_Neighbors",
    "regression.Regression_Decision_Tree",
    "regression.Random_Forest",
    "regression.GBDT",
    "regression.AdaBoost",
    "regression.XGBoost",
    "regression.LightGBM",
    "regression.Polynomial_Regression"
]
