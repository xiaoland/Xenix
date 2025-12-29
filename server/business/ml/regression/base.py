"""
Abstract base class for regression models.

This module defines the common interface that all regression models must implement.
"""

from abc import ABC, abstractmethod
from typing import (
    Dict,
    Any,
    Union,
    Optional,
    Callable,
    TypeVar,
    Generic,
    TypedDict,
    List,
)
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.pipeline import Pipeline
from pydantic import BaseModel


class ProgressInfo(TypedDict):
    """Progress information for hyperparameter tuning callbacks."""

    percentage: float
    round: int
    total_rounds: int
    metrics: Dict[str, float]
    params: Dict[str, Any]


class TuneResult(TypedDict):
    """Result of model tuning."""

    best_params: Dict[str, Any]
    best_score: float
    model: Union[BaseEstimator, Pipeline]


# Type variable for model type
ModelType = TypeVar("ModelType", bound=Union[BaseEstimator, Pipeline])

# Type variable for parameter type
ModelParamType = TypeVar("ModelParamType", bound=BaseModel)

# Type variable for parameter grid type
ParamGridType = TypeVar("ParamGridType", bound=BaseModel)


class RegressionModel(ABC, Generic[ModelType, ModelParamType, ParamGridType]):
    """
    Abstract base class for regression models.

    All regression model modules should implement this interface to ensure
    consistency across different model implementations.

    Type Parameters:
        ModelType: The specific sklearn model type (Pipeline or BaseEstimator subclass)
        ModelParamType: The parameter model type (pydantic BaseModel subclass)
        ParamGridType: The parameter grid model type (pydantic BaseModel subclass with list fields)
    """

    @staticmethod
    @abstractmethod
    def tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[ParamGridType] = None,
        upd_pg: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> TuneResult:
        """
        Perform hyperparameter tuning for the regression model.

        Args:
            X_train: Training features as DataFrame
            y_train: Training target as Series
            param_grid: Optional parameter grid as pydantic BaseModel instance
                If None, uses default parameter grid for the model
            upd_pg: Optional callback function for progress updates.
                Called with a ProgressInfo dict containing:
                - percentage: Progress percentage (0-100)
                - round: Current round/iteration number
                - total_rounds: Total number of rounds
                - metrics: Current metrics dictionary
                - params: Current parameters being evaluated

        Returns:
            Dictionary containing:
                - 'best_params': Best parameters found during tuning
                - 'model': Trained model with best parameters
        """
        pass

    @staticmethod
    @abstractmethod
    def evaluate(model: ModelType, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """
        Evaluate model performance on given data.

        Args:
            model: Trained model (specific type based on ModelType)
            X: Features as DataFrame
            y: Target as Series

        Returns:
            A Dictionary of metrics, suggested keys:
                - 'mse': Mean Squared Error
                - 'mae': Mean Absolute Error
                - 'r2': R-squared score
        """
        pass

    @staticmethod
    @abstractmethod
    def predict(model: ModelType, X: pd.DataFrame) -> pd.Series:
        """
        Make predictions using trained model.

        Args:
            model: Trained model (specific type based on ModelType)
            X: Features as DataFrame

        Returns:
            Predictions as Series with index matching X
        """
        pass

    @staticmethod
    @abstractmethod
    def create_model(params: Optional[ModelParamType] = None) -> ModelType:
        """
        Create a model instance with given parameters.

        Args:
            params: Model parameters as pydantic BaseModel instance

        Returns:
            Sklearn Pipeline or estimator with specified parameters (ModelType)
        """
        pass
