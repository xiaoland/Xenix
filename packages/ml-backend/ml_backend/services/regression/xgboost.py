"""XGBoost Regression model"""

from typing import Any, Dict, List
import xgboost as xgb

from .base import RegressionModelBase


class XGBoostRegression(RegressionModelBase):
    """XGBoost Regression"""

    def get_model_class(self):
        return xgb.XGBRegressor

    def get_default_params(self) -> Dict[str, Any]:
        return {"n_estimators": 100, "objective": "reg:squarederror"}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "n_estimators": [50, 100, 200],
            "learning_rate": [0.01, 0.1, 0.3],
            "max_depth": [3, 5, 7],
            "subsample": [0.8, 1.0],
            "colsample_bytree": [0.8, 1.0]
        }
