"""
LightGBM Model Module
"""

import pandas as pd
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

try:
    from lightgbm import LGBMRegressor
except ImportError:
    raise ImportError(
        "LightGBM is not installed. Please install it with: pip install lightgbm"
    )

from typing import Dict, Any, Union, Optional, Callable
from pydantic import BaseModel, Field
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult


class LightGBMModelParam(BaseModel):
    """Parameters for LightGBMRegressionModel."""

    n_estimators: int = Field(
        default=100, description="Number of boosting rounds (trees)."
    )
    learning_rate: float = Field(default=0.1, description="Learning rate.")
    max_depth: int = Field(
        default=3,
        description="Maximum tree depth (use -1 for no limit in LightGBM).",
    )


class LightGBMRegressionModel(RegressionModel[LGBMRegressor, LightGBMModelParam]):
    """LightGBM Regression model implementation."""

    @staticmethod
    def tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[LightGBMModelParam] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> TuneResult:
        # Use provided params or default
        if param_grid is None:
            params = LightGBMModelParam().model_dump()
        else:
            params = param_grid.model_dump(exclude_none=True)

        # Create model with parameters
        model = LGBMRegressor(
            objective="regression",
            random_state=42,
            n_jobs=-1,
            verbose=-1,
            verbosity=-1,
            n_estimators=params.get("n_estimators", 100),
            learning_rate=params.get("learning_rate", 0.1),
            max_depth=params.get("max_depth", 3),
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
        model: LGBMRegressor, X: pd.DataFrame, y: pd.Series
    ) -> Dict[str, float]:
        y_pred = model.predict(X)
        return {
            "mse": float(mean_squared_error(y, y_pred)),
            "mae": float(mean_absolute_error(y, y_pred)),
            "r2": float(r2_score(y, y_pred)),
        }

    @staticmethod
    def predict(model: LGBMRegressor, X: pd.DataFrame) -> pd.Series:
        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index, name="predictions")

    @staticmethod
    def create_model(params: Optional[Dict[str, Any]] = None) -> LGBMRegressor:
        model = LGBMRegressor(
            objective="regression", random_state=42, n_jobs=-1, verbose=-1, verbosity=-1
        )
        if params:
            model.set_params(**params)
        return model


# Alias for the model class
Model = LightGBMRegressionModel
