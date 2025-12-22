"""
Linear Regression Model Module

This module provides tune, evaluate, and predict functions for Linear regression.
All functions accept pandas DataFrames instead of file paths.
"""

import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score


def tune(X_train: pd.DataFrame, y_train: pd.Series) -> dict:
    """
    Perform hyperparameter tuning for Linear regression.
    
    Args:
        X_train: Training features as DataFrame
        y_train: Training target as Series
        
    Returns:
        dict with 'best_params' and 'best_score'
    """
    base_model = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LinearRegression())
    ])
    
    param_grid = {
        'model__fit_intercept': [True, False],
        'model__copy_X': [True, False]
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
        model: Trained model (sklearn Pipeline or estimator)
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
        model: Trained model (sklearn Pipeline or estimator)
        X: Features as DataFrame
        
    Returns:
        Predictions as Series
    """
    predictions = model.predict(X)
    return pd.Series(predictions, index=X.index, name='predictions')


def create_model(params: dict = None):
    """
    Create a Linear Regression model with given parameters.
    
    Args:
        params: Model parameters
        
    Returns:
        Sklearn Pipeline with StandardScaler and LinearRegression model
    """
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LinearRegression())
    ])
    
    if params:
        model.set_params(**params)
    
    return model
