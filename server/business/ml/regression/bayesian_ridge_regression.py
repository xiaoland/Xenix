"""
Bayesian Ridge Regression Model Module
"""

import pandas as pd
from sklearn.linear_model import BayesianRidge
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable, List
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


class BayesianRidgeParamGridModel(BaseModel):
    """Parameter grid for Bayesian Ridge hyperparameter tuning."""

    model__alpha_1: List[float] = Field(
        default=[1e-6, 1e-5, 1e-4], description="Hyperparameter alpha_1."
    )
    model__alpha_2: List[float] = Field(
        default=[1e-6, 1e-5, 1e-4], description="Hyperparameter alpha_2."
    )


class BayesianRidgeRegressionModel(
    RegressionModel[Pipeline, BayesianRidgeModelParam, BayesianRidgeParamGridModel]
):
    """BayesianRidge Regression model implementation."""

    @staticmethod
    def auto_tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[BayesianRidgeParamGridModel] = None,
        
    ) -> TuneResult:
        if param_grid is None:
            grid = BayesianRidgeParamGridModel().model_dump()
        else:
            grid = param_grid.model_dump()

        base_model = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", BayesianRidge()),
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
    def create_model(params: Optional[BayesianRidgeModelParam] = None) -> Pipeline:
        model = Pipeline([("scaler", StandardScaler()), ("model", BayesianRidge())])
        if params:
            p = params.model_dump()
            model.set_params(**p)
        return model


# Alias for the model class

# Register parameter schemas
BayesianRidgeRegressionModel.register_schemas(
    param_grid_class=BayesianRidgeRegressionParamGridModel,
    param_class=BayesianRidgeRegressionModelParam,
)

Model = BayesianRidgeRegressionModel
