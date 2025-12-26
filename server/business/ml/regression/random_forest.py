"""
Random Forest Model Module

This module provides tune, evaluate, and predict functions for Random Forest regression.
All functions accept pandas DataFrames instead of file paths.
"""

from typing import Dict, Any, Union, Optional, Callable
from pydantic import BaseModel
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult
from .progress_utils import create_progress_scorer



class RandomForestParamGrid(BaseModel):
    """Parameter grid for RandomForestRegressionModel."""
    n_estimators: list[int] = [50, 100, 200]
    max_depth: list[int | None] = [5, 10, None]
    min_samples_split: list[int] = [2, 5]


class RandomForestRegressionModel(RegressionModel[RandomForestRegressor, RandomForestParamGrid]):
    """Random Forest Regression model implementation."""
    
    @staticmethod
    def tune(X_train: pd.DataFrame, y_train: pd.Series, param_grid: Optional[RandomForestParamGrid] = None, progress_callback: Optional[Callable[[ProgressInfo], None]] = None) -> TuneResult:
        """
        Perform hyperparameter tuning for Random Forest regression.
        
        Args:
            X_train: Training features as DataFrame
            y_train: Training target as Series
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with 'best_params', 'best_score', and 'model'
        """
        base_model = RandomForestRegressor(random_state=42, n_jobs=-1)
        
        # Use provided param_grid or default
        if param_grid is None:
            param_grid_dict = RandomForestParamGrid().model_dump()
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
            n_jobs=1,  # Required for progress tracking
            verbose=0
        )
        
        grid_search.fit(X_train, y_train)
        
        return {
            'best_params': grid_search.best_params_,
            'best_score': float(grid_search.best_score_),
            'model': grid_search.best_estimator_
        }
    
    @staticmethod
    def evaluate(model: RandomForestRegressor, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
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
    def predict(model: RandomForestRegressor, X: pd.DataFrame) -> pd.Series:
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
