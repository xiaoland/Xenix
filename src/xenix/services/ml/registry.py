from __future__ import annotations

from ...exceptions import NotFoundError
from .models.association import ApyoriAssociationRulesService, MlxtendAssociationRulesService
from .models.anomaly import IsolationForestAnomalyService, LocalOutlierFactorAnomalyService
from .models.classification import (
    AdaBoostClassificationService,
    DecisionTreeClassificationService,
    GradientBoostingClassificationService,
    KNeighborsClassificationService,
    LightGBMClassificationService,
    LogisticRegressionService,
    NaiveBayesClassificationService,
    RandomForestClassificationService,
    XGBoostClassificationService,
)
from .models.clustering import DBSCANClusteringService, KMeansClusteringService
from .models.recommendation import ItemSimilarityRecommendationService
from .models.regression import (
    AdaBoostRegressionService,
    BayesianRidgeRegressionService,
    DecisionTreeRegressionService,
    GradientBoostingRegressionService,
    KNeighborsRegressionService,
    LassoRegressionService,
    LightGBMRegressionService,
    LinearRegressionService,
    PolynomialRegressionService,
    RandomForestRegressionService,
    RidgeRegressionService,
    XGBoostRegressionService,
)
from .types import ModelCatalogEntry, ModelServiceBase

_MODEL_SERVICES: dict[str, type[ModelServiceBase]] = {
    service.key: service
    for service in (
        LinearRegressionService,
        LassoRegressionService,
        RidgeRegressionService,
        BayesianRidgeRegressionService,
        KNeighborsRegressionService,
        DecisionTreeRegressionService,
        GradientBoostingRegressionService,
        AdaBoostRegressionService,
        XGBoostRegressionService,
        LightGBMRegressionService,
        PolynomialRegressionService,
        RandomForestRegressionService,
        LogisticRegressionService,
        NaiveBayesClassificationService,
        KNeighborsClassificationService,
        DecisionTreeClassificationService,
        GradientBoostingClassificationService,
        AdaBoostClassificationService,
        XGBoostClassificationService,
        LightGBMClassificationService,
        RandomForestClassificationService,
        KMeansClusteringService,
        DBSCANClusteringService,
        IsolationForestAnomalyService,
        LocalOutlierFactorAnomalyService,
        ApyoriAssociationRulesService,
        MlxtendAssociationRulesService,
        ItemSimilarityRecommendationService,
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
