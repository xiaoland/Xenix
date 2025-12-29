"""
Bayesian Ridge Regression Model Module
"""

import pandas as pd
from sklearn.linear_model import BayesianRidge
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable
from pydantic import BaseModel, Field
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult


class BayesianRidgeModelParam(BaseModel):
    """Parameters for BayesianRidgeRegressionModel."""

    model__alpha_1: float = Field(
        default=1e-6,
        description="Hyperparameter alpha_1 (shape parameter) for BayesianRidge.",
    )
    model__alpha_2: float = Field(
        default=1e-6,
        description="Hyperparameter alpha_2 (scale parameter) for BayesianRidge.",
    )


class BayesianRidgeRegressionModel(RegressionModel[Pipeline, BayesianRidgeModelParam]):
    """BayesianRidge Regression model implementation."""

    @staticmethod
    def tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[BayesianRidgeModelParam] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> TuneResult:
        # Use provided params or default
        if param_grid is None:
            params = BayesianRidgeModelParam().model_dump()
        else:
            params = param_grid.model_dump(exclude_none=True)

        # Create pipeline model: Standardization + BayesianRidge
        model = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    BayesianRidge(
                        alpha_1=params.get("model__alpha_1", 1e-6),
                        alpha_2=params.get("model__alpha_2", 1e-6),
                    ),
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
        y_pred = model.predict(X)
        return {
            "mse": float(mean_squared_error(y, y_pred)),
            "mae": float(mean_absolute_error(y, y_pred)),
            "r2": float(r2_score(y, y_pred)),
        }

    @staticmethod
    def predict(model: Pipeline, X: pd.DataFrame) -> pd.Series:
        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index, name="predictions")

    @staticmethod
    def create_model(params: Optional[Dict[str, Any]] = None) -> Pipeline:
        model = Pipeline([("scaler", StandardScaler()), ("model", BayesianRidge())])
        if params:
            model.set_params(**params)
        return model


# Alias for the model class
Model = BayesianRidgeRegressionModel
