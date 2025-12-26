"""
Ridge Regression Model Module

This module provides tune, evaluate, and predict functions for Ridge regression.
All functions accept pandas DataFrames instead of file paths.
"""

from typing import Dict, Any, Union, Optional, Callable
from pydantic import BaseModel
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult
from .progress_utils import create_progress_scorer



class RidgeParamGrid(BaseModel):
    """Parameter grid for RidgeRegression."""
    model__alpha: list[float] = [0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0]


class RidgeRegression(RegressionModel[Pipeline, RidgeParamGrid]):
    """Ridge Regression model implementation."""
    
    @staticmethod
    def tune(X_train: pd.DataFrame, y_train: pd.Series, param_grid: Optional[RidgeParamGrid] = None, progress_callback: Optional[Callable[[ProgressInfo], None]] = None) -> TuneResult:
        """
        Perform hyperparameter tuning for Ridge regression.
        
        Args:
            X_train: Training features as DataFrame
            y_train: Training target as Series
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with 'best_params', 'best_score', and 'model'
        """
        # Define base pipeline model: Standardization + Ridge
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", Ridge(random_state=42))
        ])
        
        # Use provided param_grid or default
        if param_grid is None:
            param_grid_dict = RidgeParamGrid().model_dump()
        else:
            # Convert pydantic model to dict, excluding None values
            param_grid_dict = param_grid.model_dump(exclude_none=True)
        
        # Calculate total number of fits
        from sklearn.model_selection import ParameterGrid
        param_combinations = list(ParameterGrid(param_grid_dict))
        total_fits = len(param_combinations) * 5  # 5-fold CV
        
        # Create progress scorer
        progress_scorer = create_progress_scorer(progress_callback, total_fits)
        
        # Grid Search with 5-fold cross validation
        # Note: n_jobs=1 is required for progress tracking to work correctly
        grid_search = GridSearchCV(
            estimator=base_model,
            param_grid=param_grid_dict,
            cv=5,
            scoring=progress_scorer,
            n_jobs=1,
            verbose=0
        )
        
        # Run grid search
        grid_search.fit(X_train, y_train)
        
        return {
            'best_params': grid_search.best_params_,
            'best_score': float(grid_search.best_score_),
            'model': grid_search.best_estimator_
        }
    
    @staticmethod
    def evaluate(model: Pipeline, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """
        Evaluate model performance on given data.
        
        Args:
            model: Trained model (sklearn Pipeline or estimator)
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
    def predict(model: Pipeline, X: pd.DataFrame) -> pd.Series:
        """
        Make predictions using trained model.
        
        Args:
            model: Trained model (sklearn Pipeline or estimator)
            X: Features as DataFrame
            
        Returns:
            Predictions as Series
        """
        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index, name='predictions')
    
    @staticmethod
    def create_model(params: Optional[Dict[str, Any]] = None) -> Pipeline:
        """
        Create a Ridge model with given parameters.
        
        Args:
            params: Model parameters (e.g., {'model__alpha': 1.0})
            
        Returns:
            Sklearn Pipeline with StandardScaler and Ridge model
        """
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", Ridge(random_state=42))
        ])
        
        if params:
            model.set_params(**params)
        
        return model


# Alias for the model class
Model = RidgeRegression
