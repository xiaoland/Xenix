"""Linear Regression model"""

from typing import Any, Dict, List
from sklearn.linear_model import LinearRegression

from .base import RegressionModelBase


class LinearRegressionModel(RegressionModelBase):
    """Linear Regression (OLS)"""

    def get_model_class(self):
        return LinearRegression

    def get_default_params(self) -> Dict[str, Any]:
        return {}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "fit_intercept": [True, False],
            "positive": [True, False]
        }
