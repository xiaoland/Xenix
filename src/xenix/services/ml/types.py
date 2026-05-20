from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field

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


class ModelFamily(StrEnum):
    SUPERVISED = "supervised"
    CLUSTERING = "clustering"
    ANOMALY_DETECTION = "anomaly_detection"
    ASSOCIATION_RULES = "association_rules"
    RECOMMENDATION = "recommendation"


class ModelTaskKind(StrEnum):
    PREDICTOR = "predictor"
    SEGMENTER = "segmenter"
    ANOMALY_SCORER = "anomaly_scorer"
    RULE_MINER = "rule_miner"
    RECOMMENDER = "recommender"


class ColumnRoleKind(StrEnum):
    SINGLE_COLUMN = "single_column"
    MANY_COLUMNS = "many_columns"


class ModelRoleDefinition(BaseModel):
    name: str
    kind: ColumnRoleKind
    required: bool = True
    description: str = ""


class ColumnRoleBinding(BaseModel):
    role: str
    columns: list[str] = Field(default_factory=list)
    role_kind: ColumnRoleKind | None = None
    required: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelRoleSchema(BaseModel):
    roles: list[ModelRoleDefinition] = Field(default_factory=list)
    additional_roles: bool = False


class ModelResultContract(BaseModel):
    train_result_kinds: list[str] = Field(default_factory=list)
    apply_result_kinds: list[str] = Field(default_factory=list)
    preview_kinds: list[str] = Field(default_factory=list)


class ModelCatalogEntry(BaseModel):
    model_key: str
    display_name: str
    problem_kind: ProblemKind
    model_family: ModelFamily
    model_task_kind: ModelTaskKind
    family: str = "General"
    guidance: str = ""
    recommendation_tier: int = 100
    requires_target: bool
    supports_fit: bool = True
    supports_hyperparameter_tuning: bool
    train_role_schema: ModelRoleSchema
    apply_role_schema: ModelRoleSchema
    result_contract: ModelResultContract
    param_schema: dict[str, Any]
    param_grid_schema: dict[str, Any] | None = None


class ModelServiceBase(ABC):
    key: ClassVar[str]
    display_name: ClassVar[str]
    problem_kind: ClassVar[ProblemKind]
    family: ClassVar[str] = "General"
    guidance: ClassVar[str] = ""
    recommendation_tier: ClassVar[int] = 100
    requires_target: ClassVar[bool] = True
    supports_fit: ClassVar[bool] = True
    supports_hyperparameter_tuning: ClassVar[bool] = True
    model_family: ClassVar[ModelFamily | None] = None
    model_task_kind: ClassVar[ModelTaskKind | None] = None
    train_role_schema: ClassVar[ModelRoleSchema | None] = None
    apply_role_schema: ClassVar[ModelRoleSchema | None] = None
    result_contract: ClassVar[ModelResultContract | None] = None
    params_model: ClassVar[type[BaseModel]]
    param_grid_model: ClassVar[type[BaseModel] | None] = None

    @classmethod
    def catalog_entry(cls) -> ModelCatalogEntry:
        model_family = cls.model_family or cls._default_model_family()
        model_task_kind = cls.model_task_kind or cls._default_model_task_kind()
        return ModelCatalogEntry(
            model_key=cls.key,
            display_name=cls.display_name,
            problem_kind=cls.problem_kind,
            model_family=model_family,
            model_task_kind=model_task_kind,
            family=cls.family,
            guidance=cls.guidance,
            recommendation_tier=cls.recommendation_tier,
            requires_target=cls.requires_target,
            supports_fit=cls.supports_fit,
            supports_hyperparameter_tuning=cls.supports_hyperparameter_tuning,
            train_role_schema=cls.train_role_schema or cls._default_train_role_schema(),
            apply_role_schema=cls.apply_role_schema or cls._default_apply_role_schema(),
            result_contract=cls.result_contract or cls._default_result_contract(model_task_kind),
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
    def _default_model_family(cls) -> ModelFamily:
        if cls.problem_kind in {ProblemKind.REGRESSION, ProblemKind.CLASSIFICATION}:
            return ModelFamily.SUPERVISED
        if cls.problem_kind is ProblemKind.CLUSTERING:
            return ModelFamily.CLUSTERING
        if cls.problem_kind is ProblemKind.ANOMALY_DETECTION:
            return ModelFamily.ANOMALY_DETECTION
        raise ValueError(f"Problem kind '{cls.problem_kind}' has no default model family.")

    @classmethod
    def _default_model_task_kind(cls) -> ModelTaskKind:
        if cls.problem_kind in {ProblemKind.REGRESSION, ProblemKind.CLASSIFICATION}:
            return ModelTaskKind.PREDICTOR
        if cls.problem_kind is ProblemKind.CLUSTERING:
            return ModelTaskKind.SEGMENTER
        if cls.problem_kind is ProblemKind.ANOMALY_DETECTION:
            return ModelTaskKind.ANOMALY_SCORER
        raise ValueError(f"Problem kind '{cls.problem_kind}' has no default model task kind.")

    @classmethod
    def _default_train_role_schema(cls) -> ModelRoleSchema:
        roles = [
            ModelRoleDefinition(
                name="feature",
                kind=ColumnRoleKind.MANY_COLUMNS,
                required=True,
                description="Input columns used to train the analyzer.",
            )
        ]
        if cls.requires_target:
            roles.append(
                ModelRoleDefinition(
                    name="target",
                    kind=ColumnRoleKind.SINGLE_COLUMN,
                    required=True,
                    description="Outcome column the analyzer learns to predict.",
                )
            )
        return ModelRoleSchema(roles=roles, additional_roles=False)

    @classmethod
    def _default_apply_role_schema(cls) -> ModelRoleSchema:
        return ModelRoleSchema(
            roles=[
                ModelRoleDefinition(
                    name="feature",
                    kind=ColumnRoleKind.MANY_COLUMNS,
                    required=True,
                    description="Input columns required when applying the trained analyzer.",
                )
            ],
            additional_roles=False,
        )

    @classmethod
    def _default_result_contract(cls, model_task_kind: ModelTaskKind) -> ModelResultContract:
        if model_task_kind is ModelTaskKind.PREDICTOR:
            return ModelResultContract(
                train_result_kinds=["model", "metrics", "report"],
                apply_result_kinds=["table"],
                preview_kinds=["model", "table", "file"],
            )
        if model_task_kind is ModelTaskKind.SEGMENTER:
            return ModelResultContract(
                train_result_kinds=["model", "table"],
                apply_result_kinds=["table"],
                preview_kinds=["model", "table", "file"],
            )
        if model_task_kind is ModelTaskKind.ANOMALY_SCORER:
            return ModelResultContract(
                train_result_kinds=["model", "table"],
                apply_result_kinds=["table"],
                preview_kinds=["model", "table", "file"],
            )
        if model_task_kind is ModelTaskKind.RULE_MINER:
            return ModelResultContract(
                train_result_kinds=["model", "table"],
                apply_result_kinds=["table"],
                preview_kinds=["model", "table", "file"],
            )
        if model_task_kind is ModelTaskKind.RECOMMENDER:
            return ModelResultContract(
                train_result_kinds=["model", "table"],
                apply_result_kinds=["table"],
                preview_kinds=["model", "table", "file"],
            )
        return ModelResultContract()

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
