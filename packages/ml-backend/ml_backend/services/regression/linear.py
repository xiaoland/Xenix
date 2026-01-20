"""Linear Regression model with Pydantic parameter schemas"""

from typing import List
from pydantic import BaseModel, Field
from sklearn.linear_model import LinearRegression

from .base import RegressionModel


# Parameter schema for single training
class LinearParams(BaseModel):
    """Parameters for Linear Regression"""
    fit_intercept: bool = Field(default=True, description="Whether to calculate intercept")
    copy_X: bool = Field(default=True, description="Whether to copy X (True) or overwrite")
    n_jobs: int | None = Field(default=None, description="Number of jobs for computation")
    positive: bool = Field(default=False, description="Force coefficients to be positive")


# Parameter grid schema for batch training (GridSearchCV)
class LinearParamGrid(BaseModel):
    """Parameter grid for Linear Regression GridSearchCV"""
    fit_intercept: List[bool] = Field(
        default=[True, False],
        description="Whether to calculate intercept"
    )
    positive: List[bool] = Field(
        default=[True, False],
        description="Force coefficients to be positive"
    )


class LinearRegressionModel(
    RegressionModel[LinearRegression, LinearParams, LinearParamGrid],
    param_grid=LinearParamGrid,
    model_param=LinearParams
):
    """
    Linear Regression (OLS - Ordinary Least Squares)

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: LinearParams) -> LinearRegression:
        """
        Create Linear Regression model instance

        Args:
            params: Validated Linear Regression parameters

        Returns:
            Configured LinearRegression model
        """
        return LinearRegression(**params.model_dump(exclude_none=True))
