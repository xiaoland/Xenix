"""Ridge Regression model"""

from typing import Any, Dict, List
from sklearn.linear_model import Ridge

from .base import RegressionModelBase


class RidgeRegression(RegressionModelBase):
    """Ridge Regression with L2 regularization"""

    def get_model_class(self):
        return Ridge

    def get_default_params(self) -> Dict[str, Any]:
        return {"alpha": 1.0}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "alpha": [0.1, 1.0, 10.0, 100.0],
            "solver": ["auto", "svd", "cholesky"]
        }
