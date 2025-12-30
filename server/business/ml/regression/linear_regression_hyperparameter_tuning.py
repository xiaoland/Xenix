"""
Linear Regression Model Module

This module provides tune, evaluate, and predict functions for Linear regression.
All functions accept pandas DataFrames instead of file paths.
"""

from typing import Dict, Any, Union, Optional, Callable, List
from pydantic import BaseModel, Field
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult


class LinearRegressionModelParam(BaseModel):
    """Parameters for LinearRegressionModel."""

    model__fit_intercept: bool = Field(
        default=True,
        description="Whether to calculate the intercept for the model (model__fit_intercept).",
    )
    model__copy_X: bool = Field(
        default=True,
        description="Whether to copy X before fitting (model__copy_X).",
    )


class LinearRegressionParamGridModel(BaseModel):
    """Parameter grid for Linear Regression hyperparameter tuning."""

    model__fit_intercept: List[bool] = Field(
        default=[True, False], description="Whether to calculate the intercept."
    )
    model__copy_X: List[bool] = Field(
        default=[True, False], description="Whether to copy X before fitting."
    )


class LinearRegressionModel(
    RegressionModel[
        Pipeline, LinearRegressionModelParam, LinearRegressionParamGridModel
    ]
):
    """Linear Regression model implementation."""

    @staticmethod
    def auto_tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[LinearRegressionParamGridModel] = None,
        
    ) -> TuneResult:
        if param_grid is None:
            grid = LinearRegressionParamGridModel().model_dump()
        else:
            grid = param_grid.model_dump()

        base_model = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", LinearRegression()),
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
    def create_model(params: Optional[LinearRegressionModelParam] = None) -> Pipeline:
        model = Pipeline([("scaler", StandardScaler()), ("model", LinearRegression())])
        if params:
            p = params.model_dump()
            model.set_params(**p)
        return model


# Alias for the model class
Model = LinearRegressionModel
