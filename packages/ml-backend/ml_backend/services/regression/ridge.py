"""Ridge Regression model with Pydantic parameter schemas"""

from typing import List, Literal
from pydantic import BaseModel, Field
from sklearn.linear_model import Ridge

from .base import RegressionModel


# Parameter schema for single training
class RidgeParams(BaseModel):
    """Parameters for Ridge Regression"""
    alpha: float = Field(default=1.0, description="Regularization strength")
    solver: Literal["auto", "svd", "cholesky", "lsqr", "sparse_cg", "sag", "saga"] = Field(
        default="auto",
        description="Solver algorithm"
    )
    fit_intercept: bool = Field(default=True, description="Whether to calculate intercept")
    max_iter: int | None = Field(default=None, description="Maximum iterations for iterative solvers")
    tol: float = Field(default=0.0001, description="Tolerance for solver convergence")


# Parameter grid schema for batch training (GridSearchCV)
class RidgeParamGrid(BaseModel):
    """Parameter grid for Ridge Regression GridSearchCV"""
    alpha: List[float] = Field(
        default=[0.1, 1.0, 10.0, 100.0],
        description="Regularization strength values to try"
    )
    solver: List[Literal["auto", "svd", "cholesky"]] = Field(
        default=["auto", "svd", "cholesky"],
        description="Solver algorithms to try"
    )
    fit_intercept: List[bool] = Field(
        default=[True, False],
        description="Whether to calculate intercept"
    )


class RidgeRegression(
    RegressionModel[Ridge, RidgeParams, RidgeParamGrid],
    param_grid=RidgeParamGrid,
    model_param=RidgeParams
):
    """
    Ridge Regression with L2 regularization

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: RidgeParams) -> Ridge:
        """
        Create Ridge model instance

        Args:
            params: Validated Ridge parameters

        Returns:
            Configured Ridge model
        """
        return Ridge(**params.model_dump(exclude_none=True))
