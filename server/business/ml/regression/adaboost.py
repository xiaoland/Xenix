"""
AdaBoost Model Module
"""

import pandas as pd
from sklearn.ensemble import AdaBoostRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable
from pydantic import BaseModel, Field
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult


class AdaBoostModelParam(BaseModel):
    """Parameters for AdaBoostRegressionModel."""

    n_estimators: int = Field(default=100, description="Number of estimators (trees).")
    learning_rate: float = Field(default=0.1, description="Learning rate (shrinkage).")
    estimator__max_depth: int = Field(
        default=3,
        description="Max depth for the base estimator (DecisionTree).",
    )


class AdaBoostRegressionModel(RegressionModel[AdaBoostRegressor, AdaBoostModelParam]):
    """AdaBoost Regression model implementation."""

    @staticmethod
    def tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[AdaBoostModelParam] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> TuneResult:
        # Use provided params or default
        if param_grid is None:
            params = AdaBoostModelParam().model_dump()
        else:
            params = param_grid.model_dump(exclude_none=True)

        # Create model with parameters
        model = AdaBoostRegressor(
            estimator=DecisionTreeRegressor(
                max_depth=params.get("estimator__max_depth", 3)
            ),
            n_estimators=params.get("n_estimators", 100),
            learning_rate=params.get("learning_rate", 0.1),
            random_state=42,
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
        model: AdaBoostRegressor, X: pd.DataFrame, y: pd.Series
    ) -> Dict[str, float]:
        y_pred = model.predict(X)
        return {
            "mse": float(mean_squared_error(y, y_pred)),
            "mae": float(mean_absolute_error(y, y_pred)),
            "r2": float(r2_score(y, y_pred)),
        }

    @staticmethod
    def predict(model: AdaBoostRegressor, X: pd.DataFrame) -> pd.Series:
        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index, name="predictions")

    @staticmethod
    def create_model(params: Optional[Dict[str, Any]] = None) -> AdaBoostRegressor:
        estimator_depth = 3
        if params and "estimator__max_depth" in params:
            estimator_depth = params.pop("estimator__max_depth")

        model = AdaBoostRegressor(
            estimator=DecisionTreeRegressor(max_depth=estimator_depth), random_state=42
        )
        if params:
            model.set_params(**params)
        return model


# Alias for the model class
Model = AdaBoostRegressionModel
