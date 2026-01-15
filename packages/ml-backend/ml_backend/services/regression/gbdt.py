"""Gradient Boosting Decision Tree (GBDT) Regression model"""

from typing import Any, Dict, List
from sklearn.ensemble import GradientBoostingRegressor

from .base import RegressionModelBase


class GBDTRegression(RegressionModelBase):
    """Gradient Boosting Decision Tree Regression"""

    def get_model_class(self):
        return GradientBoostingRegressor

    def get_default_params(self) -> Dict[str, Any]:
        return {"n_estimators": 100}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "n_estimators": [50, 100, 200],
            "learning_rate": [0.01, 0.1, 0.2],
            "max_depth": [3, 5, 7],
            "subsample": [0.8, 1.0]
        }
