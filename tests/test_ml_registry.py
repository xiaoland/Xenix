from xenix.services.ml.contracts import CandidateMetrics
from xenix.services.ml.evaluation import compare_metric_snapshots, get_default_policy
from xenix.services.ml.registry import get_model_catalog_entry, list_model_catalog
from xenix.services.ml.types import ColumnRoleKind, ModelCatalogEntry, ModelFamily, ModelTaskKind
from xenix.services.storage.models import ProblemKind


def test_model_catalog_exposes_json_schema_and_problem_kinds() -> None:
    catalog = list_model_catalog()

    assert len(catalog) == 21
    assert all(isinstance(entry, ModelCatalogEntry) for entry in catalog)
    assert all(entry.model_family for entry in catalog)
    assert all(entry.model_task_kind for entry in catalog)
    assert all(entry.train_role_schema.roles for entry in catalog)
    assert all(entry.apply_role_schema.roles for entry in catalog)
    assert all(entry.result_contract.preview_kinds for entry in catalog)
    ridge = get_model_catalog_entry("regression.ridge")
    assert ridge.problem_kind is ProblemKind.REGRESSION
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
    bayesian_ridge = get_model_catalog_entry("regression.bayesian_ridge")
    assert bayesian_ridge.param_schema["properties"]["alpha_1"]["default"] == 1e-6
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
    clustering = get_model_catalog_entry("clustering.kmeans")
    assert clustering.problem_kind is ProblemKind.CLUSTERING
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
    assert anomaly.model_family is ModelFamily.ANOMALY_DETECTION
    assert anomaly.model_task_kind is ModelTaskKind.ANOMALY_SCORER
    assert anomaly.requires_target is False
    assert [role.name for role in anomaly.train_role_schema.roles] == ["feature"]
    assert [role.name for role in anomaly.apply_role_schema.roles] == ["feature"]
    assert anomaly.result_contract.train_result_kinds == ["model", "table"]
    assert anomaly.supports_hyperparameter_tuning is False
    assert anomaly.param_grid_schema is None


def test_clustering_policy_uses_non_split_metric_defaults() -> None:
    policy = get_default_policy(ProblemKind.CLUSTERING)

    assert policy.primary_metric_name == "cluster_count"
    assert policy.split_strategy == "none"
    assert policy.test_size == 0.0
    assert policy.cv_folds is None


def test_anomaly_policy_uses_non_split_metric_defaults() -> None:
    policy = get_default_policy(ProblemKind.ANOMALY_DETECTION)

    assert policy.primary_metric_name == "anomaly_count"
    assert policy.split_strategy == "none"
    assert policy.test_size == 0.0
    assert policy.cv_folds is None


def test_compare_metric_snapshots_prefers_higher_primary_metric_then_tie_breakers() -> None:
    policy = get_default_policy(ProblemKind.REGRESSION)
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
