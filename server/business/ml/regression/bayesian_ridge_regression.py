"""
Bayesian Ridge Regression Model Module
"""

import pandas as pd
from sklearn.linear_model import BayesianRidge
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable
from pydantic import BaseModel
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult
from .progress_utils import create_progress_scorer



class BayesianRidgeParamGrid(BaseModel):
    """Parameter grid for BayesianRidgeRegressionModel."""
    model__alpha_1: list[float] = [1e-6, 1e-5, 1e-4]
    model__alpha_2: list[float] = [1e-6, 1e-5, 1e-4]


class BayesianRidgeRegressionModel(RegressionModel[Pipeline, BayesianRidgeParamGrid]):
    """BayesianRidge Regression model implementation."""
    
    @staticmethod
    def tune(X_train: pd.DataFrame, y_train: pd.Series, param_grid: Optional[BayesianRidgeParamGrid] = None, progress_callback: Optional[Callable[[ProgressInfo], None]] = None) -> TuneResult:
        base_model = Pipeline([
            ("scaler", StandardScaler()),
            ("model", BayesianRidge())
        ])
    
        # Use provided param_grid or default
        if param_grid is None:
            param_grid_dict = BayesianRidgeParamGrid().model_dump()
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
    def evaluate(model: Pipeline, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        y_pred = model.predict(X)
        return {
            'mse': float(mean_squared_error(y, y_pred)),
            'mae': float(mean_absolute_error(y, y_pred)),
            'r2': float(r2_score(y, y_pred))
        }


    
    @staticmethod
    def predict(model: Pipeline, X: pd.DataFrame) -> pd.Series:
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
