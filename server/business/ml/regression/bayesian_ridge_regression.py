"""
Bayesian Ridge Regression Model Module
"""

import pandas as pd
from sklearn.linear_model import BayesianRidge
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional
from sklearn.base import BaseEstimator

from .base import RegressionModel


class BayesianRidgeRegressionModel(RegressionModel):
    """BayesianRidge Regression model implementation."""
    
    @staticmethod
    def tune(X_train: pd.DataFrame, y_train: pd.Series) -> Dict[str, Any]:
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", BayesianRidge())
        ])
    
        param_grid = {
            'model__alpha_1': [1e-6, 1e-5, 1e-4],
            'model__alpha_2': [1e-6, 1e-5, 1e-4],
            'model__lambda_1': [1e-6, 1e-5, 1e-4],
            'model__lambda_2': [1e-6, 1e-5, 1e-4]
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
    def evaluate(model: Union[BaseEstimator, Pipeline], X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        y_pred = model.predict(X)
        return {
            'mse': float(mean_squared_error(y, y_pred)),
            'mae': float(mean_absolute_error(y, y_pred)),
            'r2': float(r2_score(y, y_pred))
        }


    
    @staticmethod
    def predict(model: Union[BaseEstimator, Pipeline], X: pd.DataFrame) -> pd.Series:
        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index, name='predictions')


    
    @staticmethod
    def create_model(params: Optional[Dict[str, Any]] = None) -> Pipeline:
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", BayesianRidge())
        ])
        if params:
            model.set_params(**params)
        return model


# Alias for the model class
Model = BayesianRidgeRegressionModel
