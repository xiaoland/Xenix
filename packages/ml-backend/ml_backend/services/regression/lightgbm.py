"""LightGBM Regression model"""

from typing import Any, Dict, List
import lightgbm as lgb

from .base import RegressionModelBase


class LightGBMRegression(RegressionModelBase):
    """LightGBM Regression"""

    def get_model_class(self):
        return lgb.LGBMRegressor

    def get_default_params(self) -> Dict[str, Any]:
        return {"n_estimators": 100, "verbose": -1}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "n_estimators": [50, 100, 200],
            "learning_rate": [0.01, 0.1, 0.3],
            "max_depth": [3, 5, 7, -1],
            "num_leaves": [31, 50, 100],
            "subsample": [0.8, 1.0]
        }
