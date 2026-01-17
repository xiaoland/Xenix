"""Decision Tree Regression model with Pydantic parameter schemas"""

from typing import List, Literal
from pydantic import BaseModel, Field
from sklearn.tree import DecisionTreeRegressor

from .base import RegressionModel


# Parameter schema for single training
class DecisionTreeParams(BaseModel):
    """Parameters for Decision Tree Regression"""
    criterion: Literal["squared_error", "friedman_mse", "absolute_error", "poisson"] = Field(
        default="squared_error",
        description="Function to measure split quality"
    )
    splitter: Literal["best", "random"] = Field(
        default="best",
        description="Strategy to split at each node"
    )
    max_depth: int | None = Field(default=5, description="Maximum depth of tree (None=unlimited)")
    min_samples_split: int = Field(default=2, description="Minimum samples to split node", ge=2)
    min_samples_leaf: int = Field(default=1, description="Minimum samples at leaf node", ge=1)
    max_features: int | float | Literal["auto", "sqrt", "log2"] | None = Field(
        default=None,
        description="Number of features to consider for best split"
    )


# Parameter grid schema for batch training (GridSearchCV)
class DecisionTreeParamGrid(BaseModel):
    """Parameter grid for Decision Tree Regression GridSearchCV"""
    max_depth: List[int | None] = Field(
        default=[3, 5, 7, 10, None],
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


class DecisionTreeRegression(
    RegressionModel[DecisionTreeRegressor, DecisionTreeParams, DecisionTreeParamGrid],
    param_grid=DecisionTreeParamGrid,
    model_param=DecisionTreeParams
):
    """
    Decision Tree Regression

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: DecisionTreeParams) -> DecisionTreeRegressor:
        """
        Create Decision Tree Regressor model instance

        Args:
            params: Validated Decision Tree parameters

        Returns:
            Configured DecisionTreeRegressor model
        """
        return DecisionTreeRegressor(**params.model_dump(exclude_none=True))
