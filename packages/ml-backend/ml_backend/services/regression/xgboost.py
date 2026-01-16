"""XGBoost Regression model with Pydantic parameter schemas"""

from typing import List, Literal
from pydantic import BaseModel, Field
import xgboost as xgb

from .base import RegressionModel


# Parameter schema for single training
class XGBoostParams(BaseModel):
    """Parameters for XGBoost Regression"""
    n_estimators: int = Field(default=100, description="Number of boosting rounds", ge=1)
    learning_rate: float = Field(default=0.3, description="Step size shrinkage (eta)", gt=0, le=1)
    max_depth: int = Field(default=6, description="Maximum tree depth", ge=1)
    subsample: float = Field(default=1.0, description="Subsample ratio of training instances", gt=0, le=1)
    colsample_bytree: float = Field(default=1.0, description="Subsample ratio of columns", gt=0, le=1)
    objective: Literal["reg:squarederror", "reg:squaredlogerror", "reg:pseudohubererror"] = Field(
        default="reg:squarederror",
        description="Learning task objective"
    )
    gamma: float = Field(default=0.0, description="Minimum loss reduction for split", ge=0)
    min_child_weight: float = Field(default=1.0, description="Minimum sum of instance weight in child", ge=0)


# Parameter grid schema for batch training (GridSearchCV)
class XGBoostParamGrid(BaseModel):
    """Parameter grid for XGBoost Regression GridSearchCV"""
    n_estimators: List[int] = Field(
        default=[50, 100, 200],
        description="Number of boosting rounds to try"
    )
    learning_rate: List[float] = Field(
        default=[0.01, 0.1, 0.3],
        description="Learning rate values to try"
    )
    max_depth: List[int] = Field(
        default=[3, 5, 7],
        description="Maximum depth values to try"
    )
    subsample: List[float] = Field(
        default=[0.8, 1.0],
        description="Subsample ratios to try"
    )
    colsample_bytree: List[float] = Field(
        default=[0.8, 1.0],
        description="Column subsample ratios to try"
    )


class XGBoostRegression(
    RegressionModel[xgb.XGBRegressor, XGBoostParams, XGBoostParamGrid],
    param_grid=XGBoostParamGrid,
    model_param=XGBoostParams
):
    """
    XGBoost Regression - gradient boosted trees

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: XGBoostParams) -> xgb.XGBRegressor:
        """
        Create XGBoost Regressor model instance

        Args:
            params: Validated XGBoost parameters

        Returns:
            Configured XGBRegressor model
        """
        return xgb.XGBRegressor(**params.model_dump(exclude_none=True))
