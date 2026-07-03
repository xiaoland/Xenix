from __future__ import annotations

from ...exceptions import NotFoundError
from .models.association import ApyoriAssociationRulesService, MlxtendAssociationRulesService
from .models.anomaly import IsolationForestAnomalyService, LocalOutlierFactorAnomalyService
from .models.classification import (
    AdaBoostClassificationService,
    CalibratedLinearSVCClassificationService,
    DecisionTreeClassificationService,
    ExtraTreesClassificationService,
    GradientBoostingClassificationService,
    HistGradientBoostingClassificationService,
    KNeighborsClassificationService,
    LabelPropagationClassificationService,
    LabelSpreadingClassificationService,
    LightGBMClassificationService,
    LogisticRegressionService,
    MLPClassificationService,
    MultinomialNBClassificationService,
    NaiveBayesClassificationService,
    RandomForestClassificationService,
    SelfTrainingClassificationService,
    SVCClassificationService,
    XGBoostClassificationService,
)
from .models.clustering import (
    BirchClusteringService,
    DBSCANClusteringService,
    GaussianMixtureClusteringService,
    KMeansClusteringService,
    MiniBatchKMeansClusteringService,
)
from .models.recommendation import ItemSimilarityRecommendationService
from .models.regression import (
    AdaBoostRegressionService,
    BayesianRidgeRegressionService,
    DecisionTreeRegressionService,
    ElasticNetRegressionService,
    GradientBoostingRegressionService,
    HistGradientBoostingRegressionService,
    KNeighborsRegressionService,
    LassoRegressionService,
    LightGBMRegressionService,
    LinearRegressionService,
    MLPRegressionService,
    PolynomialRegressionService,
    RandomForestRegressionService,
    RidgeRegressionService,
    SVRRegressionService,
    XGBoostRegressionService,
)
from .models.text_analysis import (
    TokenizedTextClassificationService,
    TokenizedTextClusteringService,
    TokenizedTextSimilarityService,
    TokenizedTextTopicModelingService,
)
from .types import ModelCatalogEntry, ModelServiceBase

_MODEL_SERVICES: dict[str, type[ModelServiceBase]] = {
    service.key: service
    for service in (
        LinearRegressionService,
        LassoRegressionService,
        ElasticNetRegressionService,
        RidgeRegressionService,
        BayesianRidgeRegressionService,
        KNeighborsRegressionService,
        DecisionTreeRegressionService,
        GradientBoostingRegressionService,
        HistGradientBoostingRegressionService,
        AdaBoostRegressionService,
        XGBoostRegressionService,
        LightGBMRegressionService,
        SVRRegressionService,
        MLPRegressionService,
        PolynomialRegressionService,
        RandomForestRegressionService,
        LogisticRegressionService,
        NaiveBayesClassificationService,
        MultinomialNBClassificationService,
        KNeighborsClassificationService,
        DecisionTreeClassificationService,
        GradientBoostingClassificationService,
        HistGradientBoostingClassificationService,
        AdaBoostClassificationService,
        XGBoostClassificationService,
        LightGBMClassificationService,
        RandomForestClassificationService,
        ExtraTreesClassificationService,
        SVCClassificationService,
        CalibratedLinearSVCClassificationService,
        MLPClassificationService,
        LabelPropagationClassificationService,
        LabelSpreadingClassificationService,
        SelfTrainingClassificationService,
        BirchClusteringService,
        GaussianMixtureClusteringService,
        KMeansClusteringService,
        MiniBatchKMeansClusteringService,
        DBSCANClusteringService,
        IsolationForestAnomalyService,
        LocalOutlierFactorAnomalyService,
        ApyoriAssociationRulesService,
        MlxtendAssociationRulesService,
        ItemSimilarityRecommendationService,
        TokenizedTextClassificationService,
        TokenizedTextClusteringService,
        TokenizedTextTopicModelingService,
        TokenizedTextSimilarityService,
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
