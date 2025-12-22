#!/usr/bin/env python3
"""
Base utilities for ML model handling.
"""
import importlib
from types import ModuleType


def import_model_module(model_name: str) -> ModuleType:
    """
    Dynamically import model module.
    
    Args:
        model_name: Model name in dotted format (e.g., "regression.adaboost")
        
    Returns:
        The imported module
        
    Raises:
        ImportError: If the model module cannot be found
    """
    # Model name is already in dotted format (e.g., "regression.adaboost")
    try:
        return importlib.import_module(model_name)
    except ImportError as e:
        raise ImportError(f"Model module '{model_name}' not found: {e}")
