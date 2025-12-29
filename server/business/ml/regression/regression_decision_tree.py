"""
Regression Decision Tree Model Module
"""

import pandas as pd
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable
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


class DecisionTreeRegressionModel(
    RegressionModel[DecisionTreeRegressor, DecisionTreeModelParam]
):
    """DecisionTree Regression model implementation."""

    @staticmethod
    def tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[DecisionTreeModelParam] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> TuneResult:
        # Use provided params or default
        if param_grid is None:
            params = DecisionTreeModelParam().model_dump()
        else:
            params = param_grid.model_dump(exclude_none=True)

        # Create model with parameters
        model = DecisionTreeRegressor(
            random_state=42,
            max_depth=params.get("max_depth"),
            min_samples_split=params.get("min_samples_split", 2),
            min_samples_leaf=params.get("min_samples_leaf", 1),
        )

        # Train the model
        model.fit(X_train, y_train)

        return {
            "best_params": params,
            "best_score": 0.0,  # Not applicable for single parameter training
            "model": model,
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
    def create_model(params: Optional[Dict[str, Any]] = None) -> DecisionTreeRegressor:
        model = DecisionTreeRegressor(random_state=42)
        if params:
            model.set_params(**params)
        return model


# Alias for the model class
Model = DecisionTreeRegressionModel
