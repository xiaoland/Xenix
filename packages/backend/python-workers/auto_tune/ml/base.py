#!/usr/bin/env python3
"""
Base utilities for ML model handling.
"""
import importlib
from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from regression.base import RegressionModel


def import_regression_model(model_name: str) -> Type['RegressionModel']:
    """
    Dynamically import regression model module and return the Model class.
    
    Args:
        model_name: Model name in dotted format (e.g., "regression.adaboost")
        
    Returns:
        The Model class from the imported module, type-cast to RegressionModel
        
    Raises:
        ImportError: If the model module cannot be found
        AttributeError: If the module doesn't have a Model attribute
        ValueError: If the model is not a regression model
    
    Example:
        >>> Model = import_regression_model('regression.ridge')
        >>> result = Model.tune(X_train, y_train)
    """
    # Validate that this is a regression model
    if not model_name.startswith('regression.'):
        raise ValueError(f"Model '{model_name}' is not a regression model. Use import_regression_model only for regression models.")
    
    try:
        module = importlib.import_module(model_name)
        if not hasattr(module, 'Model'):
            raise AttributeError(f"Module '{model_name}' does not have a 'Model' attribute")
        return module.Model
    except ImportError as e:
        raise ImportError(f"Model module '{model_name}' not found: {e}")


def import_model(model_name: str) -> Type:
    """
    Dynamically import model module and return the Model class.
    Generic function that delegates to specific import functions based on model type.
    
    Args:
        model_name: Model name in dotted format (e.g., "regression.adaboost", "classification.svm")
        
    Returns:
        The Model class from the imported module
        
    Raises:
        ImportError: If the model module cannot be found
        AttributeError: If the module doesn't have a Model attribute
        ValueError: If the model type is not recognized
    
    Example:
        >>> Model = import_model('regression.ridge')
        >>> result = Model.tune(X_train, y_train)
    """
    # Determine model type from prefix and delegate to appropriate function
    if model_name.startswith('regression.'):
        return import_regression_model(model_name)
    # Future: Add support for other model types
    # elif model_name.startswith('classification.'):
    #     return import_classification_model(model_name)
    # elif model_name.startswith('association.'):
    #     return import_association_model(model_name)
    else:
        raise ValueError(f"Unknown model type for '{model_name}'. Model name should start with a recognized prefix (e.g., 'regression.', 'classification.')")


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
