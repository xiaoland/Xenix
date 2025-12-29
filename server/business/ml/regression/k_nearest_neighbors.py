"""
K-Nearest Neighbors Model Module
"""

import pandas as pd
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable, List
from pydantic import BaseModel, Field
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult


class KNNModelParam(BaseModel):
    """Parameters for KNNRegressionModel."""

    model__n_neighbors: int = Field(
        default=5,
        description="Number of neighbors to consider for KNN (model__n_neighbors).",
    )
    model__weights: str = Field(
        default="uniform",
        description="Weight function used in prediction: 'uniform' or 'distance' (model__weights).",
    )


class KNNParamGridModel(BaseModel):
    """Parameter grid for KNN hyperparameter tuning."""

    model__n_neighbors: List[int] = Field(
        default=[3, 5, 7], description="Number of neighbors."
    )
    model__weights: List[str] = Field(
        default=["uniform", "distance"], description="Weight function."
    )


class KNNRegressionModel(RegressionModel[Pipeline, KNNModelParam, KNNParamGridModel]):
    """KNN Regression model implementation."""

    @staticmethod
    def tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[KNNParamGridModel] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> TuneResult:
        if param_grid is None:
            grid = KNNParamGridModel().model_dump()
        else:
            grid = param_grid.model_dump()

        base_model = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", KNeighborsRegressor()),
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
    def create_model(params: Optional[KNNModelParam] = None) -> Pipeline:
        model = Pipeline(
            [("scaler", StandardScaler()), ("model", KNeighborsRegressor())]
        )
        if params:
            p = params.model_dump()
            model.set_params(**p)
        return model


# Alias for the model class
Model = KNNRegressionModel
