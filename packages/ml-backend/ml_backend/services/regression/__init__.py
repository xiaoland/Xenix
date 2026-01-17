"""Regression service - 12 regression models"""

from .linear import LinearRegressionModel
from .ridge import RidgeRegression
from .lasso import LassoRegression
from .bayesian_ridge import BayesianRidgeRegression
from .polynomial import PolynomialRegression
from .knn import KNNRegression
from .decision_tree import DecisionTreeRegression
from .random_forest import RandomForestRegression
from .adaboost import AdaBoostRegression
from .gbdt import GBDTRegression
from .xgboost import XGBoostRegression
from .lightgbm import LightGBMRegression


# Model registry: maps model names to model classes
REGRESSION_MODELS = {
    "regression.linear": LinearRegressionModel,
    "regression.ridge": RidgeRegression,
    "regression.lasso": LassoRegression,
    "regression.bayesian_ridge": BayesianRidgeRegression,
    "regression.polynomial": PolynomialRegression,
    "regression.knn": KNNRegression,
    "regression.decision_tree": DecisionTreeRegression,
    "regression.random_forest": RandomForestRegression,
    "regression.adaboost": AdaBoostRegression,
    "regression.gbdt": GBDTRegression,
    "regression.xgboost": XGBoostRegression,
    "regression.lightgbm": LightGBMRegression,
}


def get_regression_model(model_name: str):
    """
    Get regression model instance by name

    Args:
        model_name: Model identifier (e.g., 'regression.ridge')

    Returns:
        Model instance

    Raises:
        ValueError: If model name is unknown
    """
    if model_name not in REGRESSION_MODELS:
        raise ValueError(
            f"Unknown regression model: {model_name}. "
            f"Available models: {', '.join(REGRESSION_MODELS.keys())}"
        )

    model_class = REGRESSION_MODELS[model_name]
    return model_class()


def list_regression_models():
    """Get list of available regression model names"""
    return list(REGRESSION_MODELS.keys())


__all__ = [
    "REGRESSION_MODELS",
    "get_regression_model",
    "list_regression_models",
    "LinearRegressionModel",
    "RidgeRegression",
    "LassoRegression",
    "BayesianRidgeRegression",
    "PolynomialRegression",
    "KNNRegression",
    "DecisionTreeRegression",
    "RandomForestRegression",
    "AdaBoostRegression",
    "GBDTRegression",
    "XGBoostRegression",
    "LightGBMRegression",
]
