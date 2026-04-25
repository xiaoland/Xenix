from __future__ import annotations

from pydantic import BaseModel, Field
from sklearn.cluster import DBSCAN, KMeans

from ...storage.models import ProblemKind
from .base import UnsupervisedClusteringModelService


class KMeansParams(BaseModel):
    n_clusters: int = Field(default=4, ge=2, le=20)
    n_init: int = Field(default=10, ge=1, le=50)
    max_iter: int = Field(default=300, ge=50, le=1000)


class DBSCANParams(BaseModel):
    eps: float = Field(default=0.5, gt=0.0, le=10.0)
    min_samples: int = Field(default=5, ge=1, le=100)


class KMeansClusteringService(UnsupervisedClusteringModelService):
    key = "clustering.kmeans"
    display_name = "KMeans Clustering"
    problem_kind = ProblemKind.CLUSTERING
    params_model = KMeansParams

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> KMeans:
        kwargs = dict(estimator_kwargs)
        kwargs.setdefault("random_state", 42)
        return KMeans(**kwargs)


class DBSCANClusteringService(UnsupervisedClusteringModelService):
    key = "clustering.dbscan"
    display_name = "DBSCAN Clustering"
    problem_kind = ProblemKind.CLUSTERING
    params_model = DBSCANParams

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> DBSCAN:
        return DBSCAN(**estimator_kwargs)
