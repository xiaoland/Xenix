import time
from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_service import (
    BulkTuneWithEvaluateInput,
    BulkTuningSelection,
    CreateColumnSelectionInput,
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


def _build_services(monkeypatch, tmp_path: Path) -> tuple[ProjectService, DatasetService, MLTaskService, MLService]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    project_service = ProjectService(context.session_factory)
    dataset_service = DatasetService(context.session_factory, paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    ml_service = MLService(
        paths,
        context.session_factory,
        dataset_service,
        ml_task_service,
    )
    return project_service, dataset_service, ml_task_service, ml_service


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


def _create_selection(
    ml_service: MLService,
    dataset_id: str,
    feature_columns: list[str],
    target_columns: list[str] | None = None,
) -> object:
    return ml_service.create_column_selection(
        CreateColumnSelectionInput(
            dataset_id=dataset_id,
            feature_columns=feature_columns,
            target_columns=target_columns or [],
        )
    )


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


def test_dataset_scoped_fit_evaluate_and_inference_run(monkeypatch, tmp_path: Path) -> None:
    project_service, dataset_service, _ml_task_service, ml_service = _build_services(monkeypatch, tmp_path)
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
    selection = _create_selection(ml_service, dataset.id, ["feature_a", "feature_b"], ["target"])

    fit_task = ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            selection_id=selection.id,
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
            trained_model_id=trained_models[0].id,
            input_files=[str(inference_input.resolve())],
        )
    )
    tasks_after_inference = _wait_for_terminal_dataset_tasks(ml_service, dataset.id, expected_count=3)
    inference_details = ml_service.get_task_details(inference_task.id)
    result_dataset = dataset_service.get_dataset_by_ml_task(inference_task.id)
    metadata = parse_trained_model_metadata(trained_models[0].metadata_payload)

    assert {task.task_type for task in tasks} == {MLTaskType.FIT, MLTaskType.EVALUATE}
    assert all(task.status is MLTaskStatus.SUCCEEDED for task in tasks_after_inference)
    assert len(trained_models) == 1
    assert fit_details.task.result_payload is not None
    assert fit_details.task.result_payload["trained_model_id"] == trained_models[0].id
    assert metadata is not None
    assert metadata.source_run_name == "Direct demand analysis"
    assert metadata.evaluation_primary_metric_name == "r2"
    assert inference_details.task.task_type is MLTaskType.INFERENCE
    assert result_dataset is not None
    assert "prediction" in Path(result_dataset.source_path).read_text(encoding="utf-8").splitlines()[0]
    assert [artifact.artifact_kind for artifact in inference_details.artifacts] == [MLTaskArtifactKind.INFERENCE_RESULT]


def test_clustering_fit_runs_without_follow_up_evaluate_and_persists_export_artifact(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_service, dataset_service, _ml_task_service, ml_service = _build_services(monkeypatch, tmp_path)
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
    selection = _create_selection(ml_service, dataset.id, ["spend", "visits", "segment"])

    fit_task = ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            selection_id=selection.id,
            run_name="Segments",
            model_key="clustering.kmeans",
            params={"n_clusters": 2, "n_init": 10, "max_iter": 200},
        )
    )

    tasks = _wait_for_terminal_dataset_tasks(ml_service, dataset.id, expected_count=1)
    trained_models = ml_service.list_dataset_trained_models(dataset.id)
    fit_details = ml_service.get_task_details(fit_task.id)

    assert len(tasks) == 1
    assert tasks[0].task_type is MLTaskType.FIT
    assert tasks[0].status is MLTaskStatus.SUCCEEDED
    assert len(trained_models) == 1
    assert len(fit_details.artifacts) == 2
    export_artifact = next(
        artifact for artifact in fit_details.artifacts if artifact.artifact_kind is MLTaskArtifactKind.EXPORT_FILE
    )
    assert Path(export_artifact.absolute_path).exists()
    assert export_artifact.absolute_path.endswith("cluster_assignments.csv")
    assert fit_details.task.result_payload["result_summary"]["cluster_count"] == 2
    metadata = parse_trained_model_metadata(trained_models[0].metadata_payload)
    assert metadata is not None
    assert metadata.target_columns == []
    assert metadata.feature_columns == ["spend", "visits", "segment"]


def test_bulk_tuning_creates_one_tuning_task_per_model_and_follow_up_evaluations(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_service, dataset_service, _ml_task_service, ml_service = _build_services(monkeypatch, tmp_path)
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
    selection = _create_selection(ml_service, dataset.id, ["age", "tenure", "segment"], ["label"])

    created = ml_service.bulk_tune_with_evaluate(
        BulkTuneWithEvaluateInput(
            selection_id=selection.id,
            run_name="Churn",
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

    tasks = _wait_for_terminal_dataset_tasks(ml_service, dataset.id, expected_count=4)

    assert len(created) == 2
    assert len(tasks) == 4
    assert [task.task_type for task in tasks].count(MLTaskType.HYPERPARAMETER_TUNING) == 2
    assert [task.task_type for task in tasks].count(MLTaskType.EVALUATE) == 2
    assert all(task.status is MLTaskStatus.SUCCEEDED for task in tasks)
    assert len(ml_service.list_dataset_trained_models(dataset.id)) == 2


def test_tuning_rejects_empty_param_grid_sequences_before_worker(monkeypatch, tmp_path: Path) -> None:
    project_service, dataset_service, _ml_task_service, ml_service = _build_services(monkeypatch, tmp_path)
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
    selection = _create_selection(ml_service, dataset.id, ["age", "tenure", "segment"], ["label"])

    with pytest.raises(ValidationError):
        ml_service.tune_with_evaluate(
            TuneWithEvaluateInput(
                selection_id=selection.id,
                model_key="classification.random_forest",
                param_grid={"n_estimators": [], "max_depth": [3], "max_features": ["sqrt"]},
            )
        )


def test_column_selection_error_names_missing_columns_and_suggestions(monkeypatch, tmp_path: Path) -> None:
    project_service, dataset_service, _ml_task_service, ml_service = _build_services(monkeypatch, tmp_path)
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "churn.csv"
    dataset_file.write_text(
        "Account Balance (Yuan),Last Month’s Trading Commission (Yuan),Customer Churn (Yes/No)\n"
        "22686.5,149.25,0\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Churn")

    with pytest.raises(ValidationError) as exc_info:
        ml_service.create_column_selection(
            CreateColumnSelectionInput(
                dataset_id=dataset.id,
                feature_columns=[
                    "Account Balance (Yuan)",
                    "Last Month's Trading Commission (Yuan)",
                ],
                target_columns=["Customer Churn (Yes/No)"],
            )
        )

    message = str(exc_info.value)
    assert "Missing feature columns: `Last Month's Trading Commission (Yuan)`." in message
    assert "`Last Month's Trading Commission (Yuan)` -> `Last Month’s Trading Commission (Yuan)`" in message
    assert "Available columns:" in message
    assert "Use the exact column names returned by data.peek" in message


def test_inference_rejects_input_files_missing_required_features(monkeypatch, tmp_path: Path) -> None:
    project_service, dataset_service, _ml_task_service, ml_service = _build_services(monkeypatch, tmp_path)
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
    selection = _create_selection(ml_service, dataset.id, ["feature_a", "feature_b"], ["target"])
    ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            selection_id=selection.id,
            run_name="Demand",
            model_key="regression.linear",
            params={"fit_intercept": True},
        )
    )
    _wait_for_terminal_dataset_tasks(ml_service, dataset.id, expected_count=2)
    trained_models = _wait_for_dataset_trained_models(
        ml_service,
        dataset.id,
        expected_count=1,
        require_evaluation=True,
    )
    invalid_input = tmp_path / "invalid-infer.csv"
    invalid_input.write_text("feature_a\n11\n12\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        ml_service.infer(
            InferWithFilesInput(
                trained_model_id=trained_models[0].id,
                input_files=[str(invalid_input.resolve())],
            )
        )
