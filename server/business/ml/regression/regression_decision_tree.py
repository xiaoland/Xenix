"""
Regression Decision Tree Model Module
"""

import pandas as pd
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from typing import Dict, Any, Union, Optional, Callable
from pydantic import BaseModel
from sklearn.base import BaseEstimator

from .base import RegressionModel, ProgressInfo, TuneResult



class DecisionTreeParamGrid(BaseModel):
    """Parameter grid for DecisionTreeRegressionModel."""
    max_depth: list[int | None] = [5, 10, 20, None]
    min_samples_split: list[int] = [2, 5, 10]
    min_samples_leaf: list[int] = [1, 2, 4]


class DecisionTreeRegressionModel(RegressionModel[DecisionTreeRegressor, DecisionTreeParamGrid]):
    """DecisionTree Regression model implementation."""
    
    @staticmethod
    def tune(X_train: pd.DataFrame, y_train: pd.Series, param_grid: Optional[DecisionTreeParamGrid] = None, progress_callback: Optional[Callable[[ProgressInfo], None]] = None) -> TuneResult:
        base_model = DecisionTreeRegressor(random_state=42)
    
        # Use provided param_grid or default
        if param_grid is None:
            param_grid_dict = DecisionTreeParamGrid().model_dump()
        else:
            # Convert pydantic model to dict, excluding None values
            param_grid_dict = param_grid.model_dump(exclude_none=True)

        # Calculate total number of fits
        from sklearn.model_selection import ParameterGrid
        param_combinations = list(ParameterGrid(param_grid_dict))
        total_fits = len(param_combinations) * 5  # 5-fold CV
        
        # Create a custom scorer that tracks progress
        current_fit = [0]  # Use list to allow mutation in nested function
        
        def progress_scorer(estimator, X, y):
            """Custom scorer that reports progress"""
            from sklearn.metrics import mean_squared_error
            current_fit[0] += 1
            
            if progress_callback:
                percentage = (current_fit[0] / total_fits) * 100
                progress_callback({
                    'percentage': percentage,
                    'round': current_fit[0],
                    'total_rounds': total_fits,
                    'metrics': {},
                    'params': estimator.get_params()
                })
            
            # Return the actual score
            y_pred = estimator.predict(X)
            return -mean_squared_error(y, y_pred)
    
        grid_search = GridSearchCV(
            estimator=base_model,
            param_grid=param_grid_dict,
            cv=5,
            scoring=progress_scorer,
            n_jobs=1,  # Must be 1 to ensure sequential execution for progress tracking
            verbose=0
        )
    
        grid_search.fit(X_train, y_train)
    
        return {
            'best_params': grid_search.best_params_,
            'best_score': float(grid_search.best_score_),
            'model': grid_search.best_estimator_
        }


    
    @staticmethod
    def evaluate(model: DecisionTreeRegressor, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        y_pred = model.predict(X)
        return {
            'mse': float(mean_squared_error(y, y_pred)),
            'mae': float(mean_absolute_error(y, y_pred)),
            'r2': float(r2_score(y, y_pred))
        }


    
    @staticmethod
    def predict(model: DecisionTreeRegressor, X: pd.DataFrame) -> pd.Series:
        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index, name='predictions')


    
    @staticmethod
    def create_model(params: Optional[Dict[str, Any]] = None) -> DecisionTreeRegressor:
        model = DecisionTreeRegressor(random_state=42)
        if params:
            model.set_params(**params)
        return model


# Alias for the model class
Model = DecisionTreeRegressionModel
