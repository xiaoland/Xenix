from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from pandas.api.types import is_numeric_dtype
from pydantic import ConfigDict, Field
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import ValidationError
from .dataset_inspection import detect_source_format, load_dataframe
from .storage.models import DatasetSourceFormat


KEEP_SCHEMA = {"type": "string", "enum": ["first", "last", "false"]}
COLUMNS_SCHEMA = {"type": "array", "items": {"type": "string"}}
ACTION_SCHEMA = {"type": "string", "enum": ["report_only", "drop_rows"]}


_CLEANING_OPERATION_GROUPS: dict[str, dict[str, Any]] = {
    "duplicates": {
        "description": "Remove duplicate rows.",
        "operations": [
            {
                "operation": "duplicate.exact_rows",
                "description": "Remove rows that are exact duplicates across all columns.",
                "params_schema": {
                    "type": "object",
                    "properties": {"keep": KEEP_SCHEMA},
                    "additionalProperties": False,
                },
                "example": {"operation": "duplicate.exact_rows", "params": {"keep": "first"}},
            },
            {
                "operation": "duplicate.key_columns",
                "description": "Remove duplicate rows based on selected key columns.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA, "keep": KEEP_SCHEMA},
                    "required": ["columns"],
                    "additionalProperties": False,
                },
                "example": {
                    "operation": "duplicate.key_columns",
                    "params": {"columns": ["customer_id"], "keep": "first"},
                },
            },
        ],
    },
    "missing": {
        "description": "Fill missing values or drop rows with missing values.",
        "operations": [
            {
                "operation": "missing.fill_mean",
                "description": "Fill missing numeric values with each column mean.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA},
                    "required": ["columns"],
                    "additionalProperties": False,
                },
                "example": {"operation": "missing.fill_mean", "params": {"columns": ["amount"]}},
            },
            {
                "operation": "missing.fill_median",
                "description": "Fill missing numeric values with each column median.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA},
                    "required": ["columns"],
                    "additionalProperties": False,
                },
                "example": {"operation": "missing.fill_median", "params": {"columns": ["amount"]}},
            },
            {
                "operation": "missing.fill_mode",
                "description": "Fill missing values with each column mode.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA},
                    "required": ["columns"],
                    "additionalProperties": False,
                },
                "example": {"operation": "missing.fill_mode", "params": {"columns": ["segment"]}},
            },
            {
                "operation": "missing.fill_constant",
                "description": "Fill missing values with a constant value.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA, "value": {}},
                    "required": ["columns", "value"],
                    "additionalProperties": False,
                },
                "example": {"operation": "missing.fill_constant", "params": {"columns": ["amount"], "value": 0}},
            },
            {
                "operation": "missing.forward_fill",
                "description": "Fill missing values from the previous non-empty row value.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA},
                    "required": ["columns"],
                    "additionalProperties": False,
                },
                "example": {"operation": "missing.forward_fill", "params": {"columns": ["segment"]}},
            },
            {
                "operation": "missing.drop_rows",
                "description": "Drop rows where any selected column is missing.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA},
                    "required": ["columns"],
                    "additionalProperties": False,
                },
                "example": {"operation": "missing.drop_rows", "params": {"columns": ["amount"]}},
            },
        ],
    },
    "types": {
        "description": "Convert column types.",
        "operations": [
            {
                "operation": "type.convert",
                "description": "Convert one column to a target type.",
                "params_schema": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "target_type": {
                            "type": "string",
                            "enum": ["numeric", "integer", "datetime", "text", "boolean"],
                        },
                        "date_format": {"type": "string"},
                    },
                    "required": ["column", "target_type"],
                    "additionalProperties": False,
                },
                "example": {
                    "operation": "type.convert",
                    "params": {"column": "amount", "target_type": "numeric"},
                },
            },
        ],
    },
    "text": {
        "description": "Standardize text column values.",
        "operations": [
            {
                "operation": "text.trim",
                "description": "Strip leading and trailing whitespace.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA},
                    "required": ["columns"],
                    "additionalProperties": False,
                },
                "example": {"operation": "text.trim", "params": {"columns": ["region"]}},
            },
            {
                "operation": "text.lowercase",
                "description": "Convert text to lowercase.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA},
                    "required": ["columns"],
                    "additionalProperties": False,
                },
                "example": {"operation": "text.lowercase", "params": {"columns": ["region"]}},
            },
            {
                "operation": "text.uppercase",
                "description": "Convert text to uppercase.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA},
                    "required": ["columns"],
                    "additionalProperties": False,
                },
                "example": {"operation": "text.uppercase", "params": {"columns": ["region"]}},
            },
            {
                "operation": "text.collapse_whitespace",
                "description": "Collapse repeated whitespace into one space.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA},
                    "required": ["columns"],
                    "additionalProperties": False,
                },
                "example": {"operation": "text.collapse_whitespace", "params": {"columns": ["region"]}},
            },
            {
                "operation": "text.empty_to_null",
                "description": "Convert empty text values to null.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA},
                    "required": ["columns"],
                    "additionalProperties": False,
                },
                "example": {"operation": "text.empty_to_null", "params": {"columns": ["region"]}},
            },
            {
                "operation": "text.map_values",
                "description": "Replace text values through an exact value map.",
                "params_schema": {
                    "type": "object",
                    "properties": {"columns": COLUMNS_SCHEMA, "value_map": {"type": "object"}},
                    "required": ["columns", "value_map"],
                    "additionalProperties": False,
                },
                "example": {
                    "operation": "text.map_values",
                    "params": {"columns": ["region"], "value_map": {"n": "north"}},
                },
            },
        ],
    },
    "validation": {
        "description": "Report invalid values or drop rows that violate a rule.",
        "operations": [
            {
                "operation": "validation.not_null",
                "description": "Find rows where a column is null.",
                "params_schema": {
                    "type": "object",
                    "properties": {"column": {"type": "string"}, "action": ACTION_SCHEMA, "name": {"type": "string"}},
                    "required": ["column"],
                    "additionalProperties": False,
                },
                "example": {"operation": "validation.not_null", "params": {"column": "amount"}},
            },
            {
                "operation": "validation.non_negative",
                "description": "Find rows where a numeric column is below zero.",
                "params_schema": {
                    "type": "object",
                    "properties": {"column": {"type": "string"}, "action": ACTION_SCHEMA, "name": {"type": "string"}},
                    "required": ["column"],
                    "additionalProperties": False,
                },
                "example": {
                    "operation": "validation.non_negative",
                    "params": {"column": "amount", "action": "drop_rows"},
                },
            },
            {
                "operation": "validation.min",
                "description": "Find rows where a numeric column is below a minimum value.",
                "params_schema": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "value": {},
                        "action": ACTION_SCHEMA,
                        "name": {"type": "string"},
                    },
                    "required": ["column", "value"],
                    "additionalProperties": False,
                },
                "example": {"operation": "validation.min", "params": {"column": "amount", "value": 0}},
            },
            {
                "operation": "validation.max",
                "description": "Find rows where a numeric column is above a maximum value.",
                "params_schema": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "value": {},
                        "action": ACTION_SCHEMA,
                        "name": {"type": "string"},
                    },
                    "required": ["column", "value"],
                    "additionalProperties": False,
                },
                "example": {"operation": "validation.max", "params": {"column": "amount", "value": 1000}},
            },
            {
                "operation": "validation.allowed_values",
                "description": "Find rows where a value is outside an allowed set.",
                "params_schema": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "values": {"type": "array"},
                        "action": ACTION_SCHEMA,
                        "name": {"type": "string"},
                    },
                    "required": ["column", "values"],
                    "additionalProperties": False,
                },
                "example": {
                    "operation": "validation.allowed_values",
                    "params": {"column": "status", "values": ["open", "closed"]},
                },
            },
            {
                "operation": "validation.regex",
                "description": "Find rows where text does not match a regular expression.",
                "params_schema": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "value": {},
                        "action": ACTION_SCHEMA,
                        "name": {"type": "string"},
                    },
                    "required": ["column", "value"],
                    "additionalProperties": False,
                },
                "example": {
                    "operation": "validation.regex",
                    "params": {"column": "email", "value": r"^[^@]+@[^@]+$"},
                },
            },
        ],
    },
}


def cleaning_operation_metadata(groups: list[str] | None = None) -> dict[str, Any]:
    selected_groups = _normalize_groups(groups)
    group_payloads = [copy.deepcopy({"group": group, **_CLEANING_OPERATION_GROUPS[group]}) for group in selected_groups]
    return {
        "groups": group_payloads,
        "group_names": list(_CLEANING_OPERATION_GROUPS),
        "operation_count": sum(len(group["operations"]) for group in group_payloads),
    }


def _normalize_groups(groups: list[str] | None) -> list[str]:
    if not groups:
        return list(_CLEANING_OPERATION_GROUPS)
    normalized: list[str] = []
    for group in groups:
        value = str(group or "").strip()
        if not value or value in normalized:
            continue
        if value not in _CLEANING_OPERATION_GROUPS:
            raise ValidationError(
                "Unknown data.clean.metadata group "
                f"'{value}'. Available groups: {', '.join(_CLEANING_OPERATION_GROUPS)}."
            )
        normalized.append(value)
    return normalized or list(_CLEANING_OPERATION_GROUPS)


class CleanOperation(SQLModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    params: dict[str, Any] = Field(default_factory=dict)


class CleanDatasetInput(SQLModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    name: str
    operations: list[CleanOperation] = Field(default_factory=list)


class CleanDatasetResult(SQLModel):
    output_path: str
    report: dict[str, Any] = Field(default_factory=dict)


class DataCleaningService:
    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths

    def clean_dataset(self, input_data: CleanDatasetInput) -> CleanDatasetResult:
        source_path = Path(input_data.source_path).expanduser()
        if not source_path.is_absolute():
            raise ValidationError("Dataset source path must be absolute.")
        if not source_path.exists() or not source_path.is_file():
            raise ValidationError("Dataset source path must point to an existing file.")

        source_format = detect_source_format(source_path)
        if source_format is DatasetSourceFormat.UNKNOWN:
            raise ValidationError("Only .csv, .xlsx, and .xls dataset files are supported.")

        frame = load_dataframe(source_path, source_format)
        if len(frame.columns) == 0:
            raise ValidationError("Dataset file must contain at least one column.")

        report: dict[str, Any] = {
            "row_count_before": int(len(frame.index)),
            "row_count_after": int(len(frame.index)),
            "operations": [],
            "validation_rules": [],
            "warnings": [],
        }

        if not input_data.operations:
            report["rows_removed"] = 0
            report["no_op"] = True
            return CleanDatasetResult(output_path=str(source_path.resolve()), report=report)

        for operation in input_data.operations:
            frame = self._apply_operation(frame, operation, report)

        output_dir = self._paths.artifacts / "datasets" / "cleaned"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{self._slug(input_data.name)}-{uuid4().hex[:12]}.csv"
        frame.to_csv(output_path, index=False)

        report["row_count_after"] = int(len(frame.index))
        report["rows_removed"] = int(report["row_count_before"] - report["row_count_after"])
        report["no_op"] = False
        return CleanDatasetResult(output_path=str(output_path.resolve()), report=report)

    def _apply_operation(
        self,
        frame: pd.DataFrame,
        operation: CleanOperation,
        report: dict[str, Any],
    ) -> pd.DataFrame:
        operation_name = str(operation.operation or "").strip()
        params = dict(operation.params or {})
        if not operation_name:
            raise ValidationError("cleaning operation cannot be empty.")

        if operation_name == "duplicate.exact_rows":
            return self._apply_duplicate_exact_rows(frame, operation_name, params, report)
        if operation_name == "duplicate.key_columns":
            return self._apply_duplicate_key_columns(frame, operation_name, params, report)
        if operation_name.startswith("missing."):
            return self._apply_missing_operation(frame, operation_name, params, report)
        if operation_name == "type.convert":
            return self._apply_type_convert(frame, operation_name, params, report)
        if operation_name.startswith("text."):
            return self._apply_text_operation(frame, operation_name, params, report)
        if operation_name.startswith("validation."):
            return self._apply_validation_operation(frame, operation_name, params, report)
        raise ValidationError(f"Unsupported cleaning operation '{operation_name}'.")

    def _apply_duplicate_exact_rows(
        self,
        frame: pd.DataFrame,
        operation_name: str,
        params: dict[str, Any],
        report: dict[str, Any],
    ) -> pd.DataFrame:
        keep = self._keep_value(params, operation_name)
        before = int(len(frame.index))
        cleaned = frame.drop_duplicates(keep=keep)
        report["operations"].append(
            {
                "operation": operation_name,
                "rows_removed": before - int(len(cleaned.index)),
            }
        )
        return cleaned

    def _apply_duplicate_key_columns(
        self,
        frame: pd.DataFrame,
        operation_name: str,
        params: dict[str, Any],
        report: dict[str, Any],
    ) -> pd.DataFrame:
        columns = self._params_columns(frame, params, operation_name)
        keep = self._keep_value(params, operation_name)
        before = int(len(frame.index))
        cleaned = frame.drop_duplicates(subset=columns, keep=keep)
        report["operations"].append(
            {
                "operation": operation_name,
                "columns": columns,
                "rows_removed": before - int(len(cleaned.index)),
            }
        )
        return cleaned

    def _apply_missing_operation(
        self,
        frame: pd.DataFrame,
        operation_name: str,
        params: dict[str, Any],
        report: dict[str, Any],
    ) -> pd.DataFrame:
        strategy_by_operation = {
            "missing.fill_mean": "mean",
            "missing.fill_median": "median",
            "missing.fill_mode": "mode",
            "missing.fill_constant": "constant",
            "missing.forward_fill": "forward_fill",
            "missing.drop_rows": "drop_rows",
        }
        strategy = strategy_by_operation.get(operation_name)
        if strategy is None:
            raise ValidationError(f"Unsupported cleaning operation '{operation_name}'.")
        columns = self._params_columns(frame, params, operation_name)
        if strategy == "drop_rows":
            before = int(len(frame.index))
            mask = frame[columns].isna().any(axis=1)
            cleaned = frame.loc[~mask].copy()
            report["operations"].append(
                {
                    "operation": operation_name,
                    "columns": columns,
                    "rows_removed": before - int(len(cleaned.index)),
                }
            )
            return cleaned

        if strategy == "constant" and "value" not in params:
            raise ValidationError(f"{operation_name}.params.value is required.")
        for column in columns:
            missing_before = int(frame[column].isna().sum())
            if missing_before == 0:
                continue
            if strategy == "forward_fill":
                frame[column] = frame[column].ffill()
            else:
                fill_value = self._resolve_fill_value(frame[column], strategy, column, params.get("value"), report)
                frame[column] = frame[column].fillna(fill_value)
            report["operations"].append(
                {
                    "operation": operation_name,
                    "column": column,
                    "cells_filled": missing_before - int(frame[column].isna().sum()),
                }
            )
        return frame

    def _resolve_fill_value(
        self,
        series: pd.Series,
        strategy: str,
        column: str,
        value: Any,
        report: dict[str, Any],
    ) -> Any:
        if strategy == "constant":
            return "" if value is None else value
        if strategy in {"mean", "median"} and not is_numeric_dtype(series):
            raise ValidationError(f"Column '{column}' must be numeric for {strategy} fill.")
        if strategy == "mean":
            fill_value = series.mean()
        elif strategy == "median":
            fill_value = series.median()
        elif strategy == "mode":
            mode = series.dropna().mode()
            fill_value = "" if mode.empty else mode.iloc[0]
        else:
            raise ValidationError(f"Unsupported missing strategy '{strategy}'.")
        if pd.isna(fill_value):
            report["warnings"].append(
                f"Column '{column}' has no non-empty values for {strategy} fill; missing values were left empty."
            )
            return ""
        return fill_value

    def _apply_type_convert(
        self,
        frame: pd.DataFrame,
        operation_name: str,
        params: dict[str, Any],
        report: dict[str, Any],
    ) -> pd.DataFrame:
        column = self._params_column(frame, params, operation_name)
        target_type = self._one_of(
            str(params.get("target_type") or ""),
            {"numeric", "integer", "datetime", "text", "boolean"},
            f"{operation_name}.params.target_type",
        )
        before_notna = frame[column].notna()
        if target_type == "numeric":
            converted = pd.to_numeric(frame[column], errors="coerce")
        elif target_type == "integer":
            converted = pd.to_numeric(frame[column], errors="coerce").round().astype("Int64")
        elif target_type == "datetime":
            date_format = str(params.get("date_format") or "").strip() or None
            converted = pd.to_datetime(frame[column], errors="coerce", format=date_format)
        elif target_type == "text":
            converted = frame[column].astype("string")
        else:
            converted = self._to_boolean(frame[column])
        coerced_to_null = int((before_notna & converted.isna()).sum())
        frame[column] = converted
        report["operations"].append(
            {
                "operation": operation_name,
                "column": column,
                "target_type": target_type,
                "coerced_to_null": coerced_to_null,
            }
        )
        return frame

    def _apply_text_operation(
        self,
        frame: pd.DataFrame,
        operation_name: str,
        params: dict[str, Any],
        report: dict[str, Any],
    ) -> pd.DataFrame:
        columns = self._params_columns(frame, params, operation_name)
        value_map = params.get("value_map")
        if operation_name == "text.map_values" and not isinstance(value_map, dict):
            raise ValidationError(f"{operation_name}.params.value_map must be an object.")

        for column in columns:
            original = frame[column].copy()
            values = frame[column].astype("string")
            if operation_name == "text.trim":
                values = values.str.strip()
            elif operation_name == "text.lowercase":
                values = values.str.lower()
            elif operation_name == "text.uppercase":
                values = values.str.upper()
            elif operation_name == "text.collapse_whitespace":
                values = values.str.replace(r"\s+", " ", regex=True)
            elif operation_name == "text.empty_to_null":
                values = values.replace(r"^\s*$", pd.NA, regex=True)
            elif operation_name == "text.map_values":
                values = values.replace(value_map)
            else:
                raise ValidationError(f"Unsupported cleaning operation '{operation_name}'.")
            frame[column] = values
            changed = int((original.astype("string") != frame[column].astype("string")).fillna(False).sum())
            report["operations"].append(
                {
                    "operation": operation_name,
                    "column": column,
                    "cells_changed": changed,
                }
            )
        return frame

    def _apply_validation_operation(
        self,
        frame: pd.DataFrame,
        operation_name: str,
        params: dict[str, Any],
        report: dict[str, Any],
    ) -> pd.DataFrame:
        column = self._params_column(frame, params, operation_name)
        action = self._one_of(
            str(params.get("action") or "report_only"),
            {"report_only", "drop_rows"},
            f"{operation_name}.params.action",
        )
        mask = self._validation_mask(frame[column], operation_name, params)
        violations = int(mask.sum())
        entry = {
            "name": str(params.get("name") or operation_name).strip() or operation_name,
            "column": column,
            "operation": operation_name,
            "action": action,
            "violations": violations,
        }
        if action == "drop_rows" and violations:
            frame = frame.loc[~mask].copy()
            entry["rows_removed"] = violations
        report["validation_rules"].append(entry)
        return frame

    def _validation_mask(self, series: pd.Series, operation_name: str, params: dict[str, Any]) -> pd.Series:
        if operation_name == "validation.not_null":
            return series.isna()
        if operation_name == "validation.non_negative":
            return pd.to_numeric(series, errors="coerce") < 0
        if operation_name == "validation.min":
            return pd.to_numeric(series, errors="coerce") < self._float_param(params, operation_name)
        if operation_name == "validation.max":
            return pd.to_numeric(series, errors="coerce") > self._float_param(params, operation_name)
        if operation_name == "validation.allowed_values":
            values = params.get("values")
            if not isinstance(values, list):
                raise ValidationError(f"{operation_name}.params.values must be a list.")
            return ~series.isin(values)
        if operation_name == "validation.regex":
            if "value" not in params:
                raise ValidationError(f"{operation_name}.params.value is required.")
            pattern = re.compile(str(params.get("value") or ""))
            return ~series.astype("string").fillna("").str.match(pattern)
        raise ValidationError(f"Unsupported cleaning operation '{operation_name}'.")

    def _float_param(self, params: dict[str, Any], operation_name: str) -> float:
        if "value" not in params:
            raise ValidationError(f"{operation_name}.params.value is required.")
        try:
            return float(params.get("value"))
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{operation_name}.params.value must be numeric.") from exc

    def _keep_value(self, params: dict[str, Any], operation_name: str) -> str | bool:
        keep = self._one_of(str(params.get("keep") or "first"), {"first", "last", "false"}, f"{operation_name}.params.keep")
        return False if keep == "false" else keep

    def _params_columns(self, frame: pd.DataFrame, params: dict[str, Any], operation_name: str) -> list[str]:
        columns = params.get("columns")
        if not isinstance(columns, list):
            raise ValidationError(f"{operation_name}.params.columns must be a list.")
        return self._require_columns(frame, columns, f"{operation_name}.params.columns")

    def _params_column(self, frame: pd.DataFrame, params: dict[str, Any], operation_name: str) -> str:
        return self._require_column(frame, str(params.get("column") or ""), f"{operation_name}.params.column")

    def _to_boolean(self, series: pd.Series) -> pd.Series:
        true_values = {"true", "t", "yes", "y", "1"}
        false_values = {"false", "f", "no", "n", "0"}

        def convert(value: Any) -> bool | None:
            if pd.isna(value):
                return None
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().lower()
            if normalized in true_values:
                return True
            if normalized in false_values:
                return False
            return None

        return series.map(convert).astype("boolean")

    def _require_columns(self, frame: pd.DataFrame, columns: list[str], field_name: str) -> list[str]:
        normalized = [self._require_column(frame, column, field_name) for column in columns if str(column).strip()]
        if not normalized:
            raise ValidationError(f"{field_name} cannot be empty.")
        return normalized

    def _require_column(self, frame: pd.DataFrame, column: str, field_name: str) -> str:
        normalized = str(column or "").strip()
        if not normalized:
            raise ValidationError(f"{field_name} cannot be empty.")
        if normalized not in frame.columns:
            raise ValidationError(f"Column '{normalized}' does not exist.")
        return normalized

    def _one_of(self, value: str, allowed: set[str], field_name: str) -> str:
        normalized = str(value or "").strip()
        if normalized not in allowed:
            raise ValidationError(f"{field_name} must be one of: {', '.join(sorted(allowed))}.")
        return normalized

    def _slug(self, value: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
        return normalized or "dataset"
