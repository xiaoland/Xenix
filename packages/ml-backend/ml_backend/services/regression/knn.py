"""K-Nearest Neighbors Regression model with Pydantic parameter schemas"""

from typing import List, Literal
from pydantic import BaseModel, Field
from sklearn.neighbors import KNeighborsRegressor

from .base import RegressionModel


# Parameter schema for single training
class KNNParams(BaseModel):
    """Parameters for K-Nearest Neighbors Regression"""
    n_neighbors: int = Field(default=5, description="Number of neighbors to use", ge=1)
    weights: Literal["uniform", "distance"] = Field(
        default="uniform",
        description="Weight function (uniform or distance-based)"
    )
    algorithm: Literal["auto", "ball_tree", "kd_tree", "brute"] = Field(
        default="auto",
        description="Algorithm to compute nearest neighbors"
    )
    leaf_size: int = Field(default=30, description="Leaf size for tree algorithms", ge=1)
    p: int = Field(default=2, description="Power parameter for Minkowski metric (1=Manhattan, 2=Euclidean)", ge=1)


# Parameter grid schema for batch training (GridSearchCV)
class KNNParamGrid(BaseModel):
    """Parameter grid for K-Nearest Neighbors Regression GridSearchCV"""
    n_neighbors: List[int] = Field(
        default=[3, 5, 7, 9],
        description="Number of neighbors values to try"
    )
    weights: List[Literal["uniform", "distance"]] = Field(
        default=["uniform", "distance"],
        description="Weight functions to try"
    )
    algorithm: List[Literal["auto", "ball_tree", "kd_tree"]] = Field(
        default=["auto", "ball_tree", "kd_tree"],
        description="Algorithms to try"
    )


class KNNRegression(
    RegressionModel[KNeighborsRegressor, KNNParams, KNNParamGrid],
    param_grid=KNNParamGrid,
    model_param=KNNParams
):
    """
    K-Nearest Neighbors Regression

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: KNNParams) -> KNeighborsRegressor:
        """
        Create KNN Regressor model instance

        Args:
            params: Validated KNN parameters

        Returns:
            Configured KNeighborsRegressor model
        """
        return KNeighborsRegressor(**params.model_dump(exclude_none=True))
