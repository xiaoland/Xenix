"""
Abstract base class for regression models.

This module defines the common interface that all regression models must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Union, Optional, Callable, TypeVar, Generic, TypedDict
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.pipeline import Pipeline


class ProgressInfo(TypedDict):
    """Progress information for hyperparameter tuning callbacks."""
    percentage: float
    round: int
    total_rounds: int
    metrics: Dict[str, float]
    params: Dict[str, Any]


# Type variable for model type
ModelType = TypeVar('ModelType', bound=Union[BaseEstimator, Pipeline])


class RegressionModel(ABC, Generic[ModelType]):
    """
    Abstract base class for regression models.
    
    All regression model modules should implement this interface to ensure
    consistency across different model implementations.
    
    Type Parameters:
        ModelType: The specific sklearn model type (Pipeline or BaseEstimator subclass)
    """
    
    @staticmethod
    @abstractmethod
    def tune(X_train: pd.DataFrame, y_train: pd.Series, progress_callback: Optional[Callable[[ProgressInfo], None]] = None) -> Dict[str, Any]:
        """
        Perform hyperparameter tuning for the regression model.
        
        Args:
            X_train: Training features as DataFrame
            y_train: Training target as Series
            progress_callback: Optional callback function for progress updates.
                Called with a ProgressInfo dict containing:
                - percentage: Progress percentage (0-100)
                - round: Current round/iteration number
                - total_rounds: Total number of rounds
                - metrics: Current metrics dictionary
                - params: Current parameters being evaluated
            
        Returns:
            Dictionary containing:
                - 'best_params': Best parameters found during tuning
                - 'best_score': Best cross-validation score
                - 'model': Trained model with best parameters
        """
        pass
    
    @staticmethod
    @abstractmethod
    def evaluate(model: ModelType, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """
        Evaluate model performance on given data.
        
        Args:
            model: Trained model (specific type based on ModelType)
            X: Features as DataFrame
            y: Target as Series
            
        Returns:
            Dictionary containing:
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
    def create_model(params: Optional[Dict[str, Any]] = None) -> ModelType:
        """
        Create a model instance with given parameters.
        
        Args:
            params: Model parameters (e.g., {'model__alpha': 1.0})
            
        Returns:
            Sklearn Pipeline or estimator with specified parameters (ModelType)
        """
        pass
