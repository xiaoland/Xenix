"""
Random Forest Model Module

This module provides tune, evaluate, and predict functions for Random Forest regression.
All functions accept pandas DataFrames instead of file paths.
"""

from typing import Dict, Any, Union, Optional, Callable
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


class RandomForestRegressionModel(
    RegressionModel[RandomForestRegressor, RandomForestModelParam]
):
    """Random Forest Regression model implementation."""

    @staticmethod
    def tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[RandomForestModelParam] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> TuneResult:
        """
        Train Random Forest regression with specific parameters.

        Args:
            X_train: Training features as DataFrame
            y_train: Training target as Series

        Returns:
            Dictionary with 'best_params', 'best_score', and 'model'
        """
        # Use provided params or default
        if param_grid is None:
            params = RandomForestModelParam().model_dump()
        else:
            params = param_grid.model_dump(exclude_none=True)

        # Create model with parameters
        model = RandomForestRegressor(
            random_state=42,
            n_jobs=-1,
            n_estimators=params.get("n_estimators", 100),
            max_depth=params.get("max_depth"),
            min_samples_split=params.get("min_samples_split", 2),
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
    def create_model(params: Optional[Dict[str, Any]] = None) -> RandomForestRegressor:
        """
        Create a Random Forest model with given parameters.

        Args:
            params: Model parameters

        Returns:
            RandomForestRegressor model
        """
        model = RandomForestRegressor(random_state=42, n_jobs=-1)

        if params:
            model.set_params(**params)

        return model


# Alias for the model class
Model = RandomForestRegressionModel
