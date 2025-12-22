"""
Polynomial Regression Model Module
"""

import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional
from sklearn.base import BaseEstimator

from .base import RegressionModel


class PolynomialRegressionModel(RegressionModel):
    """Polynomial Regression model implementation."""
    
    @staticmethod
    def tune(X_train: pd.DataFrame, y_train: pd.Series) -> Dict[str, Any]:
        base_model = Pipeline([
            ("poly", PolynomialFeatures(degree=2, include_bias=False)),
            ("scaler", StandardScaler()),
            ("model", LinearRegression())
        ])
    
        param_grid = {
            'poly__degree': [2, 3, 4]
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
        poly_degree = 2
        if params and 'poly__degree' in params:
            poly_degree = params.get('poly__degree', 2)
    
        model = Pipeline([
            ("poly", PolynomialFeatures(degree=poly_degree, include_bias=False)),
            ("scaler", StandardScaler()),
            ("model", LinearRegression())
        ])
    
        if params:
            model.set_params(**params)
    
        return model


# Provide module-level functions for backward compatibility
def tune(X_train: pd.DataFrame, y_train: pd.Series) -> Dict[str, Any]:
    """Module-level tune function for backward compatibility."""
    return PolynomialRegressionModel.tune(X_train, y_train)


def evaluate(model: Union[BaseEstimator, Pipeline], X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
    """Module-level evaluate function for backward compatibility."""
    return PolynomialRegressionModel.evaluate(model, X, y)


def predict(model: Union[BaseEstimator, Pipeline], X: pd.DataFrame) -> pd.Series:
    """Module-level predict function for backward compatibility."""
    return PolynomialRegressionModel.predict(model, X)


def create_model(params: Optional[Dict[str, Any]] = None) -> Pipeline:
    """Module-level create_model function for backward compatibility."""
    return PolynomialRegressionModel.create_model(params)
