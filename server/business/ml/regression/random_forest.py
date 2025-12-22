"""
Random Forest Model Module

This module provides tune, evaluate, and predict functions for Random Forest regression.
All functions accept pandas DataFrames instead of file paths.
"""

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score


def tune(X_train: pd.DataFrame, y_train: pd.Series) -> dict:
    """
    Perform hyperparameter tuning for Random Forest regression.
    
    Args:
        X_train: Training features as DataFrame
        y_train: Training target as Series
        
    Returns:
        dict with 'best_params' and 'best_score'
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


def evaluate(model, X: pd.DataFrame, y: pd.Series) -> dict:
    """
    Evaluate model performance on given data.
    
    Args:
        model: Trained model (sklearn estimator)
        X: Features as DataFrame
        y: Target as Series
        
    Returns:
        dict with MSE, MAE, and R2 scores
    """
    y_pred = model.predict(X)
    
    return {
        'mse': float(mean_squared_error(y, y_pred)),
        'mae': float(mean_absolute_error(y, y_pred)),
        'r2': float(r2_score(y, y_pred))
    }


def predict(model, X: pd.DataFrame) -> pd.Series:
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


def create_model(params: dict = None):
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
