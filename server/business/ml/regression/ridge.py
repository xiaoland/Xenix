"""
Ridge Regression Model Module

This module provides tune, evaluate, and predict functions for Ridge regression.
All functions accept pandas DataFrames instead of file paths.
"""

from typing import Dict, Any, Union, Optional, Callable
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


class RidgeRegression(RegressionModel[Pipeline, RidgeModelParam]):
    """Ridge Regression model implementation."""

    @staticmethod
    def tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[RidgeModelParam] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> TuneResult:
        """
        Train Ridge regression with specific parameters.

        Args:
            X_train: Training features as DataFrame
            y_train: Training target as Series

        Returns:
            Dictionary with 'best_params', 'best_score', and 'model'
        """
        # Use provided params or default
        if param_grid is None:
            params = RidgeModelParam().model_dump()
        else:
            params = param_grid.model_dump(exclude_none=True)

        # Define pipeline model: Standardization + Ridge
        model = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    Ridge(random_state=42, alpha=params.get("model__alpha", 1.0)),
                ),
            ]
        )

        # Train the model
        model.fit(X_train, y_train)

        return {
            "best_params": params,
            "best_score": 0.0,  # Not applicable for single parameter training
            "model": model,
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
    def create_model(params: Optional[Dict[str, Any]] = None) -> Pipeline:
        """
        Create a Ridge model with given parameters.

        Args:
            params: Model parameters (e.g., {'model__alpha': 1.0})

        Returns:
            Sklearn Pipeline with StandardScaler and Ridge model
        """
        model = Pipeline(
            [("scaler", StandardScaler()), ("model", Ridge(random_state=42))]
        )

        if params:
            model.set_params(**params)

        return model


# Alias for the model class
Model = RidgeRegression
