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

    def __init_subclass__(
        cls,
        param_grid: type["ParamGridType"] = None,
        model_param: type["ModelParamType"] = None,
        **kwargs
    ):
        """
        Hook to enforce schema registration when a concrete model class is defined.
        
        All concrete model classes must provide param_grid and model_param parameters
        when subclassing.
        
        Args:
            param_grid: The pydantic model class for parameter grids (with list fields)
            model_param: The pydantic model class for single parameters
        """
        super().__init_subclass__(**kwargs)
        
        # Store the parameter schemas as class variables
        if param_grid is not None:
            cls.__paramgrid__ = param_grid
        if model_param is not None:
            cls.__modelparam__ = model_param

    @staticmethod
    @abstractmethod
    def auto_tune(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        param_grid: Optional[ParamGridType] = None,
    ) -> TuneResult:
        """
        Perform hyperparameter tuning for the regression model.

        Args:
            X_train: Training features as DataFrame
            y_train: Training target as Series
            param_grid: Optional parameter grid as pydantic BaseModel instance
                If None, uses default parameter grid for the model

        Returns:
            Dictionary containing:
                - 'best_params': Best parameters found during tuning
                - 'best_score': Best score achieved
                - 'model': Trained model with best parameters
        """
        pass

    @classmethod
    def manual_tune(
        cls,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        params: Optional[ModelParamType] = None,
    ) -> Dict[str, Any]:
        """
        Evaludate the regression model with specific parameters.

        This is a concrete method that all regression models can use.
        It creates a model with the given parameters, and then evaluates on the given test data,
        and returns the model along with evaluation metrics.

        Args:
            X_test: Test features as DataFrame
            y_test: Test target as Series
            params: Model parameters as pydantic BaseModel instance
                If None, uses default parameters for the model

        Returns:
            Dictionary containing:
                - 'model': Trained model (ModelType)
                - 'metrics': Evaluation metrics on training data
        """
        # Create model with specified parameters
        model = cls.create_model(params)

        # Evaluate on training data
        metrics = cls.evaluate(model, X_test, y_test)

        return {
            "model": model,
            "metrics": metrics,
        }

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
