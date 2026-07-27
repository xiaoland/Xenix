import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from xenix.services.ml.contracts import CandidateMetrics
from xenix.services.ml.evaluation import (
    build_classification_metrics,
    build_regression_metrics,
    compare_metric_snapshots,
    get_default_policy,
)
from xenix.services.ml.models.classification import XGBoostClassificationService
from xenix.services.ml.registry import _build_model_service_registry, get_model_service
from xenix.services.ml.types import (
    ColumnRoleKind,
    EvaluationKind,
    ModelCatalogEntry,
    ModelResultContract,
    ModelRoleDefinition,
    ModelRoleSchema,
)


def test_catalog_declarations_reject_invalid_local_contracts() -> None:
    with pytest.raises(ValidationError, match="Role name must not be blank"):
        ModelRoleDefinition(name=" ", kind=ColumnRoleKind.SINGLE_COLUMN)

    role = ModelRoleDefinition(name="feature", kind=ColumnRoleKind.MANY_COLUMNS)
    with pytest.raises(ValidationError, match="duplicate role names"):
        ModelRoleSchema(roles=[role, role])

    with pytest.raises(ValidationError, match="blank values"):
        ModelResultContract(
            train_result_kinds=["model"],
            apply_result_kinds=["table"],
            preview_kinds=[""],
        )


def test_registry_construction_validates_catalog_cross_field_contracts() -> None:
    class InvalidSummaryMetricService(XGBoostClassificationService):
        key = "classification.invalid_summary_metric"
        summary_metric_name = "result_count"

    class InvalidTuningContractService(XGBoostClassificationService):
        key = "classification.invalid_tuning_contract"
        supports_hyperparameter_tuning = False

    class ArbitraryParamSchemaService(XGBoostClassificationService):
        key = "classification.arbitrary_param_schema"

        @classmethod
        def catalog_entry(cls) -> ModelCatalogEntry:
            return super().catalog_entry().model_copy(
                update={"param_schema": {"type": "string"}}
            )

    with pytest.raises(
        ValidationError,
        match="summary_metric_name is only valid for summary evaluation",
    ):
        _build_model_service_registry((InvalidSummaryMetricService,))

    with pytest.raises(
        ValidationError,
        match="supports_hyperparameter_tuning must match",
    ):
        _build_model_service_registry((InvalidTuningContractService,))

    with pytest.raises(ValueError, match="must be derived from params_model"):
        _build_model_service_registry((ArbitraryParamSchemaService,))


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
    classification_labels = pd.Series(
        ["stay", "stay", "stay", "stay", "leave", "leave", "leave", "leave"]
    )
    classification_cases = {
        "classification.extra_trees": {"n_estimators": 10},
        "classification.hist_gradient_boosting": {
            "max_iter": 20,
            "min_samples_leaf": 1,
        },
        "classification.svc": {"kernel": "linear"},
        "classification.linear_svc_calibrated": {"cv": 2, "max_iter": 1000},
        "classification.mlp": {"hidden_layer_size": 4, "max_iter": 200},
        "classification.multinomial_naive_bayes": {},
    }
    for model_key, params in classification_cases.items():
        service = get_model_service(model_key)
        estimator = service._build_pipeline(
            **service._estimator_kwargs(service.validate_params(params))
        )
        estimator.fit(classification_features, classification_labels)
        assert len(estimator.predict(classification_features.head(2))) == 2

    regression_features = pd.DataFrame(
        {
            "score": [0.0, 0.1, 0.2, 0.3, 1.0, 1.1, 1.2, 1.3],
            "visits": [1, 1, 2, 2, 8, 8, 9, 9],
            "segment": ["a", "a", "a", "a", "b", "b", "b", "b"],
        }
    )
    regression_target = pd.Series(
        [10.0, 11.0, 12.0, 13.0, 30.0, 31.0, 32.0, 33.0]
    )
    regression_cases = {
        "regression.elastic_net": {"alpha": 0.1, "l1_ratio": 0.5},
        "regression.hist_gradient_boosting": {
            "max_iter": 20,
            "min_samples_leaf": 1,
        },
        "regression.svr": {"kernel": "linear"},
        "regression.mlp": {"hidden_layer_size": 4, "max_iter": 200},
    }
    for model_key, params in regression_cases.items():
        service = get_model_service(model_key)
        estimator = service._build_pipeline(
            **service._estimator_kwargs(service.validate_params(params))
        )
        estimator.fit(regression_features, regression_target)
        assert len(estimator.predict(regression_features.head(2))) == 2
