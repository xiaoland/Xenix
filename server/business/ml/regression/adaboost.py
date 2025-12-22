"""
AdaBoost Model Module
"""

import pandas as pd
from sklearn.ensemble import AdaBoostRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score


def tune(X_train: pd.DataFrame, y_train: pd.Series) -> dict:
    base_model = AdaBoostRegressor(
        estimator=DecisionTreeRegressor(max_depth=3),
        random_state=42
    )
    
    param_grid = {
        'n_estimators': [50, 100, 150],
        'learning_rate': [0.01, 0.1, 1.0],
        'estimator__max_depth': [3, 5, 7]
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
    estimator_depth = 3
    if params and 'estimator__max_depth' in params:
        estimator_depth = params.pop('estimator__max_depth')
    
    model = AdaBoostRegressor(
        estimator=DecisionTreeRegressor(max_depth=estimator_depth),
        random_state=42
    )
    if params:
        model.set_params(**params)
    return model
