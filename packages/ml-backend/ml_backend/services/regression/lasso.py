"""Lasso Regression model with Pydantic parameter schemas"""

from typing import List, Literal
from pydantic import BaseModel, Field
from sklearn.linear_model import Lasso

from .base import RegressionModel


# Parameter schema for single training
class LassoParams(BaseModel):
    """Parameters for Lasso Regression"""
    alpha: float = Field(default=1.0, description="Regularization strength (L1 penalty)")
    selection: Literal["cyclic", "random"] = Field(
        default="cyclic",
        description="Algorithm to use in coordinate descent"
    )
    fit_intercept: bool = Field(default=True, description="Whether to calculate intercept")
    max_iter: int = Field(default=1000, description="Maximum number of iterations")
    tol: float = Field(default=0.0001, description="Tolerance for optimization")


# Parameter grid schema for batch training (GridSearchCV)
class LassoParamGrid(BaseModel):
    """Parameter grid for Lasso Regression GridSearchCV"""
    alpha: List[float] = Field(
        default=[0.1, 1.0, 10.0, 100.0],
        description="Regularization strength values to try"
    )
    selection: List[Literal["cyclic", "random"]] = Field(
        default=["cyclic", "random"],
        description="Algorithms to try"
    )
    fit_intercept: List[bool] = Field(
        default=[True, False],
        description="Whether to calculate intercept"
    )


class LassoRegression(
    RegressionModel[Lasso, LassoParams, LassoParamGrid],
    param_grid=LassoParamGrid,
    model_param=LassoParams
):
    """
    Lasso Regression with L1 regularization

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: LassoParams) -> Lasso:
        """
        Create Lasso model instance

        Args:
            params: Validated Lasso parameters

        Returns:
            Configured Lasso model
        """
        return Lasso(**params.model_dump(exclude_none=True))
