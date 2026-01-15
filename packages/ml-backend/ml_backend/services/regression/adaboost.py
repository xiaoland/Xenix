"""AdaBoost Regression model"""

from typing import Any, Dict, List
from sklearn.ensemble import AdaBoostRegressor

from .base import RegressionModelBase


class AdaBoostRegression(RegressionModelBase):
    """AdaBoost Regression"""

    def get_model_class(self):
        return AdaBoostRegressor

    def get_default_params(self) -> Dict[str, Any]:
        return {"n_estimators": 50}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "n_estimators": [50, 100, 200],
            "learning_rate": [0.01, 0.1, 1.0],
            "loss": ["linear", "square", "exponential"]
        }
