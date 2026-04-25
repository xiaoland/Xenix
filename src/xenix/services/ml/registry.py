from __future__ import annotations

from ...exceptions import NotFoundError
from .models.classification import (
    DecisionTreeClassificationService,
    GradientBoostingClassificationService,
    LogisticRegressionService,
    RandomForestClassificationService,
)
from .models.clustering import DBSCANClusteringService, KMeansClusteringService
from .models.regression import (
    DecisionTreeRegressionService,
    GradientBoostingRegressionService,
    LassoRegressionService,
    LinearRegressionService,
    RandomForestRegressionService,
    RidgeRegressionService,
)
from .types import ModelCatalogEntry, ModelServiceBase

_MODEL_SERVICES: dict[str, type[ModelServiceBase]] = {
    service.key: service
    for service in (
        LinearRegressionService,
        LassoRegressionService,
        RidgeRegressionService,
        DecisionTreeRegressionService,
        GradientBoostingRegressionService,
        RandomForestRegressionService,
        LogisticRegressionService,
        DecisionTreeClassificationService,
        GradientBoostingClassificationService,
        RandomForestClassificationService,
        KMeansClusteringService,
        DBSCANClusteringService,
    )
}


def get_model_service(model_key: str) -> type[ModelServiceBase]:
    try:
        return _MODEL_SERVICES[model_key]
    except KeyError as exc:
        raise NotFoundError(f"Model '{model_key}' was not found.") from exc


def list_model_keys() -> list[str]:
    return sorted(_MODEL_SERVICES)


def list_model_catalog() -> list[ModelCatalogEntry]:
    return [get_model_service(model_key).catalog_entry() for model_key in list_model_keys()]


def get_model_catalog_entry(model_key: str) -> ModelCatalogEntry:
    return get_model_service(model_key).catalog_entry()
