"""Logistic Regression classification model"""

from typing import Any, Dict, List
from sklearn.linear_model import LogisticRegression

from .base import ClassificationModelBase


class LogisticRegressionClassifier(ClassificationModelBase):
    """Logistic Regression Classifier"""

    def get_model_class(self):
        return LogisticRegression

    def get_default_params(self) -> Dict[str, Any]:
        return {"max_iter": 1000}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "C": [0.1, 1.0, 10.0, 100.0],
            "solver": ["lbfgs", "liblinear"],
            "penalty": ["l2"]
        }
