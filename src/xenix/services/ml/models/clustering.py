from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.cluster import DBSCAN, Birch, KMeans, MiniBatchKMeans
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import Pipeline

from ...storage.models import ProblemKind
from ..clustering_evidence import (
    ClusteringEvaluationFacts,
    apply_label_mapping,
    build_clustering_evidence,
    build_stable_label_mapping,
)
from ..types import ApplyMode
from .base import UnsupervisedClusteringModelService


class KMeansParams(BaseModel):
    n_clusters: int = Field(default=4, ge=2, le=20)
    n_init: int = Field(default=10, ge=1, le=50)
    max_iter: int = Field(default=300, ge=50, le=1000)
    random_state: int = Field(default=42, ge=0, le=2_147_483_647)


class DBSCANParams(BaseModel):
    eps: float = Field(default=0.5, gt=0.0, le=10.0)
    min_samples: int = Field(default=5, ge=1, le=100)


class MiniBatchKMeansParams(BaseModel):
    n_clusters: int = Field(default=4, ge=2, le=20)
    batch_size: int = Field(default=256, ge=10, le=10000)
    n_init: int = Field(default=10, ge=1, le=50)
    max_iter: int = Field(default=300, ge=50, le=1000)
    random_state: int = Field(default=42, ge=0, le=2_147_483_647)


class BirchParams(BaseModel):
    n_clusters: int | None = Field(default=4, ge=2, le=20)
    threshold: float = Field(default=0.5, gt=0.0, le=10.0)
    branching_factor: int = Field(default=50, ge=2, le=500)


class GaussianMixtureParams(BaseModel):
    n_components: int = Field(default=4, ge=1, le=20)
    covariance_type: Literal["full", "tied", "diag", "spherical"] = Field(default="full")
    n_init: int = Field(default=1, ge=1, le=20)
    max_iter: int = Field(default=100, ge=50, le=1000)
    reg_covar: float = Field(default=1e-6, ge=0.0, le=1.0)
    random_state: int = Field(default=42, ge=0, le=2_147_483_647)


@dataclass(frozen=True)
class ClusteringFitEvidence:
    estimator: Pipeline
    display_labels: np.ndarray
    facts: ClusteringEvaluationFacts


class TrustworthyClusteringMixin:
    """Model-side hooks used by the clustering worker orchestration.

    The evidence is computed in the declared prepared feature space, while the
    bounded profiles are deliberately computed from the selected original-scale
    columns.  The retained raw-to-display label map is the only authority used
    by apply.
    """

    supports_evaluation = True
    supports_apply = True
    apply_mode = ApplyMode.ROWS
    summary_metric_name = "silhouette"
    params_model: type[BaseModel]

    @classmethod
    def fit_with_evidence(
        cls,
        dataframe: pd.DataFrame,
        feature_columns: list[str],
        params: BaseModel | dict[str, Any],
    ) -> ClusteringFitEvidence:
        if not feature_columns:
            raise ValueError("Select at least one input column for clustering.")
        missing = [column for column in feature_columns if column not in dataframe.columns]
        if missing:
            raise ValueError(f"Clustering input is missing required columns: {', '.join(missing)}.")

        params_model = (
            params if isinstance(params, cls.params_model) else cls.params_model.model_validate(params)
        )
        estimator_kwargs = params_model.model_dump(exclude_none=True, by_alias=True)
        features = dataframe.loc[:, feature_columns].copy()
        estimator = cls._build_pipeline(**estimator_kwargs)
        raw_labels = np.asarray(estimator.fit_predict(features), dtype=np.int64)
        label_mapping = build_stable_label_mapping(raw_labels)
        display_labels = apply_label_mapping(raw_labels, label_mapping)
        transformed = estimator.named_steps["preprocess"].transform(features)

        def estimator_factory(seed: int) -> Any:
            stability_kwargs = dict(estimator_kwargs)
            if "random_state" in cls.params_model.model_fields:
                stability_kwargs["random_state"] = seed
            return cls._build_estimator(**stability_kwargs)

        facts = build_clustering_evidence(
            raw_features=features,
            transformed_features=transformed,
            display_labels=display_labels,
            label_mapping=label_mapping,
            estimator_factory=estimator_factory,
        )
        estimator.xenix_cluster_label_mapping_ = dict(label_mapping)
        estimator.xenix_clustering_evidence_ = facts.model_dump(mode="json")
        return ClusteringFitEvidence(
            estimator=estimator,
            display_labels=display_labels,
            facts=facts,
        )

    @classmethod
    def predict_with_retained_labels(
        cls,
        estimator: Pipeline,
        dataframe: pd.DataFrame,
        feature_columns: list[str],
    ) -> np.ndarray:
        if not cls.supports_apply or cls.apply_mode is ApplyMode.NONE:
            raise ValueError(f"Model '{cls.key}' does not support apply.")
        if not hasattr(estimator, "predict"):
            raise ValueError(f"Model '{cls.key}' does not support apply.")
        mapping = getattr(estimator, "xenix_cluster_label_mapping_", None)
        if not isinstance(mapping, dict) or not mapping:
            raise ValueError("The retained clustering analyzer has no persisted label map.")
        missing = [column for column in feature_columns if column not in dataframe.columns]
        if missing:
            raise ValueError(f"Apply input is missing required columns: {', '.join(missing)}.")
        raw_labels = estimator.predict(dataframe.loc[:, feature_columns].copy())
        return apply_label_mapping(raw_labels, mapping)


class KMeansClusteringService(TrustworthyClusteringMixin, UnsupervisedClusteringModelService):
    key = "clustering.kmeans"
    display_name = "KMeans Clustering"
    problem_kind = ProblemKind.CLUSTERING
    family = "Centroid clustering"
    guidance = "Creates a chosen number of compact segments around representative centers."
    recommendation_tier = 10
    params_model = KMeansParams

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> KMeans:
        kwargs = dict(estimator_kwargs)
        kwargs.setdefault("random_state", 42)
        return KMeans(**kwargs)


class MiniBatchKMeansClusteringService(
    TrustworthyClusteringMixin,
    UnsupervisedClusteringModelService,
):
    key = "clustering.minibatch_kmeans"
    display_name = "MiniBatch KMeans Clustering"
    problem_kind = ProblemKind.CLUSTERING
    family = "Centroid clustering"
    guidance = "Creates compact segments with a faster mini-batch KMeans fit for larger datasets."
    recommendation_tier = 12
    params_model = MiniBatchKMeansParams

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> MiniBatchKMeans:
        kwargs = dict(estimator_kwargs)
        kwargs.setdefault("random_state", 42)
        return MiniBatchKMeans(**kwargs)


class BirchClusteringService(TrustworthyClusteringMixin, UnsupervisedClusteringModelService):
    key = "clustering.birch"
    display_name = "BIRCH Clustering"
    problem_kind = ProblemKind.CLUSTERING
    family = "Hierarchical clustering"
    guidance = "Builds scalable customer segments through compact clustering feature summaries."
    recommendation_tier = 15
    params_model = BirchParams

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> Birch:
        return Birch(**estimator_kwargs)


class GaussianMixtureClusteringService(
    TrustworthyClusteringMixin,
    UnsupervisedClusteringModelService,
):
    key = "clustering.gaussian_mixture"
    display_name = "Gaussian Mixture Clustering"
    problem_kind = ProblemKind.CLUSTERING
    family = "Probabilistic clustering"
    guidance = "Groups rows into probabilistic mixture components for less rigid segment shapes."
    recommendation_tier = 18
    params_model = GaussianMixtureParams

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> GaussianMixture:
        kwargs = dict(estimator_kwargs)
        kwargs.setdefault("random_state", 42)
        return GaussianMixture(**kwargs)


class DBSCANClusteringService(TrustworthyClusteringMixin, UnsupervisedClusteringModelService):
    key = "clustering.dbscan"
    display_name = "DBSCAN Clustering"
    problem_kind = ProblemKind.CLUSTERING
    family = "Density clustering"
    guidance = "Finds dense natural groups and marks sparse rows as noise."
    recommendation_tier = 25
    params_model = DBSCANParams
    supports_apply = False
    apply_mode = ApplyMode.NONE

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> DBSCAN:
        return DBSCAN(**estimator_kwargs)
