from __future__ import annotations

from pathlib import Path

from ...config import AppPaths

DATABASE_FILE_NAME = "xenix.db"


def database_path(paths: AppPaths) -> Path:
    return paths.state / DATABASE_FILE_NAME


def artifact_models_root(paths: AppPaths) -> Path:
    return paths.artifacts / "models"


def artifact_datasets_root(paths: AppPaths) -> Path:
    return paths.artifacts / "datasets"


def artifact_training_root(paths: AppPaths) -> Path:
    return paths.artifacts / "training"


def artifact_inference_root(paths: AppPaths) -> Path:
    return paths.artifacts / "inference"


def ml_task_parent_root(paths: AppPaths) -> Path:
    return paths.artifacts / "ml-tasks"


def ml_task_root(paths: AppPaths, ml_task_id: str) -> Path:
    return ml_task_parent_root(paths) / ml_task_id


def work_item_dataset_dir(paths: AppPaths, work_item_id: str) -> Path:
    return artifact_datasets_root(paths) / "work-items" / work_item_id


def canonical_inference_dir(paths: AppPaths, work_item_id: str) -> Path:
    return artifact_inference_root(paths) / work_item_id


def task_input_dir(paths: AppPaths, ml_task_id: str) -> Path:
    return ml_task_root(paths, ml_task_id) / "input"


def task_output_dir(paths: AppPaths, ml_task_id: str) -> Path:
    return ml_task_root(paths, ml_task_id) / "output"


def task_models_dir(paths: AppPaths, ml_task_id: str) -> Path:
    return ml_task_root(paths, ml_task_id) / "models"


def task_request_path(paths: AppPaths, ml_task_id: str) -> Path:
    return ml_task_root(paths, ml_task_id) / "request.json"


def task_result_path(paths: AppPaths, ml_task_id: str) -> Path:
    return ml_task_root(paths, ml_task_id) / "result.json"


def task_logs_path(paths: AppPaths, ml_task_id: str) -> Path:
    return ml_task_root(paths, ml_task_id) / "logs.jsonl"


def canonical_model_dir(paths: AppPaths, work_item_id: str) -> Path:
    return artifact_models_root(paths) / work_item_id


def dataset_model_dir(paths: AppPaths, dataset_id: str) -> Path:
    return artifact_models_root(paths) / "datasets" / dataset_id


def dataset_inference_dir(paths: AppPaths, dataset_id: str) -> Path:
    return artifact_inference_root(paths) / "datasets" / dataset_id


def ensure_storage_layout(paths: AppPaths) -> None:
    for directory in (
        artifact_datasets_root(paths),
        artifact_models_root(paths),
        artifact_training_root(paths),
        artifact_inference_root(paths),
        ml_task_parent_root(paths),
    ):
        directory.mkdir(parents=True, exist_ok=True)
