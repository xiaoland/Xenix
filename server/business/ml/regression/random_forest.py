"""
Random Forest Model Module

This module provides tune, evaluate, and predict functions for Random Forest regression.
All functions accept pandas DataFrames instead of file paths.
"""

from typing import Dict, Any, Union, Optional, Callable, List
from pydantic import BaseModel, Field
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult


class RandomForestModelParam(BaseModel):
    """Parameters for RandomForestRegressionModel."""

    n_estimators: int = Field(default=100, description="Number of trees in the forest.")
    max_depth: int | None = Field(
        default=10,
        description="Maximum depth for each tree (int) or None for no limit.",
    )
    min_samples_split: int = Field(
        default=2,
        description="Minimum number of samples required to split an internal node.",
    )


class RandomForestParamGridModel(BaseModel):
    """Parameter grid for Random Forest hyperparameter tuning."""

    n_estimators: List[int] = Field(
        default=[50, 100, 200], description="Number of trees in the forest."
    )
    max_depth: List[int] = Field(
        default=[5, 10, 15], description="Maximum depth for each tree."
    )
    min_samples_split: List[int] = Field(
        default=[2, 5, 10], description="Minimum number of samples required to split."
    )


class RandomForestRegressionModel(
    RegressionModel[
        RandomForestRegressor, RandomForestModelParam, RandomForestParamGridModel
    ],
    param_grid=RandomForestParamGridModel,
    model_param=RandomForestModelParam,
):
    """Random Forest Regression model implementation."""

    @staticmethod
    def auto_tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[RandomForestParamGridModel] = None,
        
    ) -> TuneResult:
        if param_grid is None:
            grid = RandomForestParamGridModel().model_dump()
        else:
            grid = param_grid.model_dump()

        base_model = RandomForestRegressor(random_state=42, n_jobs=-1)
        gs = GridSearchCV(base_model, grid, cv=3, scoring="r2")
        gs.fit(X_train, y_train)

        return {
            "best_params": gs.best_params_,
            "best_score": gs.best_score_,
            "model": gs.best_estimator_,
        }

    @staticmethod
    def evaluate(
        model: RandomForestRegressor, X: pd.DataFrame, y: pd.Series
    ) -> Dict[str, float]:
        """
        Evaluate model performance on given data.

        Args:
            model: Trained model (sklearn estimator)
            X: Features as DataFrame
            y: Target as Series

        Returns:
            Dictionary with MSE, MAE, and R2 scores
        """
        y_pred = model.predict(X)

        return {
            "mse": float(mean_squared_error(y, y_pred)),
            "mae": float(mean_absolute_error(y, y_pred)),
            "r2": float(r2_score(y, y_pred)),
        }

    @staticmethod
    def predict(model: RandomForestRegressor, X: pd.DataFrame) -> pd.Series:
        """
        Make predictions using trained model.

        Args:
            model: Trained model (sklearn estimator)
            X: Features as DataFrame

        Returns:
            Predictions as Series
        """
        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index, name="predictions")

    @staticmethod
    def create_model(
        params: Optional[RandomForestModelParam] = None,
    ) -> RandomForestRegressor:
        model = RandomForestRegressor(random_state=42, n_jobs=-1)
        if params:
            p = params.model_dump()
            model.set_params(**p)
        return model


# Alias for the model class
Model = RandomForestRegressionModel
