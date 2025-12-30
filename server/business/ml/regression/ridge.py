"""
Ridge Regression Model Module

This module provides tune, evaluate, and predict functions for Ridge regression.
All functions accept pandas DataFrames instead of file paths.
"""

from typing import Dict, Any, Union, Optional, Callable, List
from pydantic import BaseModel, Field
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult


class RidgeModelParam(BaseModel):
    """Parameters for RidgeRegression."""

    model__alpha: float = Field(
        default=1.0,
        description="Regularization alpha value for Ridge (model__alpha).",
    )


class RidgeParamGridModel(BaseModel):
    """Parameter grid for Ridge hyperparameter tuning."""

    model__alpha: List[float] = Field(
        default=[0.001, 0.01, 0.1, 1.0, 10.0], description="Regularization alpha."
    )


class RidgeRegression(RegressionModel[Pipeline, RidgeModelParam, RidgeParamGridModel]):
    """Ridge Regression model implementation."""

    @staticmethod
    def auto_tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[RidgeParamGridModel] = None,
        
    ) -> TuneResult:
        if param_grid is None:
            grid = RidgeParamGridModel().model_dump()
        else:
            grid = param_grid.model_dump()

        base_model = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", Ridge(random_state=42)),
            ]
        )
        gs = GridSearchCV(base_model, grid, cv=3, scoring="r2")
        gs.fit(X_train, y_train)

        return {
            "best_params": gs.best_params_,
            "best_score": gs.best_score_,
            "model": gs.best_estimator_,
        }

    @staticmethod
    def evaluate(model: Pipeline, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """
        Evaluate model performance on given data.

        Args:
            model: Trained model (sklearn Pipeline or estimator)
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
    def predict(model: Pipeline, X: pd.DataFrame) -> pd.Series:
        """
        Make predictions using trained model.

        Args:
            model: Trained model (sklearn Pipeline or estimator)
            X: Features as DataFrame

        Returns:
            Predictions as Series
        """
        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index, name="predictions")

    @staticmethod
    def create_model(params: Optional[RidgeModelParam] = None) -> Pipeline:
        model = Pipeline(
            [("scaler", StandardScaler()), ("model", Ridge(random_state=42))]
        )
        if params:
            p = params.model_dump()
            model.set_params(**p)
        return model


# Alias for the model class
Model = RidgeRegression
