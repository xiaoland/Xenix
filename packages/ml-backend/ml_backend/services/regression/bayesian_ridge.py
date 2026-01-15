"""Bayesian Ridge Regression model"""

from typing import Any, Dict, List
from sklearn.linear_model import BayesianRidge

from .base import RegressionModelBase


class BayesianRidgeRegression(RegressionModelBase):
    """Bayesian Ridge Regression"""

    def get_model_class(self):
        return BayesianRidge

    def get_default_params(self) -> Dict[str, Any]:
        return {}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "alpha_1": [1e-6, 1e-5, 1e-4],
            "alpha_2": [1e-6, 1e-5, 1e-4],
            "lambda_1": [1e-6, 1e-5, 1e-4],
            "lambda_2": [1e-6, 1e-5, 1e-4]
        }
