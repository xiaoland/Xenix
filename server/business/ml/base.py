#!/usr/bin/env python3
"""
Base utilities for ML model handling.
"""
import importlib


def import_model_module(model_name: str):
    """Dynamically import model module"""
    # Model name is already in dotted format (e.g., "regression.adaboost")
    try:
        return importlib.import_module(model_name)
    except ImportError as e:
        raise ImportError(f"Model module '{model_name}' not found: {e}")