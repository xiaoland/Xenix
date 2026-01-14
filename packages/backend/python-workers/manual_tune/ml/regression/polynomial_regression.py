"""
Polynomial Regression Model Module
"""

import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable, List
from pydantic import BaseModel, Field
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult


class PolynomialModelParam(BaseModel):
    """Parameters for PolynomialRegressionModel."""

    poly__degree: int = Field(
        default=2,
        description="Degree of polynomial features (poly__degree).",
    )


class PolynomialParamGridModel(BaseModel):
    """Parameter grid for Polynomial Regression hyperparameter tuning."""

    poly__degree: List[int] = Field(
        default=[2, 3, 4], description="Degree of polynomial features."
    )


class PolynomialRegressionModel(
    RegressionModel[Pipeline, PolynomialModelParam, PolynomialParamGridModel],
    param_grid=PolynomialParamGridModel,
    model_param=PolynomialModelParam,
):
    """Polynomial Regression model implementation."""

    @staticmethod
    def auto_tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[PolynomialParamGridModel] = None,
        
    ) -> TuneResult:
        if param_grid is None:
            grid = PolynomialParamGridModel().model_dump()
        else:
            grid = param_grid.model_dump()

        base_model = Pipeline(
            [
                ("poly", PolynomialFeatures(include_bias=False)),
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
    def create_model(params: Optional[PolynomialModelParam] = None) -> Pipeline:
        model = Pipeline(
            [
                ("poly", PolynomialFeatures(include_bias=False)),
                ("scaler", StandardScaler()),
                ("model", LinearRegression()),
            ]
        )
        if params:
            p = params.model_dump()
            model.set_params(**p)
        return model


# Alias for the model class
Model = PolynomialRegressionModel
