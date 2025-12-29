"""
Polynomial Regression Model Module
"""

import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable
from pydantic import BaseModel, Field
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult


class PolynomialModelParam(BaseModel):
    """Parameters for PolynomialRegressionModel."""

    poly__degree: int = Field(
        default=2,
        description="Degree of polynomial features (poly__degree).",
    )


class PolynomialRegressionModel(RegressionModel[Pipeline, PolynomialModelParam]):
    """Polynomial Regression model implementation."""

    @staticmethod
    def tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[PolynomialModelParam] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> TuneResult:
        # Use provided params or default
        if param_grid is None:
            params = PolynomialModelParam().model_dump()
        else:
            params = param_grid.model_dump(exclude_none=True)

        # Create pipeline model with parameters
        model = Pipeline(
            [
                (
                    "poly",
                    PolynomialFeatures(
                        degree=params.get("poly__degree", 2), include_bias=False
                    ),
                ),
                ("scaler", StandardScaler()),
                ("model", LinearRegression()),
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
        poly_degree = 2
        if params and "poly__degree" in params:
            poly_degree = params.get("poly__degree", 2)

        model = Pipeline(
            [
                ("poly", PolynomialFeatures(degree=poly_degree, include_bias=False)),
                ("scaler", StandardScaler()),
                ("model", LinearRegression()),
            ]
        )

        if params:
            model.set_params(**params)

        return model


# Alias for the model class
Model = PolynomialRegressionModel
