"""Logistic Regression classification model with Pydantic parameter schemas"""

from typing import List, Literal
from pydantic import BaseModel, Field
from sklearn.linear_model import LogisticRegression

from .base import ClassificationModel


# Parameter schema for single training
class LogisticRegressionParams(BaseModel):
    """Parameters for Logistic Regression Classification"""
    C: float = Field(default=1.0, description="Inverse of regularization strength", gt=0)
    penalty: Literal["l1", "l2", "elasticnet", "none"] = Field(
        default="l2",
        description="Penalty norm type"
    )
    solver: Literal["lbfgs", "liblinear", "newton-cg", "newton-cholesky", "sag", "saga"] = Field(
        default="lbfgs",
        description="Optimization algorithm"
    )
    max_iter: int = Field(default=1000, description="Maximum number of iterations", ge=1)
    fit_intercept: bool = Field(default=True, description="Whether to calculate intercept")


# Parameter grid schema for batch training (GridSearchCV)
class LogisticRegressionParamGrid(BaseModel):
    """Parameter grid for Logistic Regression GridSearchCV"""
    C: List[float] = Field(
        default=[0.1, 1.0, 10.0, 100.0],
        description="Regularization strength values to try"
    )
    solver: List[Literal["lbfgs", "liblinear"]] = Field(
        default=["lbfgs", "liblinear"],
        description="Solvers to try"
    )
    penalty: List[Literal["l2"]] = Field(
        default=["l2"],
        description="Penalty types to try"
    )


class LogisticRegressionClassifier(
    ClassificationModel[LogisticRegression, LogisticRegressionParams, LogisticRegressionParamGrid],
    param_grid=LogisticRegressionParamGrid,
    model_param=LogisticRegressionParams
):
    """
    Logistic Regression Classifier

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: LogisticRegressionParams) -> LogisticRegression:
        """
        Create Logistic Regression model instance

        Args:
            params: Validated Logistic Regression parameters

        Returns:
            Configured LogisticRegression model
        """
        return LogisticRegression(**params.model_dump(exclude_none=True))
