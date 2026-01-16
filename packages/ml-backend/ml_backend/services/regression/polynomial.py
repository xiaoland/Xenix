"""Polynomial Regression model with Pydantic parameter schemas"""

from typing import List
from pydantic import BaseModel, Field
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline

from .base import RegressionModel


# Parameter schema for single training
class PolynomialParams(BaseModel):
    """Parameters for Polynomial Regression"""
    degree: int = Field(default=2, description="Degree of polynomial features", ge=1, le=10)
    fit_intercept: bool = Field(default=True, description="Whether to calculate intercept")
    interaction_only: bool = Field(default=False, description="Only interaction features (no powers)")
    include_bias: bool = Field(default=True, description="Include bias column in polynomial features")


# Parameter grid schema for batch training (GridSearchCV)
class PolynomialParamGrid(BaseModel):
    """Parameter grid for Polynomial Regression GridSearchCV"""
    polynomialfeatures__degree: List[int] = Field(
        default=[2, 3, 4],
        description="Polynomial degree values to try"
    )
    linearregression__fit_intercept: List[bool] = Field(
        default=[True, False],
        description="Whether to calculate intercept"
    )


class PolynomialRegression(
    RegressionModel[Pipeline, PolynomialParams, PolynomialParamGrid],
    param_grid=PolynomialParamGrid,
    model_param=PolynomialParams
):
    """
    Polynomial Regression using sklearn Pipeline

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: PolynomialParams) -> Pipeline:
        """
        Create Polynomial Regression pipeline

        Args:
            params: Validated Polynomial parameters

        Returns:
            Configured Pipeline with PolynomialFeatures and LinearRegression
        """
        return Pipeline([
            ("polynomialfeatures", PolynomialFeatures(
                degree=params.degree,
                interaction_only=params.interaction_only,
                include_bias=params.include_bias
            )),
            ("linearregression", LinearRegression(
                fit_intercept=params.fit_intercept
            ))
        ])
