"""
AdaBoost Model Module
"""

import pandas as pd
from sklearn.ensemble import AdaBoostRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable, List
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


class AdaBoostParamGridModel(BaseModel):
    """Parameter grid for AdaBoost hyperparameter tuning."""

    n_estimators: List[int] = Field(
        default=[50, 100, 200], description="Number of estimators."
    )
    learning_rate: List[float] = Field(
        default=[0.01, 0.1, 1.0], description="Learning rate."
    )
    estimator__max_depth: List[int] = Field(
        default=[1, 3, 5], description="Max depth for base estimator."
    )


class AdaBoostRegressionModel(
    RegressionModel[AdaBoostRegressor, AdaBoostModelParam, AdaBoostParamGridModel]
):
    """AdaBoost Regression model implementation."""

    @staticmethod
    def auto_tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[AdaBoostParamGridModel] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> TuneResult:
        if param_grid is None:
            grid = AdaBoostParamGridModel().model_dump()
        else:
            grid = param_grid.model_dump()

        base_model = AdaBoostRegressor(
            estimator=DecisionTreeRegressor(), random_state=42
        )
        gs = GridSearchCV(base_model, grid, cv=3, scoring="r2")
        gs.fit(X_train, y_train)

        return {
            "best_params": gs.best_params_,
            "best_score": gs.best_score_,
            "model": gs.best_estimator_,
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
    def create_model(params: Optional[AdaBoostModelParam] = None) -> AdaBoostRegressor:
        if params:
            p = params.model_dump()
        else:
            p = {}
        estimator_depth = p.get("estimator__max_depth", 3)
        model = AdaBoostRegressor(
            estimator=DecisionTreeRegressor(max_depth=estimator_depth), random_state=42
        )
        model.set_params(**{k: v for k, v in p.items() if k != "estimator__max_depth"})
        return model


# Alias for the model class
Model = AdaBoostRegressionModel
