"""
Regression Decision Tree Model Module
"""

import pandas as pd
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable, List
from pydantic import BaseModel, Field
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult


class DecisionTreeModelParam(BaseModel):
    """Parameters for DecisionTreeRegressionModel."""

    max_depth: int | None = Field(
        default=5,
        description="Maximum depth of the tree (int) or None to expand until all leaves are pure.",
    )
    min_samples_split: int = Field(
        default=2,
        description="Minimum number of samples required to split an internal node.",
    )
    min_samples_leaf: int = Field(
        default=1,
        description="Minimum number of samples required to be at a leaf node.",
    )


class DecisionTreeParamGridModel(BaseModel):
    """Parameter grid for Decision Tree hyperparameter tuning."""

    max_depth: List[int] = Field(
        default=[3, 5, 7], description="Maximum depth of the tree."
    )
    min_samples_split: List[int] = Field(
        default=[2, 5, 10], description="Minimum number of samples required to split."
    )
    min_samples_leaf: List[int] = Field(
        default=[1, 2, 4],
        description="Minimum number of samples required to be at a leaf node.",
    )


class DecisionTreeRegressionModel(
    RegressionModel[
        DecisionTreeRegressor, DecisionTreeModelParam, DecisionTreeParamGridModel
    ]
):
    """DecisionTree Regression model implementation."""

    @staticmethod
    def auto_tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[DecisionTreeParamGridModel] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> TuneResult:
        if param_grid is None:
            grid = DecisionTreeParamGridModel().model_dump()
        else:
            grid = param_grid.model_dump()

        base_model = DecisionTreeRegressor(random_state=42)
        gs = GridSearchCV(base_model, grid, cv=3, scoring="r2")
        gs.fit(X_train, y_train)

        return {
            "best_params": gs.best_params_,
            "best_score": gs.best_score_,
            "model": gs.best_estimator_,
        }

    @staticmethod
    def evaluate(
        model: DecisionTreeRegressor, X: pd.DataFrame, y: pd.Series
    ) -> Dict[str, float]:
        y_pred = model.predict(X)
        return {
            "mse": float(mean_squared_error(y, y_pred)),
            "mae": float(mean_absolute_error(y, y_pred)),
            "r2": float(r2_score(y, y_pred)),
        }

    @staticmethod
    def predict(model: DecisionTreeRegressor, X: pd.DataFrame) -> pd.Series:
        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index, name="predictions")

    @staticmethod
    def create_model(
        params: Optional[DecisionTreeModelParam] = None,
    ) -> DecisionTreeRegressor:
        model = DecisionTreeRegressor(random_state=42)
        if params:
            p = params.model_dump()
            model.set_params(**p)
        return model


# Alias for the model class
Model = DecisionTreeRegressionModel
