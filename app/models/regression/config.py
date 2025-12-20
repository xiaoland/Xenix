"""
Configuration file for Xenix ML models.
This file contains utility functions and constants.
NO default feature columns - they must be provided via stdin for data-specific requirements.
"""

# Constants for model identification
AVAILABLE_MODELS = [
    "Linear_Regression_Hyperparameter_Tuning",
    "Ridge",
    "Lasso",
    "Bayesian_Ridge_Regression",
    "K-Nearest_Neighbors",
    "Regression_Decision_Tree",
    "Random_Forest",
    "GBDT",
    "AdaBoost",
    "XGBoost",
    "LightGBM",
    "Polynomial_Regression"
]
