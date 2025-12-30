"""
GBDT (Gradient Boosting Decision Tree) Model Module
"""

import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable, List
from pydantic import BaseModel, Field
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult


class GBDTModelParam(BaseModel):
    """Parameters for GBDTRegressionModel."""

    n_estimators: int = Field(
        default=100, description="Number of boosting rounds (trees)."
    )
    learning_rate: float = Field(default=0.1, description="Learning rate.")
    max_depth: int = Field(
        default=3, description="Maximum tree depth for base learners."
    )


class GBDTParamGridModel(BaseModel):
    """Parameter grid for GBDT hyperparameter tuning."""

    n_estimators: List[int] = Field(
        default=[50, 100, 200], description="Number of boosting rounds."
    )
    learning_rate: List[float] = Field(
        default=[0.01, 0.1, 0.2], description="Learning rate."
    )
    max_depth: List[int] = Field(default=[3, 5, 7], description="Maximum tree depth.")


class GBDTRegressionModel(
    RegressionModel[GradientBoostingRegressor, GBDTModelParam, GBDTParamGridModel]
):
    """GBDT Regression model implementation."""

    @staticmethod
    def auto_tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[GBDTParamGridModel] = None,
        
    ) -> TuneResult:
        if param_grid is None:
            grid = GBDTParamGridModel().model_dump()
        else:
            grid = param_grid.model_dump()

        base_model = GradientBoostingRegressor(random_state=42)
        gs = GridSearchCV(base_model, grid, cv=3, scoring="r2")
        gs.fit(X_train, y_train)

        return {
            "best_params": gs.best_params_,
            "best_score": gs.best_score_,
            "model": gs.best_estimator_,
        }

    @staticmethod
    def evaluate(
        model: GradientBoostingRegressor, X: pd.DataFrame, y: pd.Series
    ) -> Dict[str, float]:
        y_pred = model.predict(X)
        return {
            "mse": float(mean_squared_error(y, y_pred)),
            "mae": float(mean_absolute_error(y, y_pred)),
            "r2": float(r2_score(y, y_pred)),
        }

    @staticmethod
    def predict(model: GradientBoostingRegressor, X: pd.DataFrame) -> pd.Series:
        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index, name="predictions")

    @staticmethod
    def create_model(
        params: Optional[GBDTModelParam] = None,
    ) -> GradientBoostingRegressor:
        model = GradientBoostingRegressor(random_state=42)
        if params:
            p = params.model_dump()
            model.set_params(**p)
        return model


# Alias for the model class

# Register parameter schemas
GBDTRegressionModel.register_schemas(
    param_grid_class=GBDTRegressionParamGridModel,
    param_class=GBDTRegressionModelParam,
)

Model = GBDTRegressionModel
