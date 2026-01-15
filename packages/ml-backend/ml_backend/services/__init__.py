"""ML Services - regression and classification models"""

from .regression import (
    REGRESSION_MODELS,
    get_regression_model,
    list_regression_models
)
from .classification import (
    CLASSIFICATION_MODELS,
    get_classification_model,
    list_classification_models
)


# Combined model registry
ALL_MODELS = {
    **REGRESSION_MODELS,
    **CLASSIFICATION_MODELS
}


def get_model(model_name: str):
    """
    Get model instance by name

    Args:
        model_name: Model identifier (e.g., 'regression.ridge', 'classification.logistic_regression')

    Returns:
        Model instance

    Raises:
        ValueError: If model name is unknown
    """
    # Determine service type from model name
    if model_name.startswith("regression."):
        return get_regression_model(model_name)
    elif model_name.startswith("classification."):
        return get_classification_model(model_name)
    else:
        raise ValueError(
            f"Unknown model: {model_name}. "
            f"Model name must start with 'regression.' or 'classification.'"
        )


def list_models():
    """Get list of all available model names"""
    return list(ALL_MODELS.keys())


__all__ = [
    "ALL_MODELS",
    "REGRESSION_MODELS",
    "CLASSIFICATION_MODELS",
    "get_model",
    "get_regression_model",
    "get_classification_model",
    "list_models",
    "list_regression_models",
    "list_classification_models",
]
