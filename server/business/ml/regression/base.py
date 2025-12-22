"""
Abstract base class for regression models.

This module defines the common interface that all regression models must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Union, Optional
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.pipeline import Pipeline


class RegressionModel(ABC):
    """
    Abstract base class for regression models.
    
    All regression model modules should implement this interface to ensure
    consistency across different model implementations.
    """
    
    @staticmethod
    @abstractmethod
    def tune(X_train: pd.DataFrame, y_train: pd.Series) -> Dict[str, Any]:
        """
        Perform hyperparameter tuning for the regression model.
        
        Args:
            X_train: Training features as DataFrame
            y_train: Training target as Series
            
        Returns:
            Dictionary containing:
                - 'best_params': Best parameters found during tuning
                - 'best_score': Best cross-validation score
                - 'model': Trained model with best parameters
        """
        pass
    
    @staticmethod
    @abstractmethod
    def evaluate(model: Union[BaseEstimator, Pipeline], X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """
        Evaluate model performance on given data.
        
        Args:
            model: Trained model (sklearn Pipeline or estimator)
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
    def predict(model: Union[BaseEstimator, Pipeline], X: pd.DataFrame) -> pd.Series:
        """
        Make predictions using trained model.
        
        Args:
            model: Trained model (sklearn Pipeline or estimator)
            X: Features as DataFrame
            
        Returns:
            Predictions as Series with index matching X
        """
        pass
    
    @staticmethod
    @abstractmethod
    def create_model(params: Optional[Dict[str, Any]] = None) -> Union[BaseEstimator, Pipeline]:
        """
        Create a model instance with given parameters.
        
        Args:
            params: Model parameters (e.g., {'model__alpha': 1.0})
            
        Returns:
            Sklearn Pipeline or estimator with specified parameters
        """
        pass
