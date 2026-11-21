"""Prepare fit and tuning requests, including dataset identity and text resources."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..exceptions import DatasetSourceMissingError, ValidationError
from .audit_contracts import ExecutionOrigin
from .data_tokenization_contracts import StagedTextResourceInput, TextPreparationInput, TextProcessingOptions
from .dataset_inspection import DatasetInspection, InspectDatasetInput
from .dataset_service import DatasetService
from .ml.contracts import (
    ColumnSelection,
    DatasetSnapshotFact,
    EvaluationPolicySnapshot,
    FitTaskRequest,
    ForecastOptions,
    HyperparameterTuningPayload,
    HyperparameterTuningTaskRequest,
    ManualTrainingPayload,
    TaskContinuationPlan,
    TrainedModelContextPayload,
)
from .ml.evaluation import get_default_policy
from .ml.registry import get_model_catalog_entry, get_model_service
from .ml.types import ColumnRoleBinding, ModelCatalogEntry, ModelFamily
from .ml_column_bindings import ColumnBindingService
from .storage.identity import reserve_ids
from .storage.models import DatasetRow, MLTaskType

_MULTILINGUAL_TEXT_MODEL_KEYS = frozenset(
    {
        "text.classification.multilingual_logistic_regression_tfidf",
        "text.clustering.multilingual_kmeans_tfidf",
        "text.topic_modeling.multilingual_lda",
        "text.similarity.multilingual_tfidf_cosine",
    }
)
_MAX_TEXT_RESOURCE_ROWS = 20_000
_MULTILINGUAL_TEXT_RETRIEVAL_KEY = "text.similarity.multilingual_tfidf_cosine"
_MAX_EXACT_TEXT_RETRIEVAL_ROWS = 2_000


class FitWithEvaluateInput(SQLModel):
    origin: ExecutionOrigin | None = None
    binding_id: int
    run_name: str | None = None
    model_key: str
    params: dict[str, Any] = Field(default_factory=dict)


class TuneWithEvaluateInput(SQLModel):
    origin: ExecutionOrigin | None = None
    binding_id: int
    run_name: str | None = None
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


@dataclass(frozen=True)
class _TrainingContext:
    project_id: int
    dataset: DatasetRow
    run_name: str
    catalog: ModelCatalogEntry
    train_role_bindings: list[ColumnRoleBinding]
    column_selection: ColumnSelection
    evaluation_policy: EvaluationPolicySnapshot
    inspection: DatasetInspection
    dataset_snapshot: DatasetSnapshotFact


class TrainingInputPreparation:
    def __init__(
        self,
        session_factory: sessionmaker,
        dataset_service: DatasetService,
        column_bindings: ColumnBindingService,
    ) -> None:
        self._session_factory = session_factory
        self._dataset_service = dataset_service
        self._column_bindings = column_bindings

    def build_fit_request(self, input_data: FitWithEvaluateInput) -> FitTaskRequest:
        context = self._build_training_context(input_data)
        self._validate_model_runtime_admission(context)
        model_service = get_model_service(input_data.model_key)
        try:
            params_model = model_service.validate_params(input_data.params)
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

        return FitTaskRequest(
            task_id=reserve_ids(self._session_factory)[0],
            project_id=context.project_id,
            dataset_id=context.dataset.id,
            dataset_source_path=context.dataset.source_path,
            evaluation_kind=context.catalog.evaluation_kind,
            train_role_bindings=[binding.model_dump(mode="json") for binding in context.train_role_bindings],
            evaluation_policy=context.evaluation_policy,
            dataset_snapshot=context.dataset_snapshot,
            forecast_options=(
                ForecastOptions.model_validate(params_model.model_dump(mode="python"))
                if context.catalog.model_family is ModelFamily.FORECASTING
                else None
            ),
            text_preparation=self._build_text_preparation_input(
                context,
                params_model,
            ),
            continuation_plan=(
                TaskContinuationPlan(next_operation=MLTaskType.EVALUATE.value)
                if context.catalog.supports_evaluation
                else None
            ),
            manual_training=ManualTrainingPayload(
                model_key=input_data.model_key,
                params=params_model.model_dump(mode="json", by_alias=True),
            ),
            trained_model_context=self._build_trained_model_context(context),
        )

    def build_tuning_request(self, input_data: TuneWithEvaluateInput) -> HyperparameterTuningTaskRequest:
        context = self._build_training_context(input_data)
        if not context.catalog.supports_hyperparameter_tuning:
            raise ValidationError(
                f"Model '{input_data.model_key}' does not support hyperparameter tuning."
            )
        model_service = get_model_service(input_data.model_key)
        try:
            param_grid_model = model_service.validate_param_grid(input_data.param_grid)
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

        return HyperparameterTuningTaskRequest(
            task_id=reserve_ids(self._session_factory)[0],
            project_id=context.project_id,
            dataset_id=context.dataset.id,
            dataset_source_path=context.dataset.source_path,
            evaluation_kind=context.catalog.evaluation_kind,
            train_role_bindings=[binding.model_dump(mode="json") for binding in context.train_role_bindings],
            evaluation_policy=context.evaluation_policy,
            dataset_snapshot=context.dataset_snapshot,
            forecast_options=(
                ForecastOptions.model_validate(param_grid_model.model_dump(mode="python"))
                if context.catalog.model_family is ModelFamily.FORECASTING
                else None
            ),
            continuation_plan=(
                TaskContinuationPlan(next_operation=MLTaskType.EVALUATE.value)
                if context.catalog.supports_evaluation
                else None
            ),
            hyperparameter_tuning=HyperparameterTuningPayload(
                model_key=input_data.model_key,
                param_grid=param_grid_model.model_dump(mode="json", by_alias=True),
            ),
            trained_model_context=self._build_trained_model_context(context),
        )

    @staticmethod
    def _validate_model_runtime_admission(context: "_TrainingContext") -> None:
        if (
            context.catalog.model_key == _MULTILINGUAL_TEXT_RETRIEVAL_KEY
            and context.inspection.row_count > _MAX_EXACT_TEXT_RETRIEVAL_ROWS
        ):
            raise ValidationError(
                "Exact multilingual text retrieval supports at most "
                f"{_MAX_EXACT_TEXT_RETRIEVAL_ROWS:,} source rows in v1."
            )

    def _build_training_context(
        self,
        input_data: FitWithEvaluateInput | TuneWithEvaluateInput,
    ) -> "_TrainingContext":
        model_key = input_data.model_key
        binding = self._column_bindings.resolve(input_data.binding_id, model_key=model_key)
        feature_columns = binding.feature_columns
        target_columns = binding.target_columns
        run_name = (input_data.run_name or "").strip()

        catalog = get_model_catalog_entry(model_key)
        requires_complete_target = any(role.name == "target" and role.required for role in catalog.train_role_schema.roles)
        if requires_complete_target and len(target_columns) != 1:
            raise ValidationError("The selected model requires exactly one target column.")

        return _TrainingContext(
            project_id=binding.dataset.project_id,
            dataset=binding.dataset,
            run_name=run_name or binding.dataset.name,
            catalog=catalog,
            train_role_bindings=list(binding.role_bindings),
            column_selection=ColumnSelection(
                feature_columns=feature_columns,
                target_columns=target_columns,
            ),
            evaluation_policy=get_default_policy(
                catalog.evaluation_kind,
                model_key=model_key,
                summary_metric_name=catalog.summary_metric_name,
                group_aware=get_model_service(model_key).uses_automatic_groups or any(
                    role_binding.role == "group" and role_binding.columns
                    for role_binding in binding.role_bindings
                ),
            ),
            inspection=binding.inspection,
            dataset_snapshot=binding.dataset_snapshot,
        )

    def _build_trained_model_context(self, context: "_TrainingContext") -> TrainedModelContextPayload:
        return TrainedModelContextPayload(
            run_name=context.run_name,
            dataset_name=context.dataset.name,
            dataset_file_name=context.inspection.file_name,
            evaluation_kind=context.catalog.evaluation_kind.value,
            model_family=context.catalog.model_family.value,
            model_task_kind=context.catalog.model_task_kind.value,
            train_role_bindings=[binding.model_dump(mode="json") for binding in context.train_role_bindings],
            apply_role_schema=context.catalog.apply_role_schema.model_dump(mode="json"),
            result_contract=context.catalog.result_contract.model_dump(mode="json"),
            dataset_row_count=context.inspection.row_count,
            dataset_column_count=context.inspection.column_count,
            preview_columns=list(context.inspection.preview_columns),
            preview_rows=[list(row) for row in context.inspection.preview_rows],
        )

    def _build_text_preparation_input(
        self,
        context: "_TrainingContext",
        params_model: Any,
    ) -> TextPreparationInput | None:
        if context.catalog.model_key not in _MULTILINGUAL_TEXT_MODEL_KEYS:
            return None
        params = params_model.model_dump(mode="python")
        custom_ids = self._text_resource_dataset_ids(
            params.get("custom_dictionary_dataset_ids"),
            field_name="custom_dictionary_dataset_ids",
        )
        stopword_ids = self._text_resource_dataset_ids(
            params.get("stopword_dataset_ids"),
            field_name="stopword_dataset_ids",
        )
        if set(custom_ids) & set(stopword_ids):
            raise ValidationError(
                "A text resource Dataset cannot be both a custom dictionary and a stopword list."
            )
        return TextPreparationInput.model_validate(
            {
                "tokenizer_profile": params.get("preparation_profile"),
                "phrase_mode": params.get("phrase_mode"),
                **{name: params[name] for name in TextProcessingOptions.model_fields if name in params},
                "custom_dictionary_resources": [
                    self._stage_text_resource(context, dataset_id)
                    for dataset_id in custom_ids
                ],
                "stopword_resources": [
                    self._stage_text_resource(context, dataset_id)
                    for dataset_id in stopword_ids
                ],
            }
        )

    @staticmethod
    def _text_resource_dataset_ids(value: Any, *, field_name: str) -> list[int]:
        if value is None:
            return []
        if not isinstance(value, list) or any(
            type(item) is not int or item < 1 for item in value
        ):
            raise ValidationError(f"{field_name} must contain registered Dataset ids.")
        if len(value) != len(set(value)):
            raise ValidationError(f"{field_name} cannot contain duplicate Dataset ids.")
        return value

    def _stage_text_resource(
        self,
        context: "_TrainingContext",
        dataset_id: int,
    ) -> StagedTextResourceInput:
        dataset = self._dataset_service.get_dataset(dataset_id)
        if dataset.project_id != context.project_id:
            raise ValidationError(
                "Text preparation resources must belong to the training project."
            )
        source_path = Path(dataset.source_path)
        if not source_path.is_file():
            raise DatasetSourceMissingError("Text preparation resource source file is missing.")
        inspection = self._dataset_service.inspect_source_file(
            InspectDatasetInput(source_path=str(source_path.resolve()))
        )
        if inspection.column_count != 1 or not 1 <= inspection.row_count <= _MAX_TEXT_RESOURCE_ROWS:
            raise ValidationError(
                "Each text preparation resource must contain one term column and 1-20,000 rows."
            )
        digest = hashlib.sha256()
        with source_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return StagedTextResourceInput(
            dataset_id=dataset.id,
            absolute_path=str(source_path.resolve()),
            source_sha256=digest.hexdigest(),
        )
