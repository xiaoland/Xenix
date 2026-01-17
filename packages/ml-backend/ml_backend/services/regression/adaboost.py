"""AdaBoost Regression model with Pydantic parameter schemas"""

from typing import List, Literal
from pydantic import BaseModel, Field
from sklearn.ensemble import AdaBoostRegressor

from .base import RegressionModel


# Parameter schema for single training
class AdaBoostParams(BaseModel):
    """Parameters for AdaBoost Regression"""
    n_estimators: int = Field(default=50, description="Number of boosting stages", ge=1)
    learning_rate: float = Field(default=1.0, description="Weight applied at each boosting iteration", gt=0)
    loss: Literal["linear", "square", "exponential"] = Field(
        default="linear",
        description="Loss function to use when updating weights"
    )


# Parameter grid schema for batch training (GridSearchCV)
class AdaBoostParamGrid(BaseModel):
    """Parameter grid for AdaBoost Regression GridSearchCV"""
    n_estimators: List[int] = Field(
        default=[50, 100, 200],
        description="Number of boosting stages to try"
    )
    learning_rate: List[float] = Field(
        default=[0.01, 0.1, 1.0],
        description="Learning rate values to try"
    )
    loss: List[Literal["linear", "square", "exponential"]] = Field(
        default=["linear", "square", "exponential"],
        description="Loss functions to try"
    )


class AdaBoostRegression(
    RegressionModel[AdaBoostRegressor, AdaBoostParams, AdaBoostParamGrid],
    param_grid=AdaBoostParamGrid,
    model_param=AdaBoostParams
):
    """
    AdaBoost Regression - adaptive boosting ensemble

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: AdaBoostParams) -> AdaBoostRegressor:
        """
        Create AdaBoost Regressor model instance

        Args:
            params: Validated AdaBoost parameters

        Returns:
            Configured AdaBoostRegressor model
        """
        return AdaBoostRegressor(**params.model_dump(exclude_none=True))
