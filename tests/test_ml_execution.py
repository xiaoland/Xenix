import time
from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_service import (
    BulkTuneWithEvaluateInput,
    BulkTuningSelection,
    FitWithEvaluateInput,
    InferWithFilesInput,
    MLService,
    TuneWithEvaluateInput,
)
from xenix.services.ml_task_service import MLTaskService
from xenix.services.project_service import CreateProjectInput, ProjectService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskArtifactKind, MLTaskStatus, MLTaskType
from xenix.services.trained_model_metadata import parse_trained_model_metadata
from xenix.services.work_item_service import CreateWorkItemInput, WorkItemService


def _build_services(
    monkeypatch,
    tmp_path: Path,
) -> tuple[ProjectService, WorkItemService, DatasetService, MLTaskService, MLService]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    project_service = ProjectService(context.session_factory)
    work_item_service = WorkItemService(context.session_factory, paths)
    dataset_service = DatasetService(context.session_factory, paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    ml_service = MLService(
        paths,
        context.session_factory,
        dataset_service,
        work_item_service,
        ml_task_service,
    )
    return project_service, work_item_service, dataset_service, ml_task_service, ml_service


def _register_dataset(
    dataset_service: DatasetService,
    project_id: str,
    dataset_path: Path,
    *,
    name: str,
) -> object:
    return dataset_service.register_dataset(
        RegisterDatasetInput(project_id=project_id, source_path=str(dataset_path.resolve()), name=name)
    )


def _create_work_item(
    work_item_service: WorkItemService,
    project_id: str,
    source_dataset_id: str,
    *,
    name: str,
    feature_columns: list[str],
    target_columns: list[str],
) -> object:
    return work_item_service.create_work_item(
        CreateWorkItemInput(
            project_id=project_id,
            name=name,
            source_dataset_id=source_dataset_id,
            feature_columns=feature_columns,
            target_columns=target_columns,
        )
    )


def _wait_for_terminal_tasks(
    ml_service: MLService,
    work_item_id: str,
    expected_count: int,
    timeout_seconds: float = 60.0,
) -> list:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        tasks = ml_service.list_work_item_tasks(work_item_id)
        if len(tasks) >= expected_count and all(
            task.status in {MLTaskStatus.SUCCEEDED, MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}
            for task in tasks
        ):
            return tasks
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for ML tasks to complete.")


def _wait_for_terminal_dataset_tasks(
    ml_service: MLService,
    dataset_id: str,
    expected_count: int,
    timeout_seconds: float = 60.0,
) -> list:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        tasks = ml_service.list_dataset_tasks(dataset_id)
        if len(tasks) >= expected_count and all(
            task.status in {MLTaskStatus.SUCCEEDED, MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}
            for task in tasks
        ):
            return tasks
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for dataset-scoped ML tasks to complete.")


def _wait_for_best_trained_model_id(
    work_item_service: WorkItemService,
    work_item_id: str,
    timeout_seconds: float = 30.0,
) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        work_item = work_item_service.get_work_item(work_item_id)
        if work_item.best_trained_model_id is not None:
            return work_item.best_trained_model_id
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for the work item to receive a best trained model.")


def _wait_for_dataset_trained_models(
    ml_service: MLService,
    dataset_id: str,
    expected_count: int,
    *,
    require_evaluation: bool = False,
    timeout_seconds: float = 30.0,
) -> list:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        trained_models = ml_service.list_dataset_trained_models(dataset_id)
        if len(trained_models) >= expected_count:
            if not require_evaluation:
                return trained_models
            metadata = parse_trained_model_metadata(trained_models[0].metadata_payload)
            if metadata is not None and metadata.evaluation_primary_metric_name is not None:
                return trained_models
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for dataset-scoped trained models.")


def test_fit_with_evaluate_runs_in_background_and_persists_best_model(monkeypatch, tmp_path: Path) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n"
        "6,6,18\n"
        "7,5,19\n"
        "8,4,20\n"
        "9,7,25\n"
        "10,8,28\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Demand")
    work_item = _create_work_item(
        work_item_service,
        project.id,
        dataset.id,
        name="Demand",
        feature_columns=["feature_a", "feature_b"],
        target_columns=["target"],
    )

    fit_task = ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=work_item.id,
            model_key="regression.linear",
            params={"fit_intercept": True},
        )
    )

    tasks = _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=2)
    trained_models = ml_service.list_trained_models(work_item.id)
    best_model_id = _wait_for_best_trained_model_id(work_item_service, work_item.id)
    work_item_after = work_item_service.get_work_item(work_item.id)
    fit_details = ml_service.get_task_details(fit_task.id)

    assert len(tasks) == 2
    assert {task.task_type for task in tasks} == {MLTaskType.FIT, MLTaskType.EVALUATE}
    assert all(task.status is MLTaskStatus.SUCCEEDED for task in tasks)
    assert len(trained_models) == 1
    assert best_model_id == trained_models[0].id
    assert work_item_after.best_trained_model_id == trained_models[0].id
    assert len(fit_details.artifacts) == 3
    key_driver_artifacts = [
        artifact for artifact in fit_details.artifacts if artifact.artifact_kind is MLTaskArtifactKind.EXPORT_FILE
    ]
    assert len(key_driver_artifacts) == 1
    key_driver_path = Path(key_driver_artifacts[0].absolute_path)
    assert key_driver_path.name == "key_drivers.csv"
    assert "feature,importance" in key_driver_path.read_text(encoding="utf-8")
    assert fit_details.task.result_payload["result_summary"]["key_driver_report"] is True
    assert any(log.level == "INFO" for log in fit_details.logs)
    metadata = parse_trained_model_metadata(trained_models[0].metadata_payload)
    assert metadata is not None
    assert metadata.source_work_item_name == "Demand"
    assert metadata.source_dataset_name == "Demand"
    assert metadata.feature_columns == ["feature_a", "feature_b"]
    assert metadata.target_columns == ["target"]
    assert metadata.preview_columns == ["feature_a", "feature_b", "target"]
    assert metadata.preview_rows[0] == ["1", "2", "5"]
    assert metadata.training_params == {"fit_intercept": True}
    assert metadata.evaluation_primary_metric_name == "r2"
    assert "r2" in metadata.evaluation_metrics
    assert metadata.artifact_file_name.endswith(".joblib")


def test_dataset_scoped_fit_evaluate_and_inference_run_without_work_item(monkeypatch, tmp_path: Path) -> None:
    project_service, _work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "direct-demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n"
        "6,6,18\n"
        "7,5,19\n"
        "8,4,20\n"
        "9,7,25\n"
        "10,8,28\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Direct Demand")

    fit_task = ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            dataset_id=dataset.id,
            feature_columns=["feature_a", "feature_b"],
            target_columns=["target"],
            run_name="Direct demand analysis",
            model_key="regression.linear",
            params={"fit_intercept": True},
        )
    )
    tasks = _wait_for_terminal_dataset_tasks(ml_service, dataset.id, expected_count=2)
    trained_models = _wait_for_dataset_trained_models(
        ml_service,
        dataset.id,
        expected_count=1,
        require_evaluation=True,
    )
    fit_details = ml_service.get_task_details(fit_task.id)

    inference_input = tmp_path / "direct-infer.csv"
    inference_input.write_text("feature_a,feature_b\n11,9\n12,10\n", encoding="utf-8")
    inference_task = ml_service.infer(
        InferWithFilesInput(
            dataset_id=dataset.id,
            feature_columns=["feature_a", "feature_b"],
            trained_model_id=trained_models[0].id,
            input_files=[str(inference_input.resolve())],
        )
    )
    tasks_after_inference = _wait_for_terminal_dataset_tasks(ml_service, dataset.id, expected_count=3)
    inference_details = ml_service.get_task_details(inference_task.id)
    result_dataset = dataset_service.get_dataset_by_ml_task(inference_task.id)
    metadata = parse_trained_model_metadata(trained_models[0].metadata_payload)

    assert {task.task_type for task in tasks} == {MLTaskType.FIT, MLTaskType.EVALUATE}
    assert all(task.work_item_id is None for task in tasks_after_inference)
    assert all(task.status is MLTaskStatus.SUCCEEDED for task in tasks_after_inference)
    assert len(trained_models) == 1
    assert fit_details.task.result_payload is not None
    assert fit_details.task.result_payload["trained_model_id"] == trained_models[0].id
    assert metadata is not None
    assert metadata.source_work_item_name == "Direct demand analysis"
    assert metadata.evaluation_primary_metric_name == "r2"
    assert inference_details.task.task_type is MLTaskType.INFERENCE
    assert result_dataset is not None
    assert "prediction" in Path(result_dataset.source_path).read_text(encoding="utf-8").splitlines()[0]
    assert [artifact.artifact_kind for artifact in inference_details.artifacts] == [MLTaskArtifactKind.INFERENCE_RESULT]


def test_clustering_fit_runs_without_follow_up_evaluate_and_persists_export_artifact(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "segments.csv"
    dataset_file.write_text(
        "spend,visits,segment\n"
        "100,1,A\n"
        "110,1,A\n"
        "120,2,A\n"
        "420,9,C\n"
        "430,8,C\n"
        "440,9,C\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Segments")
    work_item = _create_work_item(
        work_item_service,
        project.id,
        dataset.id,
        name="Segments",
        feature_columns=["spend", "visits", "segment"],
        target_columns=[],
    )

    fit_task = ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=work_item.id,
            model_key="clustering.kmeans",
            params={"n_clusters": 2, "n_init": 10, "max_iter": 200},
        )
    )

    tasks = _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=1)
    trained_models = ml_service.list_trained_models(work_item.id)
    work_item_after = work_item_service.get_work_item(work_item.id)
    fit_details = ml_service.get_task_details(fit_task.id)

    assert len(tasks) == 1
    assert tasks[0].task_type is MLTaskType.FIT
    assert tasks[0].status is MLTaskStatus.SUCCEEDED
    assert len(trained_models) == 1
    assert work_item_after.best_trained_model_id is None
    assert len(fit_details.artifacts) == 2
    assert any(artifact.artifact_kind is MLTaskArtifactKind.MODEL for artifact in fit_details.artifacts)
    export_artifact = next(
        artifact for artifact in fit_details.artifacts if artifact.artifact_kind is MLTaskArtifactKind.EXPORT_FILE
    )
    assert Path(export_artifact.absolute_path).exists()
    assert export_artifact.absolute_path.endswith("cluster_assignments.csv")
    assert fit_details.task.result_payload is not None
    assert fit_details.task.result_payload["result_summary"]["cluster_count"] == 2
    assert fit_details.task.result_payload["result_summary"]["row_count"] == 6
    metadata = parse_trained_model_metadata(trained_models[0].metadata_payload)
    assert metadata is not None
    assert metadata.target_columns == []
    assert metadata.feature_columns == ["spend", "visits", "segment"]


def test_anomaly_fit_runs_without_follow_up_evaluate_and_persists_score_artifact(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Operations"))
    dataset_file = tmp_path / "anomalies.csv"
    dataset_file.write_text(
        "amount,count,region\n"
        "10,1,North\n"
        "11,1,North\n"
        "12,1,North\n"
        "13,2,North\n"
        "14,2,North\n"
        "15,2,North\n"
        "120,20,South\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Anomalies")
    work_item = _create_work_item(
        work_item_service,
        project.id,
        dataset.id,
        name="Anomaly Run",
        feature_columns=["amount", "count", "region"],
        target_columns=[],
    )

    fit_task = ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=work_item.id,
            model_key="anomaly.isolation_forest",
            params={"n_estimators": 50, "contamination": "auto", "max_samples": "auto"},
        )
    )

    tasks = _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=1)
    fit_details = ml_service.get_task_details(fit_task.id)
    export_artifacts = [
        artifact for artifact in fit_details.artifacts if artifact.artifact_kind is MLTaskArtifactKind.EXPORT_FILE
    ]

    assert len(tasks) == 1
    assert tasks[0].task_type is MLTaskType.FIT
    assert tasks[0].status is MLTaskStatus.SUCCEEDED
    assert len(export_artifacts) == 1
    output_path = Path(export_artifacts[0].absolute_path)
    assert output_path.name == "anomaly_scores.csv"
    output_text = output_path.read_text(encoding="utf-8")
    assert "anomaly_label" in output_text
    assert "anomaly_score" in output_text
    assert "anomaly_rank" in output_text
    assert fit_details.task.result_payload["result_summary"]["anomaly_count"] >= 0
    assert fit_details.task.result_payload["result_summary"]["row_count"] == 7


def test_polynomial_regression_fit_with_evaluate_uses_p1_pipeline(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "polynomial-demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,1,3\n"
        "2,1,6\n"
        "3,2,13\n"
        "4,2,22\n"
        "5,3,37\n"
        "6,3,54\n"
        "7,4,79\n"
        "8,4,106\n"
        "9,5,141\n"
        "10,5,178\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Polynomial Demand")
    work_item = _create_work_item(
        work_item_service,
        project.id,
        dataset.id,
        name="Polynomial Demand",
        feature_columns=["feature_a", "feature_b"],
        target_columns=["target"],
    )

    fit_task = ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=work_item.id,
            model_key="regression.polynomial",
            params={"degree": 2, "fit_intercept": True},
        )
    )

    tasks = _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=2)
    trained_models = ml_service.list_trained_models(work_item.id)
    best_model_id = _wait_for_best_trained_model_id(work_item_service, work_item.id)
    fit_details = ml_service.get_task_details(fit_task.id)

    assert {task.task_type for task in tasks} == {MLTaskType.FIT, MLTaskType.EVALUATE}
    assert all(task.status is MLTaskStatus.SUCCEEDED for task in tasks)
    assert len(trained_models) == 1
    assert best_model_id == trained_models[0].id
    assert fit_details.task.result_payload is not None
    assert fit_details.task.result_payload["params"] == {"degree": 2, "fit_intercept": True}
    metadata = parse_trained_model_metadata(trained_models[0].metadata_payload)
    assert metadata is not None
    assert metadata.model_key == "regression.polynomial"
    assert metadata.evaluation_primary_metric_name == "r2"


def test_bulk_tuning_creates_one_tuning_task_per_model_and_follow_up_evaluations(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "churn.csv"
    dataset_file.write_text(
        "age,tenure,segment,label\n"
        "22,1,A,0\n"
        "25,2,A,0\n"
        "29,3,B,1\n"
        "31,4,B,1\n"
        "34,5,C,1\n"
        "36,6,C,1\n"
        "39,1,A,0\n"
        "42,2,B,0\n"
        "45,3,C,1\n"
        "48,4,A,1\n"
        "51,5,B,1\n"
        "54,6,C,1\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Churn")
    work_item = _create_work_item(
        work_item_service,
        project.id,
        dataset.id,
        name="Churn",
        feature_columns=["age", "tenure", "segment"],
        target_columns=["label"],
    )

    created = ml_service.bulk_tune_with_evaluate(
        BulkTuneWithEvaluateInput(
            work_item_id=work_item.id,
            selections=[
                BulkTuningSelection(
                    model_key="classification.logistic_regression",
                    param_grid={"C": [0.1, 1.0], "max_iter": [500, 1000]},
                ),
                BulkTuningSelection(
                    model_key="classification.random_forest",
                    param_grid={
                        "n_estimators": [50, 100],
                        "max_depth": [0, 5],
                        "max_features": ["all", "sqrt"],
                    },
                ),
            ],
        )
    )

    tasks = _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=4)

    assert len(created) == 2
    assert len(tasks) == 4
    assert [task.task_type for task in tasks].count(MLTaskType.HYPERPARAMETER_TUNING) == 2
    assert [task.task_type for task in tasks].count(MLTaskType.EVALUATE) == 2
    assert all(task.status is MLTaskStatus.SUCCEEDED for task in tasks)
    assert len(ml_service.list_trained_models(work_item.id)) == 2


def test_naive_bayes_tuning_with_evaluate_uses_p1_dense_preprocessing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "p1-churn.csv"
    dataset_file.write_text(
        "age,tenure,segment,label\n"
        "22,1,A,0\n"
        "24,2,A,0\n"
        "26,3,A,0\n"
        "28,4,B,0\n"
        "30,5,B,0\n"
        "32,6,B,0\n"
        "42,1,C,1\n"
        "44,2,C,1\n"
        "46,3,C,1\n"
        "48,4,D,1\n"
        "50,5,D,1\n"
        "52,6,D,1\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="P1 Churn")
    work_item = _create_work_item(
        work_item_service,
        project.id,
        dataset.id,
        name="P1 Churn",
        feature_columns=["age", "tenure", "segment"],
        target_columns=["label"],
    )

    tuning_task = ml_service.tune_with_evaluate(
        TuneWithEvaluateInput(
            work_item_id=work_item.id,
            model_key="classification.naive_bayes",
            param_grid={"var_smoothing": [1e-9, 1e-8]},
        )
    )

    tasks = _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=2)
    trained_models = ml_service.list_trained_models(work_item.id)
    best_model_id = _wait_for_best_trained_model_id(work_item_service, work_item.id)
    tuning_details = ml_service.get_task_details(tuning_task.id)

    assert {task.task_type for task in tasks} == {MLTaskType.HYPERPARAMETER_TUNING, MLTaskType.EVALUATE}
    assert all(task.status is MLTaskStatus.SUCCEEDED for task in tasks)
    assert len(trained_models) == 1
    assert best_model_id == trained_models[0].id
    assert tuning_details.task.result_payload is not None
    assert tuning_details.task.result_payload["model_key"] == "classification.naive_bayes"
    assert tuning_details.task.result_payload["tuning_summary"]["cv_summary"]["candidate_count"] == 2
    metadata = parse_trained_model_metadata(trained_models[0].metadata_payload)
    assert metadata is not None
    assert metadata.model_key == "classification.naive_bayes"
    assert metadata.evaluation_primary_metric_name == "f1_weighted"


def test_tuning_rejects_empty_param_grid_sequences_before_worker(monkeypatch, tmp_path: Path) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "churn.csv"
    dataset_file.write_text(
        "age,tenure,segment,label\n"
        "22,1,A,0\n"
        "25,2,A,0\n"
        "29,3,B,1\n"
        "31,4,B,1\n"
        "34,5,C,1\n"
        "36,6,C,1\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Churn")
    work_item = _create_work_item(
        work_item_service,
        project.id,
        dataset.id,
        name="Churn",
        feature_columns=["age", "tenure", "segment"],
        target_columns=["label"],
    )

    with pytest.raises(ValidationError):
        ml_service.tune_with_evaluate(
            TuneWithEvaluateInput(
                work_item_id=work_item.id,
                model_key="classification.random_forest",
                param_grid={"n_estimators": [], "max_depth": [3], "max_features": ["sqrt"]},
            )
        )


def test_inference_persists_result_dataset_and_artifact(monkeypatch, tmp_path: Path) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n"
        "6,6,18\n"
        "7,5,19\n"
        "8,4,20\n"
        "9,7,25\n"
        "10,8,28\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Demand")
    work_item = _create_work_item(
        work_item_service,
        project.id,
        dataset.id,
        name="Demand",
        feature_columns=["feature_a", "feature_b"],
        target_columns=["target"],
    )

    ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=work_item.id,
            model_key="regression.linear",
            params={"fit_intercept": True},
        )
    )
    _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=2)

    inference_input = tmp_path / "infer.csv"
    inference_input.write_text(
        "feature_a,feature_b\n11,9\n12,10\n",
        encoding="utf-8",
    )
    inference_task = ml_service.infer(
        InferWithFilesInput(
            work_item_id=work_item.id,
            input_files=[str(inference_input.resolve())],
        )
    )

    tasks = _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=3)
    details = ml_service.get_task_details(inference_task.id)
    result_dataset = dataset_service.get_dataset_by_ml_task(inference_task.id)

    assert len(tasks) == 3
    assert any(task.id == inference_task.id and task.task_type is MLTaskType.INFERENCE for task in tasks)
    assert details.task.status is MLTaskStatus.SUCCEEDED
    assert result_dataset is not None
    assert Path(result_dataset.source_path).exists()
    assert "prediction" in Path(result_dataset.source_path).read_text(encoding="utf-8").splitlines()[0]
    assert details.task.result_payload is not None
    assert details.task.result_payload["row_count"] == 2
    assert details.task.result_payload["result_dataset_id"] == result_dataset.id
    assert [artifact.artifact_kind for artifact in details.artifacts] == [MLTaskArtifactKind.INFERENCE_RESULT]


def test_inference_rejects_input_files_missing_required_features(monkeypatch, tmp_path: Path) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n"
        "6,6,18\n"
        "7,5,19\n"
        "8,4,20\n"
        "9,7,25\n"
        "10,8,28\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Demand")
    work_item = _create_work_item(
        work_item_service,
        project.id,
        dataset.id,
        name="Demand",
        feature_columns=["feature_a", "feature_b"],
        target_columns=["target"],
    )

    ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=work_item.id,
            model_key="regression.linear",
            params={"fit_intercept": True},
        )
    )
    _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=2)

    invalid_input = tmp_path / "invalid-infer.csv"
    invalid_input.write_text("feature_a\n11\n12\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        ml_service.infer(
            InferWithFilesInput(
                work_item_id=work_item.id,
                input_files=[str(invalid_input.resolve())],
            )
        )
