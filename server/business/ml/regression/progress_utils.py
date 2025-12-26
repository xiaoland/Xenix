"""
Progress tracking utilities for regression models.

This module provides shared utilities for tracking progress during hyperparameter tuning.
"""

from typing import Callable, Optional
from sklearn.metrics import mean_squared_error
from .base import ProgressInfo


def create_progress_scorer(progress_callback: Optional[Callable[[ProgressInfo], None]], total_fits: int):
    """
    Create a custom scorer that tracks and reports progress during GridSearchCV.
    
    Note: This scorer requires GridSearchCV to be run with n_jobs=1 to ensure
    sequential execution and accurate progress tracking. This is a trade-off
    between progress visibility and parallel execution performance.
    
    Args:
        progress_callback: Optional callback function for progress updates
        total_fits: Total number of model fits expected (param_combinations * cv_folds)
        
    Returns:
        A scorer function compatible with GridSearchCV
    """
    current_fit = [0]  # Use list to allow mutation in nested function
    
    def progress_scorer(estimator, X, y):
        """Custom scorer that reports progress"""
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
    
    return progress_scorer
