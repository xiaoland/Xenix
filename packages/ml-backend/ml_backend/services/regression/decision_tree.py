"""Decision Tree Regression model"""

from typing import Any, Dict, List
from sklearn.tree import DecisionTreeRegressor

from .base import RegressionModelBase


class DecisionTreeRegression(RegressionModelBase):
    """Decision Tree Regression"""

    def get_model_class(self):
        return DecisionTreeRegressor

    def get_default_params(self) -> Dict[str, Any]:
        return {"max_depth": 5}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "max_depth": [3, 5, 7, 10, None],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4]
        }
