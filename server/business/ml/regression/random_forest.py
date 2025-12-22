"""
Random Forest Model Module

This module provides tune, evaluate, and predict functions for Random Forest regression.
All functions accept pandas DataFrames instead of file paths.
"""

from typing import Dict, Any, Union, Optional, Callable
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.base import BaseEstimator

from .base import RegressionModel


class RandomForestRegressionModel(RegressionModel):
    """Random Forest Regression model implementation."""
    
    @staticmethod
    def tune(X_train: pd.DataFrame, y_train: pd.Series, progress_callback: Optional[Callable[[float, int, int, Dict[str, float], Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Perform hyperparameter tuning for Random Forest regression.
        
        Args:
            X_train: Training features as DataFrame
            y_train: Training target as Series
            
        Returns:
            Dictionary with 'best_params', 'best_score', and 'model'
        """
        base_model = RandomForestRegressor(random_state=42, n_jobs=-1)
        
        param_grid = {
            'n_estimators': [50, 100, 200],
            'max_depth': [5, 10, None],
            'min_samples_split': [2, 5]
        }
        
        grid_search = GridSearchCV(
            estimator=base_model,
            param_grid=param_grid,
            cv=5,
            scoring='neg_mean_squared_error',
            n_jobs=-1
        )
        
        grid_search.fit(X_train, y_train)
        
        return {
            'best_params': grid_search.best_params_,
            'best_score': float(grid_search.best_score_),
            'model': grid_search.best_estimator_
        }
    
    @staticmethod
    def evaluate(model: Union[BaseEstimator, RandomForestRegressor], X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """
        Evaluate model performance on given data.
        
        Args:
            model: Trained model (sklearn estimator)
            X: Features as DataFrame
            y: Target as Series
            
        Returns:
            Dictionary with MSE, MAE, and R2 scores
        """
        y_pred = model.predict(X)
        
        return {
            'mse': float(mean_squared_error(y, y_pred)),
            'mae': float(mean_absolute_error(y, y_pred)),
            'r2': float(r2_score(y, y_pred))
        }
    
    @staticmethod
    def predict(model: Union[BaseEstimator, RandomForestRegressor], X: pd.DataFrame) -> pd.Series:
        """
        Make predictions using trained model.
        
        Args:
            model: Trained model (sklearn estimator)
            X: Features as DataFrame
            
        Returns:
            Predictions as Series
        """
        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index, name='predictions')
    
    @staticmethod
    def create_model(params: Optional[Dict[str, Any]] = None) -> RandomForestRegressor:
        """
        Create a Random Forest model with given parameters.
        
        Args:
            params: Model parameters
            
        Returns:
            RandomForestRegressor model
        """
        model = RandomForestRegressor(random_state=42, n_jobs=-1)
        
        if params:
            model.set_params(**params)
        
        return model


# Alias for the model class
Model = RandomForestRegressionModel
