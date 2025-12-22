"""
K-Nearest Neighbors Model Module
"""

import pandas as pd
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional
from sklearn.base import BaseEstimator

from .base import RegressionModel


class KNNRegressionModel(RegressionModel):
    """KNN Regression model implementation."""
    
    @staticmethod
    def tune(X_train: pd.DataFrame, y_train: pd.Series) -> Dict[str, Any]:
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", KNeighborsRegressor())
        ])
    
        param_grid = {
            'model__n_neighbors': [3, 5, 7, 9, 11],
            'model__weights': ['uniform', 'distance']
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
            ("model", KNeighborsRegressor())
        ])
        if params:
            model.set_params(**params)
        return model


# Provide module-level functions for backward compatibility
def tune(X_train: pd.DataFrame, y_train: pd.Series) -> Dict[str, Any]:
    """Module-level tune function for backward compatibility."""
    return KNNRegressionModel.tune(X_train, y_train)


def evaluate(model: Union[BaseEstimator, Pipeline], X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
    """Module-level evaluate function for backward compatibility."""
    return KNNRegressionModel.evaluate(model, X, y)


def predict(model: Union[BaseEstimator, Pipeline], X: pd.DataFrame) -> pd.Series:
    """Module-level predict function for backward compatibility."""
    return KNNRegressionModel.predict(model, X)


def create_model(params: Optional[Dict[str, Any]] = None) -> Pipeline:
    """Module-level create_model function for backward compatibility."""
    return KNNRegressionModel.create_model(params)
