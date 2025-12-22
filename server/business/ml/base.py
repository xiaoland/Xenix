#!/usr/bin/env python3
"""
Base utilities for ML model handling.
"""
import importlib
from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from regression.base import RegressionModel


def import_model(model_name: str) -> Type['RegressionModel']:
    """
    Dynamically import model module and return the Model class.
    
    Args:
        model_name: Model name in dotted format (e.g., "regression.adaboost")
        
    Returns:
        The Model class from the imported module, type-cast to RegressionModel
        
    Raises:
        ImportError: If the model module cannot be found
        AttributeError: If the module doesn't have a Model attribute
    
    Example:
        >>> Model = import_model('regression.ridge')
        >>> result = Model.tune(X_train, y_train)
    """
    try:
        module = importlib.import_module(model_name)
        if not hasattr(module, 'Model'):
            raise AttributeError(f"Module '{model_name}' does not have a 'Model' attribute")
        return module.Model
    except ImportError as e:
        raise ImportError(f"Model module '{model_name}' not found: {e}")


# Keep the old function for backward compatibility during transition
def import_model_module(model_name: str):
    """
    Dynamically import model module.
    
    Args:
        model_name: Model name in dotted format (e.g., "regression.adaboost")
        
    Returns:
        The imported module
        
    Raises:
        ImportError: If the model module cannot be found
        
    Deprecated:
        Use import_model() instead to get the Model class directly
    """
    try:
        return importlib.import_module(model_name)
    except ImportError as e:
        raise ImportError(f"Model module '{model_name}' not found: {e}")
