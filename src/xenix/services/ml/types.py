from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel

from ..storage.models import ProblemKind
from .contracts import (
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    FitTaskResult,
    HyperparameterTuningTaskRequest,
    HyperparameterTuningTaskResult,
    InferenceTaskRequest,
    InferenceTaskResult,
)


class ModelCatalogEntry(BaseModel):
    model_key: str
    display_name: str
    problem_kind: ProblemKind
    requires_target: bool
    supports_fit: bool = True
    supports_hyperparameter_tuning: bool
    param_schema: dict[str, Any]
    param_grid_schema: dict[str, Any] | None = None


class ModelServiceBase(ABC):
    key: ClassVar[str]
    display_name: ClassVar[str]
    problem_kind: ClassVar[ProblemKind]
    requires_target: ClassVar[bool] = True
    supports_fit: ClassVar[bool] = True
    supports_hyperparameter_tuning: ClassVar[bool] = True
    params_model: ClassVar[type[BaseModel]]
    param_grid_model: ClassVar[type[BaseModel] | None] = None

    @classmethod
    def catalog_entry(cls) -> ModelCatalogEntry:
        return ModelCatalogEntry(
            model_key=cls.key,
            display_name=cls.display_name,
            problem_kind=cls.problem_kind,
            requires_target=cls.requires_target,
            supports_fit=cls.supports_fit,
            supports_hyperparameter_tuning=cls.supports_hyperparameter_tuning,
            param_schema=cls.params_model.model_json_schema(),
            param_grid_schema=(
                cls.param_grid_model.model_json_schema()
                if cls.param_grid_model is not None
                else None
            ),
        )

    @classmethod
    def validate_params(cls, payload: dict[str, Any]) -> BaseModel:
        return cls.params_model.model_validate(payload)

    @classmethod
    def validate_param_grid(cls, payload: dict[str, Any]) -> BaseModel:
        if cls.param_grid_model is None:
            raise ValueError(f"Model '{cls.key}' does not support hyperparameter tuning.")
        return cls.param_grid_model.model_validate(payload)

    @classmethod
    @abstractmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def infer(cls, request: InferenceTaskRequest, task_dir: Path) -> InferenceTaskResult:
        raise NotImplementedError
