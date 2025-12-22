"""
LightGBM Model Module
"""

import pandas as pd
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

try:
    from lightgbm import LGBMRegressor
except ImportError:
    raise ImportError("LightGBM is not installed. Please install it with: pip install lightgbm")


def tune(X_train: pd.DataFrame, y_train: pd.Series) -> dict:
    base_model = LGBMRegressor(
        objective="regression",
        random_state=42,
        n_jobs=-1,
        verbose=-1,
        verbosity=-1
    )
    
    param_grid = {
        'n_estimators': [50, 100, 150],
        'learning_rate': [0.01, 0.1, 0.2],
        'max_depth': [3, 5, 7]
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
    y_pred = model.predict(X)
    return {
        'mse': float(mean_squared_error(y, y_pred)),
        'mae': float(mean_absolute_error(y, y_pred)),
        'r2': float(r2_score(y, y_pred))
    }


def predict(model, X: pd.DataFrame) -> pd.Series:
    predictions = model.predict(X)
    return pd.Series(predictions, index=X.index, name='predictions')


def create_model(params: dict = None):
    model = LGBMRegressor(
        objective="regression",
        random_state=42,
        n_jobs=-1,
        verbose=-1,
        verbosity=-1
    )
    if params:
        model.set_params(**params)
    return model
