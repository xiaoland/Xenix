import numpy as np
import pandas as pd

from xenix.services.ml.contracts import CandidateMetrics
from xenix.services.ml.evaluation import (
    build_classification_metrics,
    build_regression_metrics,
    compare_metric_snapshots,
    get_default_policy,
)
from xenix.services.ml.models.classification import XGBoostClassificationService
from xenix.services.ml.registry import get_model_catalog_entry, get_model_service, list_model_catalog
from xenix.services.ml.types import ColumnRoleKind, EvaluationKind, ModelCatalogEntry, ModelFamily, ModelTaskKind
from xenix.services.storage.models import ProblemKind


def test_model_catalog_exposes_json_schema_and_model_axes() -> None:
    catalog = list_model_catalog()

    assert len(catalog) == 41
    assert all(isinstance(entry, ModelCatalogEntry) for entry in catalog)
    assert all(entry.model_family for entry in catalog)
    assert all(entry.model_task_kind for entry in catalog)
    assert all(entry.evaluation_kind for entry in catalog)
    assert all(entry.train_role_schema.roles for entry in catalog)
    assert all(entry.apply_role_schema.roles for entry in catalog)
    assert all(entry.result_contract.preview_kinds for entry in catalog)
    ridge = get_model_catalog_entry("regression.ridge")
    assert ridge.problem_kind is ProblemKind.REGRESSION
    assert ridge.evaluation_kind is EvaluationKind.REGRESSION
    assert ridge.model_family is ModelFamily.SUPERVISED
    assert ridge.model_task_kind is ModelTaskKind.PREDICTOR
    assert [role.name for role in ridge.train_role_schema.roles] == ["feature", "target"]
    assert ridge.train_role_schema.roles[0].kind is ColumnRoleKind.MANY_COLUMNS
    assert ridge.train_role_schema.roles[1].kind is ColumnRoleKind.SINGLE_COLUMN
    assert [role.name for role in ridge.apply_role_schema.roles] == ["feature"]
    assert ridge.result_contract.apply_result_kinds == ["table"]
    assert "properties" in ridge.param_schema
    assert ridge.param_grid_schema is not None
    assert ridge.family == "Regularized linear"
    assert ridge.guidance
    assert ridge.recommendation_tier == 20
    lasso = get_model_catalog_entry("regression.lasso")
    assert lasso.param_schema["properties"]["alpha"]["default"] == 1.0
    gradient_boosting = get_model_catalog_entry("classification.gradient_boosting")
    assert gradient_boosting.param_grid_schema is not None
    random_forest = get_model_catalog_entry("classification.random_forest")
    assert random_forest.param_grid_schema is not None
    assert random_forest.param_grid_schema["properties"]["n_estimators"]["default"] == [100, 200, 300]
    xgboost_regression = get_model_catalog_entry("regression.xgboost")
    assert xgboost_regression.model_family is ModelFamily.SUPERVISED
    assert xgboost_regression.param_grid_schema is not None
    assert xgboost_regression.param_grid_schema["properties"]["reg_lambda"]["default"] == [1.0, 5.0, 10.0]
    lightgbm_classification = get_model_catalog_entry("classification.lightgbm")
    assert lightgbm_classification.model_task_kind is ModelTaskKind.PREDICTOR
    assert lightgbm_classification.param_schema["properties"]["num_leaves"]["default"] == 31
    assert lightgbm_classification.param_grid_schema is not None
    assert lightgbm_classification.param_grid_schema["properties"]["n_estimators"]["default"] == [100, 200]
    assert lightgbm_classification.param_grid_schema["properties"]["max_depth"]["default"] == [-1, 5, 10]
    assert set(lightgbm_classification.param_grid_schema["properties"]) == {"n_estimators", "max_depth"}
    extra_trees = get_model_catalog_entry("classification.extra_trees")
    assert extra_trees.param_grid_schema is not None
    assert extra_trees.param_schema["properties"]["n_estimators"]["default"] == 200
    hist_classifier = get_model_catalog_entry("classification.hist_gradient_boosting")
    assert hist_classifier.param_grid_schema is not None
    assert hist_classifier.param_schema["properties"]["max_leaf_nodes"]["default"] == 31
    svc = get_model_catalog_entry("classification.svc")
    assert svc.param_schema["properties"]["C"]["default"] == 1.0
    calibrated_svc = get_model_catalog_entry("classification.linear_svc_calibrated")
    assert calibrated_svc.param_grid_schema is not None
    mlp_classifier = get_model_catalog_entry("classification.mlp")
    assert mlp_classifier.param_schema["properties"]["hidden_layer_size"]["default"] == 64
    multinomial_nb = get_model_catalog_entry("classification.multinomial_naive_bayes")
    assert multinomial_nb.family == "Probabilistic baseline"
    bayesian_ridge = get_model_catalog_entry("regression.bayesian_ridge")
    assert bayesian_ridge.param_schema["properties"]["alpha_1"]["default"] == 1e-6
    elastic_net = get_model_catalog_entry("regression.elastic_net")
    assert elastic_net.param_schema["properties"]["l1_ratio"]["default"] == 0.5
    svr = get_model_catalog_entry("regression.svr")
    assert svr.param_schema["properties"]["epsilon"]["default"] == 0.1
    mlp_regression = get_model_catalog_entry("regression.mlp")
    assert mlp_regression.param_grid_schema["properties"]["hidden_layer_size"]["default"] == [32, 64, 128]
    hist_regression = get_model_catalog_entry("regression.hist_gradient_boosting")
    assert hist_regression.param_schema["properties"]["max_leaf_nodes"]["default"] == 31
    polynomial = get_model_catalog_entry("regression.polynomial")
    assert polynomial.param_grid_schema is not None
    assert polynomial.param_grid_schema["properties"]["degree"]["default"] == [1, 2, 3]
    naive_bayes = get_model_catalog_entry("classification.naive_bayes")
    assert naive_bayes.param_schema["properties"]["var_smoothing"]["default"] == 1e-9
    assert naive_bayes.family == "Probabilistic baseline"
    assert naive_bayes.model_family is ModelFamily.SUPERVISED
    assert naive_bayes.model_task_kind is ModelTaskKind.PREDICTOR
    assert [role.name for role in naive_bayes.train_role_schema.roles] == ["feature", "target"]
    assert naive_bayes.recommendation_tier == 20
    knn = get_model_catalog_entry("classification.knn")
    assert knn.param_grid_schema is not None
    assert knn.param_grid_schema["properties"]["n_neighbors"]["default"] == [3, 5, 7]
    label_spreading = get_model_catalog_entry("classification.label_spreading")
    assert label_spreading.problem_kind is ProblemKind.CLASSIFICATION
    assert label_spreading.evaluation_kind is EvaluationKind.CLASSIFICATION
    assert label_spreading.supports_hyperparameter_tuning is False
    assert [role.name for role in label_spreading.train_role_schema.roles] == ["feature", "partial_target"]
    assert label_spreading.train_role_schema.roles[1].kind is ColumnRoleKind.SINGLE_COLUMN
    assert [role.name for role in label_spreading.apply_role_schema.roles] == ["feature"]
    clustering = get_model_catalog_entry("clustering.kmeans")
    assert clustering.problem_kind is ProblemKind.CLUSTERING
    assert clustering.evaluation_kind is EvaluationKind.SUMMARY
    assert clustering.summary_metric_name == "cluster_count"
    assert clustering.model_family is ModelFamily.CLUSTERING
    assert clustering.model_task_kind is ModelTaskKind.SEGMENTER
    assert clustering.requires_target is False
    assert [role.name for role in clustering.train_role_schema.roles] == ["feature"]
    assert clustering.train_role_schema.roles[0].kind is ColumnRoleKind.MANY_COLUMNS
    assert [role.name for role in clustering.apply_role_schema.roles] == ["feature"]
    assert clustering.result_contract.train_result_kinds == ["model", "table"]
    assert clustering.supports_hyperparameter_tuning is False
    assert clustering.param_grid_schema is None
    anomaly = get_model_catalog_entry("anomaly.isolation_forest")
    assert anomaly.problem_kind is ProblemKind.ANOMALY_DETECTION
    assert anomaly.evaluation_kind is EvaluationKind.SUMMARY
    assert anomaly.summary_metric_name == "anomaly_count"
    assert anomaly.model_family is ModelFamily.ANOMALY_DETECTION
    assert anomaly.model_task_kind is ModelTaskKind.ANOMALY_SCORER
    assert anomaly.requires_target is False
    assert [role.name for role in anomaly.train_role_schema.roles] == ["feature"]
    assert [role.name for role in anomaly.apply_role_schema.roles] == ["feature"]
    assert anomaly.result_contract.train_result_kinds == ["model", "table"]
    assert anomaly.supports_hyperparameter_tuning is False
    assert anomaly.param_grid_schema is None
    association = get_model_catalog_entry("association.apriori_mlxtend")
    assert association.problem_kind is None
    assert association.evaluation_kind is EvaluationKind.SUMMARY
    assert association.summary_metric_name == "rule_count"
    assert association.model_family is ModelFamily.ASSOCIATION_RULES
    assert association.model_task_kind is ModelTaskKind.RULE_MINER
    assert association.requires_target is False
    assert association.supports_hyperparameter_tuning is False
    assert [role.name for role in association.train_role_schema.roles] == ["item"]
    assert [role.name for role in association.apply_role_schema.roles] == ["item"]
    recommender = get_model_catalog_entry("recommendation.item_similarity")
    assert recommender.problem_kind is None
    assert recommender.evaluation_kind is EvaluationKind.SUMMARY
    assert recommender.summary_metric_name == "recommendation_count"
    assert recommender.model_family is ModelFamily.RECOMMENDATION
    assert recommender.model_task_kind is ModelTaskKind.RECOMMENDER
    assert [role.name for role in recommender.train_role_schema.roles] == ["user", "item", "rating"]
    assert [role.name for role in recommender.apply_role_schema.roles] == ["item"]


def test_clustering_policy_uses_non_split_metric_defaults() -> None:
    policy = get_default_policy(EvaluationKind.SUMMARY, summary_metric_name="cluster_count")

    assert policy.evaluation_kind is EvaluationKind.SUMMARY
    assert policy.primary_metric_name == "cluster_count"
    assert policy.split_strategy == "none"
    assert policy.test_size == 0.0
    assert policy.cv_folds is None


def test_anomaly_policy_uses_non_split_metric_defaults() -> None:
    policy = get_default_policy(EvaluationKind.SUMMARY, summary_metric_name="anomaly_count")

    assert policy.evaluation_kind is EvaluationKind.SUMMARY
    assert policy.primary_metric_name == "anomaly_count"
    assert policy.split_strategy == "none"
    assert policy.test_size == 0.0
    assert policy.cv_folds is None


def test_summary_policy_uses_task_specific_metric_defaults() -> None:
    policy = get_default_policy(EvaluationKind.SUMMARY, summary_metric_name="rule_count")

    assert policy.evaluation_kind is EvaluationKind.SUMMARY
    assert policy.primary_metric_name == "rule_count"
    assert policy.split_strategy == "none"
    assert policy.test_size == 0.0
    assert policy.cv_folds is None


def test_xgboost_classifier_preserves_string_labels() -> None:
    estimator = XGBoostClassificationService._build_pipeline(
        n_estimators=5,
        max_depth=2,
        learning_rate=0.2,
    )
    features = pd.DataFrame(
        {
            "balance": [1, 2, 8, 9, 3, 10],
            "segment": ["a", "a", "b", "b", "a", "b"],
        }
    )
    labels = pd.Series(["stay", "stay", "leave", "leave", "stay", "leave"])

    estimator.fit(features, labels)
    prediction = estimator.predict(pd.DataFrame({"balance": [4], "segment": ["a"]}))

    assert prediction[0] in {"stay", "leave"}


def test_compare_metric_snapshots_prefers_higher_primary_metric_then_tie_breakers() -> None:
    policy = get_default_policy(EvaluationKind.REGRESSION)
    left = CandidateMetrics(
        primary_metric_name="r2",
        primary_metric_value=0.91,
        metrics={"r2": 0.91, "rmse": 0.3, "mae": 0.2},
    )
    right = CandidateMetrics(
        primary_metric_name="r2",
        primary_metric_value=0.90,
        metrics={"r2": 0.90, "rmse": 0.1, "mae": 0.1},
    )

    comparison = compare_metric_snapshots(policy, left, right)

    assert comparison > 0


def test_regression_metrics_include_extended_evaluation_evidence() -> None:
    metrics = build_regression_metrics(
        pd.Series([10.0, 20.0, 30.0, 40.0]),
        np.array([12.0, 18.0, 33.0, 37.0]),
    )

    assert metrics.primary_metric_name == "r2"
    assert {
        "r2",
        "mse",
        "rmse",
        "mae",
        "mape",
        "explained_variance",
        "residual_mean",
        "residual_std",
    }.issubset(metrics.metrics)


def test_classification_metrics_include_structured_and_probability_evidence() -> None:
    metrics = build_classification_metrics(
        pd.Series(["stay", "stay", "leave", "leave"]),
        np.array(["stay", "leave", "leave", "leave"]),
        y_proba=np.array(
            [
                [0.1, 0.9],
                [0.6, 0.4],
                [0.8, 0.2],
                [0.9, 0.1],
            ]
        ),
        classes=["leave", "stay"],
    )

    assert metrics.primary_metric_name == "f1_weighted"
    assert {
        "accuracy",
        "balanced_accuracy",
        "precision_macro",
        "precision_weighted",
        "recall_macro",
        "recall_weighted",
        "f1_macro",
        "f1_weighted",
        "roc_auc",
        "pr_auc",
        "log_loss",
    }.issubset(metrics.metrics)
    assert metrics.details["labels"] == ["leave", "stay"]
    assert metrics.details["confusion_matrix"] == [[2, 0], [1, 1]]
    assert "classification_report" in metrics.details
    assert metrics.details["probability_metrics"]["available"] is True


def test_classification_metrics_record_unavailable_probability_reason() -> None:
    metrics = build_classification_metrics(
        pd.Series(["stay", "stay", "leave", "leave"]),
        np.array(["stay", "leave", "leave", "leave"]),
    )

    assert "roc_auc" not in metrics.metrics
    assert "pr_auc" not in metrics.metrics
    assert "log_loss" not in metrics.metrics
    assert metrics.details["probability_metrics"] == {
        "available": False,
        "reason": "estimator_does_not_expose_predict_proba",
    }


def test_new_supervised_model_services_fit_small_mixed_frames() -> None:
    classification_features = pd.DataFrame(
        {
            "score": [0.0, 0.1, 0.2, 0.3, 1.0, 1.1, 1.2, 1.3],
            "visits": [1, 1, 2, 2, 8, 8, 9, 9],
            "segment": ["a", "a", "a", "a", "b", "b", "b", "b"],
        }
    )
    classification_labels = pd.Series(["stay", "stay", "stay", "stay", "leave", "leave", "leave", "leave"])
    classification_cases = {
        "classification.extra_trees": {"n_estimators": 10},
        "classification.hist_gradient_boosting": {"max_iter": 20, "min_samples_leaf": 1},
        "classification.svc": {"kernel": "linear"},
        "classification.linear_svc_calibrated": {"cv": 2, "max_iter": 1000},
        "classification.mlp": {"hidden_layer_size": 4, "max_iter": 200},
        "classification.multinomial_naive_bayes": {},
    }
    for model_key, params in classification_cases.items():
        service = get_model_service(model_key)
        estimator = service._build_pipeline(**service._estimator_kwargs(service.validate_params(params)))
        estimator.fit(classification_features, classification_labels)
        assert len(estimator.predict(classification_features.head(2))) == 2

    regression_features = pd.DataFrame(
        {
            "score": [0.0, 0.1, 0.2, 0.3, 1.0, 1.1, 1.2, 1.3],
            "visits": [1, 1, 2, 2, 8, 8, 9, 9],
            "segment": ["a", "a", "a", "a", "b", "b", "b", "b"],
        }
    )
    regression_target = pd.Series([10.0, 11.0, 12.0, 13.0, 30.0, 31.0, 32.0, 33.0])
    regression_cases = {
        "regression.elastic_net": {"alpha": 0.1, "l1_ratio": 0.5},
        "regression.hist_gradient_boosting": {"max_iter": 20, "min_samples_leaf": 1},
        "regression.svr": {"kernel": "linear"},
        "regression.mlp": {"hidden_layer_size": 4, "max_iter": 200},
    }
    for model_key, params in regression_cases.items():
        service = get_model_service(model_key)
        estimator = service._build_pipeline(**service._estimator_kwargs(service.validate_params(params)))
        estimator.fit(regression_features, regression_target)
        assert len(estimator.predict(regression_features.head(2))) == 2
