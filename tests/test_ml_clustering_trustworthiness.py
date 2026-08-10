from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import adjusted_rand_score, silhouette_score

from xenix.services.ml.clustering_evidence import (
    ClusteringMetricUnavailableReason,
    ProfileValueSuppressionReason,
    compute_null_baseline,
    compute_quality,
)
from xenix.services.ml.models.clustering import (
    BirchClusteringService,
    DBSCANClusteringService,
    GaussianMixtureClusteringService,
    KMeansClusteringService,
    MiniBatchKMeansClusteringService,
)
from xenix.services.ml.types import ApplyMode


FIXTURES = Path(__file__).parent / "fixtures" / "ml_cf_service"
TRAIN_PATH = FIXTURES / "segment_train.csv"
APPLY_PATH = FIXTURES / "segment_apply.csv"
FEATURES = ["visits_90d", "avg_order_value", "return_rate", "channel"]


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fit_kmeans(dataframe: pd.DataFrame, n_clusters: int):
    return KMeansClusteringService.fit_with_evidence(
        dataframe,
        FEATURES,
        {
            "n_clusters": n_clusters,
            "n_init": 20,
            "max_iter": 300,
            "random_state": 42,
        },
    )


@pytest.mark.parametrize(
    "service",
    [
        KMeansClusteringService,
        MiniBatchKMeansClusteringService,
        BirchClusteringService,
        GaussianMixtureClusteringService,
        DBSCANClusteringService,
    ],
)
def test_every_clustering_catalog_entry_supports_evaluation(service: type) -> None:
    entry = service.catalog_entry()

    assert entry.supports_evaluation is True
    assert entry.supports_apply is (service is not DBSCANClusteringService)
    assert entry.apply_mode is (
        ApplyMode.NONE if service is DBSCANClusteringService else ApplyMode.ROWS
    )


def test_kmeans_evidence_is_typed_recomputable_and_deterministic() -> None:
    source_digest = _file_digest(TRAIN_PATH)
    dataframe = pd.read_csv(TRAIN_PATH)

    first = _fit_kmeans(dataframe, 3)
    second = _fit_kmeans(dataframe, 3)
    facts = first.facts

    transformed = first.estimator.named_steps["preprocess"].transform(dataframe[FEATURES])
    assert facts.quality.silhouette == pytest.approx(
        silhouette_score(transformed, first.display_labels),
        abs=1e-6,
    )
    assert facts.quality.evaluated_row_count == len(dataframe)
    assert facts.quality.noise_row_count == 0
    assert facts.quality.cluster_count == 3
    assert sum(fact.row_count for fact in facts.sizes) == len(dataframe)
    assert facts.stability.protocol == "subsample_80pct_5seed_ari.v1"
    assert facts.stability.sample_fraction == 0.8
    assert facts.stability.run_count == 5
    assert facts.stability.comparison_count == 10
    assert facts.null_baseline.protocol == "permuted_labels_preserve_sizes.v1"
    assert facts.null_baseline.run_count == 16
    assert facts.null_baseline.candidate_margin is not None
    assert facts.null_baseline.candidate_margin > 0.5
    assert facts.model_dump(mode="json") == second.facts.model_dump(mode="json")
    assert np.array_equal(first.display_labels, second.display_labels)
    assert _file_digest(TRAIN_PATH) == source_digest


def test_kmeans_k2_k3_k4_expose_selection_evidence_without_hidden_truth_column() -> None:
    dataframe = pd.read_csv(TRAIN_PATH)
    assert "truth" not in dataframe.columns
    expected_core_membership = np.repeat([0, 1, 2], 24)

    candidates = {cluster_count: _fit_kmeans(dataframe, cluster_count) for cluster_count in (2, 3, 4)}
    k2 = candidates[2]
    k3 = candidates[3]
    k4 = candidates[4]

    assert adjusted_rand_score(expected_core_membership, k3.display_labels[:72]) == pytest.approx(
        1.0
    )
    assert k3.facts.quality.silhouette is not None
    assert k2.facts.quality.silhouette is not None
    assert k3.facts.quality.silhouette > k2.facts.quality.silhouette
    assert not any(size.minimum_segment_warning for size in k3.facts.sizes)
    assert any(size.minimum_segment_warning for size in k4.facts.sizes)
    assert k3.facts.stability.mean_adjusted_rand_index is not None
    assert k3.facts.stability.mean_adjusted_rand_index > 0.9


def test_profiles_use_selected_original_scale_columns_and_are_recomputable() -> None:
    dataframe = pd.read_csv(TRAIN_PATH)
    fitted = _fit_kmeans(dataframe, 3)
    first_cluster = int(fitted.display_labels[0])
    profile = next(item for item in fitted.facts.profiles if item.cluster_id == first_cluster)
    assigned = dataframe.loc[fitted.display_labels == first_cluster]
    avg_order_profile = next(
        item for item in profile.numeric if item.feature == "avg_order_value"
    )
    channel_profile = next(item for item in profile.categorical if item.feature == "channel")

    assert avg_order_profile.median == pytest.approx(assigned["avg_order_value"].median())
    assert avg_order_profile.q1 == pytest.approx(assigned["avg_order_value"].quantile(0.25))
    assert avg_order_profile.q3 == pytest.approx(assigned["avg_order_value"].quantile(0.75))
    assert channel_profile.top_value == assigned["channel"].dropna().mode().iloc[0]
    profiled_features = {
        fact.feature for cluster in fitted.facts.profiles for fact in cluster.numeric + cluster.categorical
    }
    assert "entity_id" not in profiled_features
    assert any("do not establish external or causal validity" in item for item in fitted.facts.limitations)


def test_profiles_suppress_identifier_like_values_but_keep_business_categories() -> None:
    dataframe = pd.read_csv(TRAIN_PATH)
    selected_features = [*FEATURES, "entity_id"]
    fitted = KMeansClusteringService.fit_with_evidence(
        dataframe,
        selected_features,
        {"n_clusters": 3, "n_init": 20, "max_iter": 300, "random_state": 42},
    )

    for profile in fitted.facts.profiles:
        entity_profile = next(
            fact for fact in profile.categorical if fact.feature == "entity_id"
        )
        channel_profile = next(
            fact for fact in profile.categorical if fact.feature == "channel"
        )
        assert entity_profile.distinct_count > 0
        assert entity_profile.top_value is None
        assert entity_profile.top_value_share is None
        assert entity_profile.value_suppressed is True
        assert (
            entity_profile.suppression_reason
            is ProfileValueSuppressionReason.HIGH_CARDINALITY_IDENTIFIER_LIKE
        )
        assert channel_profile.top_value is not None
        assert channel_profile.top_value_share is not None
        assert channel_profile.value_suppressed is False
        assert channel_profile.suppression_reason is None

    serialized = json.dumps(fitted.facts.model_dump(mode="json"), sort_keys=True)
    assert "E001" not in serialized
    assert any(
        "Top values are suppressed" in limitation and "entity_id" in limitation
        for limitation in fitted.facts.limitations
    )


def test_quality_and_null_are_invariant_to_label_names() -> None:
    dataframe = pd.read_csv(TRAIN_PATH)
    fitted = _fit_kmeans(dataframe, 3)
    transformed = fitted.estimator.named_steps["preprocess"].transform(dataframe[FEATURES])
    renamed = np.asarray(
        [{1: 30, 2: 10, 3: 20}[int(label)] for label in fitted.display_labels],
        dtype=np.int64,
    )

    original_quality = compute_quality(transformed, fitted.display_labels)
    renamed_quality = compute_quality(transformed, renamed)
    original_null = compute_null_baseline(transformed, fitted.display_labels, original_quality)
    renamed_null = compute_null_baseline(transformed, renamed, renamed_quality)

    assert renamed_quality.silhouette == pytest.approx(original_quality.silhouette, abs=1e-12)
    assert renamed_quality.calinski_harabasz == pytest.approx(
        original_quality.calinski_harabasz,
        abs=1e-12,
    )
    assert renamed_quality.davies_bouldin == pytest.approx(
        original_quality.davies_bouldin,
        abs=1e-12,
    )
    assert renamed_null.median_silhouette == pytest.approx(
        original_null.median_silhouette,
        abs=1e-12,
    )


def test_kmeans_apply_uses_persisted_label_map_and_accepts_unseen_category(
    tmp_path: Path,
) -> None:
    train = pd.read_csv(TRAIN_PATH)
    apply_frame = pd.read_csv(APPLY_PATH)
    fitted = _fit_kmeans(train, 3)
    artifact_path = tmp_path / "clusterer.joblib"
    joblib.dump(fitted.estimator, artifact_path)
    retained = joblib.load(artifact_path)

    training_predictions = KMeansClusteringService.predict_with_retained_labels(
        retained,
        train,
        FEATURES,
    )
    apply_predictions = KMeansClusteringService.predict_with_retained_labels(
        retained,
        apply_frame,
        FEATURES,
    )

    assert np.array_equal(training_predictions, fitted.display_labels)
    assert len(apply_predictions) == len(apply_frame)
    assert set(int(value) for value in apply_predictions) <= set(
        retained.xenix_cluster_label_mapping_.values()
    )
    assert "marketplace" in set(apply_frame["channel"])


def test_dbscan_reports_noise_and_rejects_apply_before_estimator_access() -> None:
    dataframe = pd.read_csv(TRAIN_PATH)
    fitted = DBSCANClusteringService.fit_with_evidence(
        dataframe,
        FEATURES,
        {"eps": 1.2, "min_samples": 4},
    )
    facts = fitted.facts
    transformed = fitted.estimator.named_steps["preprocess"].transform(dataframe[FEATURES])
    evaluated = fitted.display_labels != -1

    assert DBSCANClusteringService.supports_evaluation is True
    assert DBSCANClusteringService.supports_apply is False
    assert DBSCANClusteringService.apply_mode is ApplyMode.NONE
    assert facts.quality.noise_row_count > 0
    assert facts.quality.evaluated_row_count == int(evaluated.sum())
    assert facts.quality.silhouette == pytest.approx(
        silhouette_score(transformed[evaluated], fitted.display_labels[evaluated]),
        abs=1e-6,
    )
    noise_size = next(size for size in facts.sizes if size.cluster_id == -1)
    assert noise_size.is_noise is True
    assert noise_size.row_count == facts.quality.noise_row_count
    assert any(
        entry.raw_label == -1 and entry.display_label == -1
        for entry in facts.label_map.entries
    )
    with pytest.raises(ValueError, match="does not support apply"):
        DBSCANClusteringService.predict_with_retained_labels(
            object(),  # type: ignore[arg-type]
            dataframe,
            FEATURES,
        )


def test_typed_unavailable_reason_replaces_invalid_metric_values() -> None:
    matrix = np.asarray([[0.0], [1.0], [2.0]])
    facts = compute_quality(matrix, np.asarray([1, 1, 1]))

    assert facts.silhouette is None
    assert facts.calinski_harabasz is None
    assert facts.davies_bouldin is None
    assert facts.unavailable_reason is ClusteringMetricUnavailableReason.FEWER_THAN_TWO_CLUSTERS
