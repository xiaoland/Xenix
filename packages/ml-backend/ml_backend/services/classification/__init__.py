"""Classification service"""

from .logistic_regression import LogisticRegressionClassifier
from .random_forest import RandomForestClassification


# Model registry: maps model names to model classes
CLASSIFICATION_MODELS = {
    "classification.logistic_regression": LogisticRegressionClassifier,
    "classification.random_forest": RandomForestClassification,
}


def get_classification_model(model_name: str):
    """
    Get classification model instance by name

    Args:
        model_name: Model identifier (e.g., 'classification.logistic_regression')

    Returns:
        Model instance

    Raises:
        ValueError: If model name is unknown
    """
    if model_name not in CLASSIFICATION_MODELS:
        raise ValueError(
            f"Unknown classification model: {model_name}. "
            f"Available models: {', '.join(CLASSIFICATION_MODELS.keys())}"
        )

    model_class = CLASSIFICATION_MODELS[model_name]
    return model_class()


def list_classification_models():
    """Get list of available classification model names"""
    return list(CLASSIFICATION_MODELS.keys())


__all__ = [
    "CLASSIFICATION_MODELS",
    "get_classification_model",
    "list_classification_models",
    "LogisticRegressionClassifier",
    "RandomForestClassification",
]
