"""Lasso Regression model"""

from typing import Any, Dict, List
from sklearn.linear_model import Lasso

from .base import RegressionModelBase


class LassoRegression(RegressionModelBase):
    """Lasso Regression with L1 regularization"""

    def get_model_class(self):
        return Lasso

    def get_default_params(self) -> Dict[str, Any]:
        return {"alpha": 1.0}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "alpha": [0.1, 1.0, 10.0, 100.0],
            "selection": ["cyclic", "random"]
        }
