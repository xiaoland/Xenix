"""Gradient Boosting Decision Tree (GBDT) Regression model with Pydantic parameter schemas"""

from typing import List, Literal
from pydantic import BaseModel, Field
from sklearn.ensemble import GradientBoostingRegressor

from .base import RegressionModel


# Parameter schema for single training
class GBDTParams(BaseModel):
    """Parameters for Gradient Boosting Decision Tree Regression"""
    n_estimators: int = Field(default=100, description="Number of boosting stages", ge=1)
    learning_rate: float = Field(default=0.1, description="Shrinks contribution of each tree", gt=0, le=1)
    max_depth: int = Field(default=3, description="Maximum depth of individual trees", ge=1)
    subsample: float = Field(default=1.0, description="Fraction of samples for fitting trees", gt=0, le=1)
    min_samples_split: int = Field(default=2, description="Minimum samples to split node", ge=2)
    min_samples_leaf: int = Field(default=1, description="Minimum samples at leaf node", ge=1)
    loss: Literal["squared_error", "absolute_error", "huber", "quantile"] = Field(
        default="squared_error",
        description="Loss function to optimize"
    )


# Parameter grid schema for batch training (GridSearchCV)
class GBDTParamGrid(BaseModel):
    """Parameter grid for GBDT Regression GridSearchCV"""
    n_estimators: List[int] = Field(
        default=[50, 100, 200],
        description="Number of boosting stages to try"
    )
    learning_rate: List[float] = Field(
        default=[0.01, 0.1, 0.2],
        description="Learning rate values to try"
    )
    max_depth: List[int] = Field(
        default=[3, 5, 7],
        description="Maximum depth values to try"
    )
    subsample: List[float] = Field(
        default=[0.8, 1.0],
        description="Subsample fractions to try"
    )


class GBDTRegression(
    RegressionModel[GradientBoostingRegressor, GBDTParams, GBDTParamGrid],
    param_grid=GBDTParamGrid,
    model_param=GBDTParams
):
    """
    Gradient Boosting Decision Tree (GBDT) Regression

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: GBDTParams) -> GradientBoostingRegressor:
        """
        Create GBDT Regressor model instance

        Args:
            params: Validated GBDT parameters

        Returns:
            Configured GradientBoostingRegressor model
        """
        return GradientBoostingRegressor(**params.model_dump(exclude_none=True))
