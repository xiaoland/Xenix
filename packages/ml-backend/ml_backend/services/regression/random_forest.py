"""Random Forest Regression model"""

from typing import Any, Dict, List
from sklearn.ensemble import RandomForestRegressor

from .base import RegressionModelBase


class RandomForestRegression(RegressionModelBase):
    """Random Forest Regression"""

    def get_model_class(self):
        return RandomForestRegressor

    def get_default_params(self) -> Dict[str, Any]:
        return {"n_estimators": 100}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "n_estimators": [50, 100, 200],
            "max_depth": [5, 10, None],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4]
        }
