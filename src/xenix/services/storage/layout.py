from __future__ import annotations

from pathlib import Path

from ...config import AppPaths

DATABASE_FILE_NAME = "xenix.db"


def database_path(paths: AppPaths) -> Path:
    return paths.state / DATABASE_FILE_NAME


def dataset_temp_root(paths: AppPaths) -> Path:
    return paths.temp / "datasets"


def dataset_temp_dir(paths: AppPaths, owner_id: str) -> Path:
    return dataset_temp_root(paths) / owner_id


def artifact_models_root(paths: AppPaths) -> Path:
    return paths.artifacts / "models"


def artifact_training_root(paths: AppPaths) -> Path:
    return paths.artifacts / "training"


def artifact_inference_root(paths: AppPaths) -> Path:
    return paths.artifacts / "inference"


def ml_task_parent_root(paths: AppPaths) -> Path:
    return paths.artifacts / "ml-tasks"


def ml_task_root(paths: AppPaths, ml_task_id: str) -> Path:
    return ml_task_parent_root(paths) / ml_task_id


def task_artifact_dir(paths: AppPaths, ml_task_id: str, family: str) -> Path:
    return ml_task_root(paths, ml_task_id) / family


def ensure_storage_layout(paths: AppPaths) -> None:
    for directory in (
        dataset_temp_root(paths),
        artifact_models_root(paths),
        artifact_training_root(paths),
        artifact_inference_root(paths),
        ml_task_parent_root(paths),
    ):
        directory.mkdir(parents=True, exist_ok=True)
