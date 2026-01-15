"""K-Nearest Neighbors Regression model"""

from typing import Any, Dict, List
from sklearn.neighbors import KNeighborsRegressor

from .base import RegressionModelBase


class KNNRegression(RegressionModelBase):
    """K-Nearest Neighbors Regression"""

    def get_model_class(self):
        return KNeighborsRegressor

    def get_default_params(self) -> Dict[str, Any]:
        return {"n_neighbors": 5}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "n_neighbors": [3, 5, 7, 9],
            "weights": ["uniform", "distance"],
            "algorithm": ["auto", "ball_tree", "kd_tree"]
        }
