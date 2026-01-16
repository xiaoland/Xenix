"""Bayesian Ridge Regression model with Pydantic parameter schemas"""

from typing import List
from pydantic import BaseModel, Field
from sklearn.linear_model import BayesianRidge

from .base import RegressionModel


# Parameter schema for single training
class BayesianRidgeParams(BaseModel):
    """Parameters for Bayesian Ridge Regression"""
    alpha_1: float = Field(default=1e-6, description="Hyperparameter for Gamma distribution prior over alpha")
    alpha_2: float = Field(default=1e-6, description="Hyperparameter for Gamma distribution prior over alpha")
    lambda_1: float = Field(default=1e-6, description="Hyperparameter for Gamma distribution prior over lambda")
    lambda_2: float = Field(default=1e-6, description="Hyperparameter for Gamma distribution prior over lambda")
    n_iter: int = Field(default=300, description="Maximum number of iterations")
    tol: float = Field(default=0.001, description="Tolerance for stopping criterion")
    fit_intercept: bool = Field(default=True, description="Whether to calculate intercept")
    compute_score: bool = Field(default=False, description="Whether to compute log marginal likelihood")


# Parameter grid schema for batch training (GridSearchCV)
class BayesianRidgeParamGrid(BaseModel):
    """Parameter grid for Bayesian Ridge Regression GridSearchCV"""
    alpha_1: List[float] = Field(
        default=[1e-6, 1e-5, 1e-4],
        description="Hyperparameter values for alpha prior"
    )
    alpha_2: List[float] = Field(
        default=[1e-6, 1e-5, 1e-4],
        description="Hyperparameter values for alpha prior"
    )
    lambda_1: List[float] = Field(
        default=[1e-6, 1e-5, 1e-4],
        description="Hyperparameter values for lambda prior"
    )
    lambda_2: List[float] = Field(
        default=[1e-6, 1e-5, 1e-4],
        description="Hyperparameter values for lambda prior"
    )


class BayesianRidgeRegression(
    RegressionModel[BayesianRidge, BayesianRidgeParams, BayesianRidgeParamGrid],
    param_grid=BayesianRidgeParamGrid,
    model_param=BayesianRidgeParams
):
    """
    Bayesian Ridge Regression with probabilistic interpretation

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: BayesianRidgeParams) -> BayesianRidge:
        """
        Create Bayesian Ridge model instance

        Args:
            params: Validated Bayesian Ridge parameters

        Returns:
            Configured BayesianRidge model
        """
        return BayesianRidge(**params.model_dump(exclude_none=True))
