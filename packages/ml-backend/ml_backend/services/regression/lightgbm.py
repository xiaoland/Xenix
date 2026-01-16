"""LightGBM Regression model with Pydantic parameter schemas"""

from typing import List
from pydantic import BaseModel, Field
import lightgbm as lgb

from .base import RegressionModel


# Parameter schema for single training
class LightGBMParams(BaseModel):
    """Parameters for LightGBM Regression"""
    n_estimators: int = Field(default=100, description="Number of boosting rounds", ge=1)
    learning_rate: float = Field(default=0.1, description="Learning rate", gt=0, le=1)
    max_depth: int = Field(default=-1, description="Maximum tree depth (-1=no limit)")
    num_leaves: int = Field(default=31, description="Maximum number of leaves in one tree", ge=2)
    subsample: float = Field(default=1.0, description="Subsample ratio of training instances", gt=0, le=1)
    colsample_bytree: float = Field(default=1.0, description="Subsample ratio of columns", gt=0, le=1)
    min_child_samples: int = Field(default=20, description="Minimum data in one leaf", ge=1)
    verbose: int = Field(default=-1, description="Verbosity level (-1=silent)")


# Parameter grid schema for batch training (GridSearchCV)
class LightGBMParamGrid(BaseModel):
    """Parameter grid for LightGBM Regression GridSearchCV"""
    n_estimators: List[int] = Field(
        default=[50, 100, 200],
        description="Number of boosting rounds to try"
    )
    learning_rate: List[float] = Field(
        default=[0.01, 0.1, 0.3],
        description="Learning rate values to try"
    )
    max_depth: List[int] = Field(
        default=[3, 5, 7, -1],
        description="Maximum depth values to try"
    )
    num_leaves: List[int] = Field(
        default=[31, 50, 100],
        description="Number of leaves values to try"
    )
    subsample: List[float] = Field(
        default=[0.8, 1.0],
        description="Subsample ratios to try"
    )


class LightGBMRegression(
    RegressionModel[lgb.LGBMRegressor, LightGBMParams, LightGBMParamGrid],
    param_grid=LightGBMParamGrid,
    model_param=LightGBMParams
):
    """
    LightGBM Regression - gradient boosting framework

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: LightGBMParams) -> lgb.LGBMRegressor:
        """
        Create LightGBM Regressor model instance

        Args:
            params: Validated LightGBM parameters

        Returns:
            Configured LGBMRegressor model
        """
        return lgb.LGBMRegressor(**params.model_dump(exclude_none=True))
