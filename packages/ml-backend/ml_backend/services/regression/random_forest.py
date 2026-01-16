"""Random Forest Regression model with Pydantic parameter schemas"""

from typing import List, Literal
from pydantic import BaseModel, Field
from sklearn.ensemble import RandomForestRegressor

from .base import RegressionModel


# Parameter schema for single training
class RandomForestParams(BaseModel):
    """Parameters for Random Forest Regression"""
    n_estimators: int = Field(default=100, description="Number of trees in forest", ge=1)
    criterion: Literal["squared_error", "friedman_mse", "absolute_error", "poisson"] = Field(
        default="squared_error",
        description="Function to measure split quality"
    )
    max_depth: int | None = Field(default=None, description="Maximum depth of trees (None=unlimited)")
    min_samples_split: int = Field(default=2, description="Minimum samples to split node", ge=2)
    min_samples_leaf: int = Field(default=1, description="Minimum samples at leaf node", ge=1)
    max_features: int | float | Literal["auto", "sqrt", "log2"] | None = Field(
        default=1.0,
        description="Number of features to consider for best split"
    )
    bootstrap: bool = Field(default=True, description="Whether to use bootstrap samples")
    n_jobs: int | None = Field(default=None, description="Number of parallel jobs (-1=all cores)")


# Parameter grid schema for batch training (GridSearchCV)
class RandomForestParamGrid(BaseModel):
    """Parameter grid for Random Forest Regression GridSearchCV"""
    n_estimators: List[int] = Field(
        default=[50, 100, 200],
        description="Number of trees values to try"
    )
    max_depth: List[int | None] = Field(
        default=[5, 10, None],
        description="Maximum depth values to try"
    )
    min_samples_split: List[int] = Field(
        default=[2, 5, 10],
        description="Minimum samples to split values to try"
    )
    min_samples_leaf: List[int] = Field(
        default=[1, 2, 4],
        description="Minimum samples at leaf values to try"
    )


class RandomForestRegression(
    RegressionModel[RandomForestRegressor, RandomForestParams, RandomForestParamGrid],
    param_grid=RandomForestParamGrid,
    model_param=RandomForestParams
):
    """
    Random Forest Regression - ensemble of decision trees

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: RandomForestParams) -> RandomForestRegressor:
        """
        Create Random Forest Regressor model instance

        Args:
            params: Validated Random Forest parameters

        Returns:
            Configured RandomForestRegressor model
        """
        return RandomForestRegressor(**params.model_dump(exclude_none=True))
