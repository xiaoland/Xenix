"""Data tool handlers and their projection helpers."""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError as PydanticValidationError

from ...exceptions import ValidationError
from ..data_cleaning import (
    CleanOperation,
    CleanDatasetInput,
    cleaning_operation_metadata,
)
from ..data_tokenization import TokenizeDatasetInput
from ..data_tokenization_contracts import StagedTextResourceInput
from ..data_transform import (
    DataQueryInput,
    DataTransformInput,
    DatasetSqlBinding,
)
from ..dataset_inspection import InspectDatasetInput, detect_source_format, load_dataframe
from ..dataset_service import (
    DatasetDerivationInput,
    DatasetDerivationSourceInput,
)
from ..ml_service import (
    CreateColumnBindingInput,
)
from ..llm.tooling import (
    ToolExecutionContext,
    ToolSuccess,
)
from ..llm.xenix_table_text import render_xenix_table_tool_result
from .tool_inputs import (
    DataCleanInput,
    DataCleanMetadataInput,
    DataFeatureSelectInput,
    DataIntegrateInput,
    DataQueryInput as DataQueryToolInput,
    DataTokenizeInput,
    DataTransformInput as DataTransformToolInput,
)
from ._model_keys import (
    slug,
)


from ._tool_common import _raise_if_cancelled


# Synchronous wait window before a model tool returns a running_background
# receipt. ML fit/tune/apply can outlive one conversation turn: wait up to this
# window so fast tasks return results inline, otherwise hand back a receipt with
# async_state="running_background" and let the Agent poll model.task.query
# instead of blocking the turn for the task's full duration.
MODEL_APPLY_GRACE_SECONDS = 30.0
MODEL_TRAIN_GRACE_SECONDS = 60.0
MAX_CLEANING_REPORT_OPERATION_ENTRIES = 12
MAX_CLEANING_REPORT_VALIDATION_ENTRIES = 12
MAX_CLEANING_REPORT_WARNING_ENTRIES = 5
MAX_CLEANING_REPORT_COLUMN_NAMES = 6
MAX_CLEANING_REPORT_WARNING_CHARS = 240
MAX_CLEANING_REPORT_COLUMN_NAME_CHARS = 96
MAX_CLEANING_REPORT_FILL_VALUE_CHARS = 96
MODEL_HYPER_TRAIN_GRACE_SECONDS = 60.0
MAX_MODEL_TASK_LOG_CHARS = 500
MAX_MODEL_METRICS = 24
MAX_MODEL_ROLE_BINDINGS = 16
MAX_MODEL_ROLE_COLUMNS = 20
MAX_MODEL_COLUMN_NAME_CHARS = 96
_LOCAL_PATH_PATTERN = re.compile(r"(?:(?:[A-Za-z]:[\\/]|\\\\|/)[^\s'\"<>]*)")


class DataTools:
    def __init__(
        self,
        *,
        paths,
        dataset_service,
        data_cleaning_service,
        data_tokenization_service,
        data_transform_service,
        ml_service,
        preprocessing_worker_runner,
    ) -> None:
        self._paths = paths
        self._dataset_service = dataset_service
        self._data_cleaning_service = data_cleaning_service
        self._data_tokenization_service = data_tokenization_service
        self._data_transform_service = data_transform_service
        self._ml_service = ml_service
        self._preprocessing_worker_runner = preprocessing_worker_runner


    def _data_integrate(
        self,
        input_data: DataIntegrateInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        datasets = [
            self._dataset_service.get_dataset(dataset_id)
            for dataset_id in input_data.dataset_ids
        ]
        frames = [self._load_frame(Path(dataset.source_path).expanduser().resolve()) for dataset in datasets]
        output_dir = self._paths.artifacts / "datasets" / "integrated"
        output_dir.mkdir(parents=True, exist_ok=True)
        name = input_data.name or "Integrated dataset"
        output_path = output_dir / f"{slug(name)}-{int(time.time())}.csv"
        pd.concat(frames, ignore_index=True).to_csv(output_path, index=False)
        input_dataset_ids = [dataset.id for dataset in datasets]
        payload = self._register_generated_dataset_result(
            context,
            output_path=output_path,
            name=name,
            summary="Integrated dataset created.",
            derivation=DatasetDerivationInput(
                operation_name="data.integrate",
                inputs=[
                    DatasetDerivationSourceInput(dataset_id=dataset.id)
                    for dataset in datasets
                ],
                parameters_payload=input_data.model_dump(
                    mode="json",
                    exclude={"dataset_ids"},
                    exclude_none=True,
                ),
            ),
            metadata_payload={"input_dataset_ids": input_dataset_ids},
        )
        payload["input_dataset_ids"] = input_dataset_ids
        return self._tabular_tool_success("data.integrate", payload)

    def _data_clean(
        self,
        input_data: DataCleanInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        dataset = self._dataset_service.get_dataset(input_data.dataset_id)
        name = input_data.name or f"{dataset.name} cleaned"
        operations = [
            operation.model_dump(mode="python")
            for operation in input_data.operations
        ]
        if not operations:
            report: dict[str, Any] = {
                "row_count_before": None,
                "row_count_after": None,
                "rows_removed": 0,
                "operations": [],
                "validation_rules": [],
                "warnings": [],
                "no_op": True,
            }
            return self._tabular_tool_success(
                "data.clean",
                {
                    "dataset_id": dataset.id,
                    "source_dataset_id": dataset.id,
                    "scope": "whole_dataset",
                    "holdout_safe_model_preparation": False,
                    "cleaning_report": report,
                    "message": (
                        "No whole-Dataset cleaning operations were requested. Nothing happened. "
                        "Use split-fitted model preparation for holdout-safe learned preprocessing."
                    ),
                },
            )
        try:
            clean_input = CleanDatasetInput(
                source_path=dataset.source_path,
                name=name,
                operations=[
                    CleanOperation(**operation)
                    for operation in operations
                ],
            )
        except PydanticValidationError as exc:
            raise ValidationError("operations must contain objects with operation and optional params.") from exc
        clean_result = self._data_cleaning_service.clean_dataset(clean_input)
        row_count_before = int(clean_result.report.get("row_count_before", 0))
        row_count_after = int(clean_result.report.get("row_count_after", 0))
        payload = self._register_generated_dataset_result(
            context,
            output_path=Path(clean_result.output_path),
            name=name,
            summary=(
                f"Whole-Dataset cleaned result created. Rows: {row_count_before} -> {row_count_after}. "
                "This business transformation is not holdout-safe learned model preparation."
            ),
            derivation=DatasetDerivationInput(
                operation_name="data.clean",
                inputs=[
                    DatasetDerivationSourceInput(dataset_id=dataset.id, alias="input")
                ],
                parameters_payload=input_data.model_dump(
                    mode="json",
                    exclude={"dataset_id"},
                    exclude_none=True,
                ),
            ),
            metadata_payload={"cleaning_report": clean_result.report},
        )
        payload["row_count_before"] = row_count_before
        payload["row_count_after"] = row_count_after
        payload["source_dataset_id"] = dataset.id
        payload["scope"] = "whole_dataset"
        payload["holdout_safe_model_preparation"] = False
        payload["cleaning_report"] = self._compact_cleaning_report(clean_result.report)
        return self._tabular_tool_success("data.clean", payload)

    def _data_clean_metadata(
        self,
        input_data: DataCleanMetadataInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        groups: list[str] = (
            list(input_data.groups)
            if input_data.groups is not None
            else []
        )
        payload = cleaning_operation_metadata(groups)
        return ToolSuccess(value=payload)

    def _data_tokenize(
        self,
        input_data: DataTokenizeInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        dataset = self._dataset_service.get_dataset(input_data.dataset_id)
        custom_dictionary_resources = self._staged_text_resources(
            input_data.custom_dictionary_dataset_ids,
            project_id=dataset.project_id,
        )
        stopword_resources = self._staged_text_resources(
            input_data.stopword_dataset_ids,
            project_id=dataset.project_id,
        )
        default_name = f"{dataset.name} tokenized"
        name = input_data.name or default_name
        tokenize_result = self._data_tokenization_service.tokenize_dataset(
            TokenizeDatasetInput(
                source_path=dataset.source_path,
                name=name,
                text_column=input_data.text_column,
                text_column_index=input_data.text_column_index,
                id_columns=input_data.id_columns,
                id_column_indexes=input_data.id_column_indexes,
                output=input_data.output,
                tokenizer_profile=input_data.tokenizer_profile,
                phrase_mode=input_data.phrase_mode,
                custom_dictionary_resources=custom_dictionary_resources,
                stopword_resources=stopword_resources,
            )
        )
        raw_row_count = tokenize_result.report.get("output_row_count", 0)
        row_count = (
            raw_row_count
            if isinstance(raw_row_count, int) and not isinstance(raw_row_count, bool)
            else 0
        )
        payload = self._register_generated_dataset_result(
            context,
            output_path=Path(tokenize_result.output_path),
            name=name,
            summary=f"Tokenized dataset created. Rows: {row_count}.",
            derivation=DatasetDerivationInput(
                operation_name="data.tokenize",
                inputs=[
                    DatasetDerivationSourceInput(dataset_id=dataset.id, alias="input"),
                    *[
                        DatasetDerivationSourceInput(
                            dataset_id=dataset_id,
                            alias="custom_dictionary",
                        )
                        for dataset_id in input_data.custom_dictionary_dataset_ids
                    ],
                    *[
                        DatasetDerivationSourceInput(
                            dataset_id=dataset_id,
                            alias="stopwords",
                        )
                        for dataset_id in input_data.stopword_dataset_ids
                    ],
                ],
                parameters_payload=input_data.model_dump(
                    mode="json",
                    exclude={
                        "dataset_id",
                        "custom_dictionary_dataset_ids",
                        "stopword_dataset_ids",
                    },
                    exclude_none=True,
                ),
            ),
            compatibility_parent_dataset_id=dataset.id,
            metadata_payload={"tokenization_report": tokenize_result.report},
        )
        payload["row_count"] = row_count
        payload["tokenization_report"] = tokenize_result.report
        return self._tabular_tool_success("data.tokenize", payload)

    def _data_query(
        self,
        input_data: DataQueryToolInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        bindings = self._resolve_sql_bindings(
            input_data,
        )
        query_result = self._data_transform_service.query(
            DataQueryInput(
                bindings=bindings,
                sql=input_data.sql,
                limit=input_data.limit,
                column_reference=input_data.column_reference,
            )
        )
        payload = {
            "columns": self._query_columns_payload(query_result.columns),
            "rows": self._query_rows_payload(query_result.rows, query_result.columns),
            "returned_row_count": query_result.returned_row_count,
            "total_row_count": query_result.total_row_count,
            "truncated": query_result.truncated,
        }
        return self._tabular_tool_success("data.query", payload)

    def _data_transform(
        self,
        input_data: DataTransformToolInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        bindings = self._resolve_sql_bindings(input_data)
        input_dataset_ids = [binding.dataset_id for binding in bindings]
        default_name = "Transformed dataset"
        if len(bindings) == 1:
            default_name = f"{self._dataset_service.get_dataset(bindings[0].dataset_id).name} transformed"
        name = input_data.name or default_name
        transform_result = self._data_transform_service.transform(
            DataTransformInput(
                bindings=bindings,
                sql=input_data.sql,
                name=name,
                column_reference=input_data.column_reference,
            )
        )
        payload = self._register_generated_dataset_result(
            context,
            output_path=Path(transform_result.output_path),
            name=name,
            summary=f"Transformed dataset created. Rows: {transform_result.row_count}.",
            derivation=DatasetDerivationInput(
                operation_name="data.transform",
                inputs=[
                    DatasetDerivationSourceInput(
                        dataset_id=binding.dataset_id,
                        alias=binding.alias,
                    )
                    for binding in bindings
                ],
                parameters_payload=input_data.model_dump(
                    mode="json",
                    exclude={"dataset_id", "bindings", "explanation"},
                    exclude_none=True,
                ),
                agent_explanation=input_data.explanation,
            ),
            metadata_payload={
                "transform_report": transform_result.transform_report,
                "input_dataset_ids": input_dataset_ids,
            },
        )
        payload["row_count"] = transform_result.row_count
        payload["columns"] = transform_result.columns
        payload["transform_report"] = transform_result.transform_report
        payload["input_dataset_ids"] = input_dataset_ids
        return self._tabular_tool_success("data.transform", payload)

    def _data_feature_select(
        self,
        input_data: DataFeatureSelectInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        binding = self._ml_service.create_column_binding(
            CreateColumnBindingInput(
                dataset_id=input_data.dataset_id,
                model_key=input_data.model_key,
                role_bindings=[
                    role_binding.model_dump(mode="python", exclude_none=True)
                    for role_binding in input_data.role_bindings
                ],
            )
        )
        return ToolSuccess(
            value={
                "binding_id": binding.id,
                "dataset_id": binding.dataset_id,
                "role_bindings": list(binding.role_bindings),
                "model_key": binding.model_key,
                "model_family": binding.model_family,
                "model_task_kind": binding.model_task_kind,
            },
        )

    def _staged_text_resources(
        self,
        dataset_ids: list[str],
        *,
        project_id: str,
    ) -> list[StagedTextResourceInput]:
        resources: list[StagedTextResourceInput] = []
        for dataset_id in dataset_ids:
            dataset = self._dataset_service.get_dataset(dataset_id)
            if dataset.project_id != project_id:
                raise ValidationError(
                    "Text preparation resources must belong to the input Dataset project."
                )
            source_path = Path(dataset.source_path)
            if not source_path.is_file():
                raise ValidationError("Text preparation resource source file is missing.")
            inspection = self._dataset_service.inspect_source_file(
                InspectDatasetInput(source_path=str(source_path.resolve()))
            )
            if inspection.column_count != 1 or not 1 <= inspection.row_count <= 20_000:
                raise ValidationError(
                    "Each text preparation resource must contain one term column and 1-20,000 rows."
                )
            digest = hashlib.sha256()
            with source_path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            resources.append(
                StagedTextResourceInput(
                    dataset_id=dataset.id,
                    absolute_path=str(source_path.resolve()),
                    source_sha256=digest.hexdigest(),
                )
            )
        return resources

    def _resolve_sql_bindings(
        self,
        input_data: DataQueryToolInput | DataTransformToolInput,
    ) -> list[DatasetSqlBinding]:
        if input_data.bindings is not None:
            bindings: list[DatasetSqlBinding] = []
            for input_binding in input_data.bindings:
                dataset = self._dataset_service.get_dataset(input_binding.dataset_id)
                bindings.append(
                    DatasetSqlBinding(
                        alias=input_binding.alias,
                        dataset_id=dataset.id,
                        source_path=dataset.source_path,
                    )
                )
            return bindings

        dataset_id = input_data.dataset_id
        if dataset_id is None:
            raise AssertionError("Validated SQL Tool input must own an input source.")
        dataset = self._dataset_service.get_dataset(dataset_id)
        return [
            DatasetSqlBinding(
                alias="input",
                dataset_id=dataset.id,
                source_path=dataset.source_path,
            )
        ]

    def _query_columns_payload(self, columns: list[dict[str, str]]) -> dict[str, Any]:
        rows = [
            [
                str(column.get("name") or ""),
                str(column.get("type") or ""),
                index,
            ]
            for index, column in enumerate(columns)
        ]
        return self._compact_table(["name", "type", "index"], rows)

    def _query_rows_payload(
        self,
        rows: list[dict[str, Any]],
        columns: list[dict[str, str]],
    ) -> dict[str, Any]:
        column_names = [str(column.get("name") or "") for column in columns]
        data = [[row.get(column_name) for column_name in column_names] for row in rows]
        return {
            "_schema": {column_name: index for index, column_name in enumerate(column_names)},
            "data": data,
        }

    def _compact_cleaning_report(self, report: dict[str, Any]) -> dict[str, Any]:
        """Project full execution audit into the bounded next-call facts.

        The complete report is retained in the generated artifact metadata.  A
        provider only needs the operation sequence, aggregate effects, small
        field samples and warnings needed to decide its next Tool call.
        """

        compact: dict[str, Any] = {}
        for key in ("row_count_before", "row_count_after", "rows_removed", "no_op"):
            value = report.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                compact[key] = value

        operations = report.get("operations")
        if isinstance(operations, list):
            compact["operation_count"] = len(operations)
            compact["operations"] = [
                self._compact_cleaning_report_operation(item)
                for item in operations[:MAX_CLEANING_REPORT_OPERATION_ENTRIES]
                if isinstance(item, dict)
            ]
            omitted = len(operations) - len(compact["operations"])
            if omitted:
                compact["omitted_operation_entries"] = omitted

        validation_rules = report.get("validation_rules")
        if isinstance(validation_rules, list):
            compact["validation_rule_count"] = len(validation_rules)
            compact["validation_rules"] = [
                self._compact_cleaning_validation_rule(item)
                for item in validation_rules[:MAX_CLEANING_REPORT_VALIDATION_ENTRIES]
                if isinstance(item, dict)
            ]
            omitted = len(validation_rules) - len(compact["validation_rules"])
            if omitted:
                compact["omitted_validation_rules"] = omitted

        warnings = report.get("warnings")
        if isinstance(warnings, list):
            normalized_warnings = [
                self._bounded_cleaning_text(item, MAX_CLEANING_REPORT_WARNING_CHARS)
                for item in warnings
                if str(item).strip()
            ]
            compact["warning_count"] = len(normalized_warnings)
            if normalized_warnings:
                compact["warnings"] = normalized_warnings[:MAX_CLEANING_REPORT_WARNING_ENTRIES]
                omitted = len(normalized_warnings) - len(compact["warnings"])
                if omitted:
                    compact["omitted_warnings"] = omitted
        return compact

    def _compact_cleaning_report_operation(self, operation: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        name = operation.get("operation")
        if isinstance(name, str) and name:
            compact["operation"] = name
        for key in (
            "column",
            "rows_removed",
            "cells_filled",
            "cells_changed",
            "coerced_to_null",
            "columns_changed",
            "columns_removed",
            "threshold",
            "multiplier",
            "target_type",
            "style",
            "ascii_lower",
            "drop_first",
            "max_categories",
        ):
            value = operation.get(key)
            if isinstance(value, (str, int, float, bool)):
                if key == "column":
                    compact[key] = self._bounded_cleaning_text(
                        value,
                        MAX_CLEANING_REPORT_COLUMN_NAME_CHARS,
                    )
                else:
                    compact[key] = value
        if "resolved_fill_value" in operation:
            compact["resolved_fill_value"] = self._compact_cleaning_scalar(
                operation.get("resolved_fill_value")
            )
        feature_range = operation.get("feature_range")
        if (
            isinstance(feature_range, list)
            and len(feature_range) == 2
            and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in feature_range)
        ):
            compact["feature_range"] = list(feature_range)
        self._compact_cleaning_report_columns(compact, "columns", operation.get("columns"))
        self._compact_cleaning_report_columns(compact, "dropped_columns", operation.get("dropped_columns"))
        self._compact_cleaning_report_columns(compact, "evaluated_columns", operation.get("evaluated_columns"))
        self._compact_cleaning_report_columns(
            compact,
            "encoded_columns",
            operation.get("encoded_columns"),
            include_empty=True,
        )
        skipped_columns = operation.get("skipped_columns")
        if isinstance(skipped_columns, list):
            self._compact_cleaning_report_columns(
                compact,
                "skipped_columns",
                [
                    item.get("column")
                    for item in skipped_columns
                    if isinstance(item, dict) and item.get("column") is not None
                ],
            )
        columns_summary = operation.get("columns_summary")
        if isinstance(columns_summary, list):
            generated_columns: list[Any] = []
            for summary in columns_summary:
                if isinstance(summary, dict) and isinstance(summary.get("generated_columns"), list):
                    generated_columns.extend(summary["generated_columns"])
            self._compact_cleaning_report_columns(compact, "generated_columns", generated_columns)
        for source_key, count_key in (
            ("mapping", "renamed_column_count"),
            ("generated_empty_names", "generated_column_name_count"),
            ("duplicate_collisions", "duplicate_column_name_count"),
            ("columns_summary", "column_summary_count"),
            ("category_columns", "generated_category_column_count"),
        ):
            value = operation.get(source_key)
            if isinstance(value, (list, dict)):
                compact[count_key] = len(value)
        return compact

    @staticmethod
    def _compact_cleaning_scalar(value: Any) -> str | int | float | bool | None:
        if value is None or isinstance(value, int | float | bool):
            return value
        return DataTools._bounded_cleaning_text(
            value,
            MAX_CLEANING_REPORT_FILL_VALUE_CHARS,
        )

    def _compact_cleaning_validation_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        for key in ("name", "column", "operation", "action", "violations", "rows_removed"):
            value = rule.get(key)
            if isinstance(value, (str, int, float, bool)):
                if key in {"name", "column"}:
                    compact[key] = self._bounded_cleaning_text(
                        value,
                        MAX_CLEANING_REPORT_COLUMN_NAME_CHARS,
                    )
                else:
                    compact[key] = value
        return compact

    @staticmethod
    def _compact_cleaning_report_columns(
        compact: dict[str, Any],
        key: str,
        value: Any,
        *,
        include_empty: bool = False,
    ) -> None:
        if not isinstance(value, list):
            return
        values = [str(item) for item in value if str(item).strip()]
        if not values:
            if include_empty:
                compact[key] = []
                compact[f"{key}_count"] = 0
            return
        compact[key] = [
            DataTools._bounded_cleaning_text(item, MAX_CLEANING_REPORT_COLUMN_NAME_CHARS)
            for item in values[:MAX_CLEANING_REPORT_COLUMN_NAMES]
        ]
        compact[f"{key}_count"] = len(values)
        omitted = len(values) - len(compact[key])
        if omitted:
            compact[f"omitted_{key}"] = omitted

    @staticmethod
    def _bounded_cleaning_text(value: Any, limit: int) -> str:
        text = str(value)
        if len(text) <= limit:
            return text
        if limit <= 1:
            return text[:limit]
        return text[: limit - 1] + "…"

    def _tabular_tool_success(self, tool_name: str, payload: dict[str, Any]) -> ToolSuccess:
        """Return the one canonical value for a tabular Tool.

        The formatter runs while the concrete Tool still owns the raw
        intermediate payload.  Once this method returns, only the XTT text
        (when the payload has a tabular contract) crosses the LLM boundary;
        there is no later raw-payload-to-XTT projection.
        """

        rendered = render_xenix_table_tool_result(
            tool_name=tool_name,
            status="succeeded",
            payload=payload,
        )
        return ToolSuccess(value=rendered if rendered is not None else payload)

    def _register_generated_dataset_result(
        self,
        context: ToolExecutionContext,
        *,
        output_path: Path,
        name: str,
        summary: str,
        derivation: DatasetDerivationInput,
        compatibility_parent_dataset_id: str | None = None,
        metadata_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_output_path = output_path.resolve()
        payload = self._preprocessing_worker_runner.run(
            "data.register_generated_dataset",
            {
                "output_path": str(resolved_output_path),
                "name": name,
                "summary": summary,
                "derivation": derivation.model_copy(
                    update={"tool_call_message_id": context.tool_call_message_id}
                ).model_dump(mode="json"),
                "derived_from_dataset_id": compatibility_parent_dataset_id,
                "metadata_payload": dict(metadata_payload or {}),
            },
            paths=self._paths,
        )
        return payload

    def _compact_table(self, keys: list[str], rows: list[list[Any]]) -> dict[str, Any]:
        return {
            "_schema": {key: index for index, key in enumerate(keys)},
            "data": rows,
        }

    def _load_frame(self, path: Path) -> pd.DataFrame:
        source_format = detect_source_format(path)
        if source_format.value == "unknown":
            raise ValidationError("Only .csv, .parquet, .xlsx, and .xls dataset files are supported.")
        return load_dataframe(path, source_format)

