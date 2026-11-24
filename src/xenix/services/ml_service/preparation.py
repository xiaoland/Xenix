from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ...config import AppPaths
from ...exceptions import DatasetSourceMissingError, ValidationError
from ..data_tokenization_contracts import (
    StagedTextResourceInput,
    TextPreparationInput,
    TextProcessingOptions,
)
from ..dataset_inspection import InspectDatasetInput
from ..dataset_service import DatasetService, MaterializeManualApplyCsvInput
from ..ml.contracts import (
    ApplyInputFile,
    DatasetSnapshotFact,
    TrainedModelContextPayload,
)
from ..storage.models import DatasetRow
from .contracts import ApplySourceInput, InlineApplyRowsInput, _TrainingContext

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


def validate_model_runtime_admission(context: _TrainingContext) -> None:
    if (
        context.catalog.model_key == _MULTILINGUAL_TEXT_RETRIEVAL_KEY
        and context.inspection.row_count > _MAX_EXACT_TEXT_RETRIEVAL_ROWS
    ):
        raise ValidationError(
            "Exact multilingual text retrieval supports at most "
            f"{_MAX_EXACT_TEXT_RETRIEVAL_ROWS:,} source rows in v1."
        )


def build_trained_model_context(context: _TrainingContext) -> TrainedModelContextPayload:
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


def build_text_preparation_input(
    dataset_service: DatasetService,
    context: _TrainingContext,
    params_model: Any,
) -> TextPreparationInput | None:
    if context.catalog.model_key not in _MULTILINGUAL_TEXT_MODEL_KEYS:
        return None
    params = params_model.model_dump(mode="python")
    custom_ids = _text_resource_dataset_ids(
        params.get("custom_dictionary_dataset_ids"),
        field_name="custom_dictionary_dataset_ids",
    )
    stopword_ids = _text_resource_dataset_ids(
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
                _stage_text_resource(dataset_service, context, dataset_id)
                for dataset_id in custom_ids
            ],
            "stopword_resources": [
                _stage_text_resource(dataset_service, context, dataset_id)
                for dataset_id in stopword_ids
            ],
        }
    )


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
    dataset_service: DatasetService,
    context: _TrainingContext,
    dataset_id: int,
) -> StagedTextResourceInput:
    dataset = dataset_service.get_dataset(dataset_id)
    if dataset.project_id != context.project_id:
        raise ValidationError(
            "Text preparation resources must belong to the training project."
        )
    source_path = Path(dataset.source_path)
    if not source_path.is_file():
        raise DatasetSourceMissingError("Text preparation resource source file is missing.")
    inspection = dataset_service.inspect_source_file(
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


def build_dataset_snapshot(
    dataset: DatasetRow,
    inspection: Any,
) -> DatasetSnapshotFact:
    source_path = Path(dataset.source_path)
    source_digest = hashlib.sha256()
    with source_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            source_digest.update(chunk)
    schema_payload = {
        "source_format": inspection.source_format.value,
        "columns": [
            {
                "name": column.name,
                "kind": column.kind.value,
                "nullable": column.nullable,
            }
            for column in inspection.columns
        ],
    }
    schema_bytes = json.dumps(
        schema_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return DatasetSnapshotFact(
        dataset_id=dataset.id,
        source_sha256=source_digest.hexdigest(),
        source_byte_size=source_path.stat().st_size,
        schema_digest=hashlib.sha256(schema_bytes).hexdigest(),
    )


def build_apply_input_files(
    paths: AppPaths,
    dataset_service: DatasetService,
    feature_columns: list[str],
    input_sources: list[ApplySourceInput],
) -> list[ApplyInputFile]:
    if not input_sources:
        raise ValidationError("Select at least one apply input file or provide inline apply rows.")
    manual_root = (paths.temp / "manual-apply").resolve()
    files: list[ApplyInputFile] = []
    for input_source in input_sources:
        raw_path = input_source.source_path
        inspection = dataset_service.inspect_source_file(
            InspectDatasetInput(source_path=str(Path(raw_path).resolve()))
        )
        available = {column.name for column in inspection.columns}
        if not set(feature_columns).issubset(available):
            raise ValidationError("Apply input file does not contain the required apply columns.")
        absolute_path = Path(inspection.source_path).resolve()
        source_kind = "manual_csv" if manual_root in absolute_path.parents else "user_file"
        files.append(
            ApplyInputFile(
                absolute_path=str(absolute_path),
                file_name=absolute_path.name,
                source_kind=source_kind,
                dataset_id=input_source.dataset_id,
                artifact_id=input_source.artifact_id,
            )
        )
    return files


def materialize_inline_apply_rows(
    dataset_service: DatasetService,
    feature_columns: list[str],
    input_rows: InlineApplyRowsInput | None,
) -> Path | None:
    if input_rows is None:
        return None

    header_index_map = _normalize_inline_header_index_map(input_rows.header_index_map)
    if set(header_index_map) != set(feature_columns):
        raise ValidationError("Inline apply columns must match the trained model apply columns exactly.")
    if not input_rows.data:
        raise ValidationError("Inline apply rows require at least one data row.")

    row_width = len(header_index_map)
    rows: list[dict[str, str | None]] = []
    for row in input_rows.data:
        if len(row) != row_width:
            raise ValidationError("Inline apply data rows must match the header index map width.")
        rows.append(
            {
                column: _normalize_inline_cell(row[header_index_map[column]])
                for column in feature_columns
            }
        )

    return dataset_service.materialize_manual_apply_csv(
        MaterializeManualApplyCsvInput(
            feature_columns=feature_columns,
            rows=rows,
        )
    )


def _normalize_inline_header_index_map(header_index_map: dict[str, int]) -> dict[str, int]:
    if not header_index_map:
        raise ValidationError("Inline apply rows require a header_index_map.")

    normalized: dict[str, int] = {}
    for raw_column, raw_index in header_index_map.items():
        column = str(raw_column).strip()
        if not column:
            raise ValidationError("Inline apply column names cannot be empty.")
        if column in normalized:
            raise ValidationError("Inline apply column names cannot be duplicated.")
        if not isinstance(raw_index, int) or isinstance(raw_index, bool) or raw_index < 0:
            raise ValidationError("Inline apply header indexes must be non-negative integers.")
        normalized[column] = raw_index

    indexes = list(normalized.values())
    if len(set(indexes)) != len(indexes):
        raise ValidationError("Inline apply header indexes cannot be duplicated.")
    if sorted(indexes) != list(range(len(indexes))):
        raise ValidationError("Inline apply header indexes must be contiguous and start at 0.")
    return normalized


def _normalize_inline_cell(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    raise ValidationError("Inline apply row values must be scalar JSON values.")
