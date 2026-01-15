"""Random Forest classification model"""

from typing import Any, Dict, List
from sklearn.ensemble import RandomForestClassifier

from .base import ClassificationModelBase


class RandomForestClassification(ClassificationModelBase):
    """Random Forest Classifier"""

    def get_model_class(self):
        return RandomForestClassifier

    def get_default_params(self) -> Dict[str, Any]:
        return {"n_estimators": 100, "random_state": 42}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "n_estimators": [50, 100, 200],
            "max_depth": [5, 10, None],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4]
        }
