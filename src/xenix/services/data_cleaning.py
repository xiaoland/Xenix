from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from pandas.api.types import is_numeric_dtype
from pydantic import Field
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import ValidationError
from .dataset_inspection import detect_source_format, load_dataframe
from .storage.models import DatasetSourceFormat


class DuplicatePolicy(SQLModel):
    mode: str = "exact_rows"
    columns: list[str] = Field(default_factory=list)
    keep: str = "first"


class MissingRule(SQLModel):
    columns: list[str] = Field(default_factory=list)
    strategy: str
    value: Any = None


class MissingPolicy(SQLModel):
    default_numeric: str = "median"
    default_text: str = "mode"
    fill_values: dict[str, Any] = Field(default_factory=dict)
    rules: list[MissingRule] = Field(default_factory=list)


class TypeCorrection(SQLModel):
    column: str
    target_type: str
    date_format: str | None = None


class TextStandardization(SQLModel):
    columns: list[str] = Field(default_factory=list)
    trim: bool = True
    lowercase: bool = False
    uppercase: bool = False
    collapse_whitespace: bool = False
    empty_to_null: bool = False
    value_map: dict[str, Any] = Field(default_factory=dict)


class ValidationRule(SQLModel):
    name: str | None = None
    column: str
    rule: str
    action: str = "report_only"
    value: Any = None
    values: list[Any] = Field(default_factory=list)


class CleanDatasetInput(SQLModel):
    source_path: str
    name: str
    drop_duplicates: bool | None = None
    duplicate_policy: DuplicatePolicy | None = None
    missing_policy: MissingPolicy | None = None
    type_corrections: list[TypeCorrection] = Field(default_factory=list)
    text_standardization: list[TextStandardization] = Field(default_factory=list)
    validation_rules: list[ValidationRule] = Field(default_factory=list)


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

        frame = self._apply_text_standardization(frame, input_data.text_standardization, report)
        frame = self._apply_type_corrections(frame, input_data.type_corrections, report)
        frame = self._apply_duplicate_policy(
            frame,
            input_data.duplicate_policy,
            drop_duplicates=input_data.drop_duplicates,
            report=report,
        )
        frame = self._apply_missing_policy(frame, input_data.missing_policy, report)
        frame = self._apply_validation_rules(frame, input_data.validation_rules, report)

        output_dir = self._paths.artifacts / "datasets" / "cleaned"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{self._slug(input_data.name)}-{uuid4().hex[:12]}.csv"
        frame.to_csv(output_path, index=False)

        report["row_count_after"] = int(len(frame.index))
        report["rows_removed"] = int(report["row_count_before"] - report["row_count_after"])
        return CleanDatasetResult(output_path=str(output_path.resolve()), report=report)

    def _apply_duplicate_policy(
        self,
        frame: pd.DataFrame,
        policy: DuplicatePolicy | None,
        *,
        drop_duplicates: bool | None,
        report: dict[str, Any],
    ) -> pd.DataFrame:
        if policy is None:
            policy = DuplicatePolicy(mode="exact_rows" if drop_duplicates is not False else "none")
        mode = self._one_of(policy.mode, {"none", "exact_rows", "key_columns"}, "duplicate_policy.mode")
        if mode == "none":
            return frame
        keep = self._one_of(policy.keep, {"first", "last", "false"}, "duplicate_policy.keep")
        keep_arg: str | bool = False if keep == "false" else keep
        before = int(len(frame.index))
        if mode == "exact_rows":
            cleaned = frame.drop_duplicates(keep=keep_arg)
            report["operations"].append(
                {
                    "operation": "duplicates",
                    "mode": mode,
                    "rows_removed": before - int(len(cleaned.index)),
                }
            )
            return cleaned

        columns = self._require_columns(frame, policy.columns, "duplicate_policy.columns")
        cleaned = frame.drop_duplicates(subset=columns, keep=keep_arg)
        report["operations"].append(
            {
                "operation": "duplicates",
                "mode": mode,
                "columns": columns,
                "rows_removed": before - int(len(cleaned.index)),
            }
        )
        return cleaned

    def _apply_missing_policy(
        self,
        frame: pd.DataFrame,
        policy: MissingPolicy | None,
        report: dict[str, Any],
    ) -> pd.DataFrame:
        policy = policy or MissingPolicy()
        handled_columns: set[str] = set()
        for rule in policy.rules:
            columns = self._require_columns(frame, rule.columns, "missing_policy.rules.columns")
            frame = self._apply_missing_strategy(
                frame,
                columns,
                rule.strategy,
                report,
                value=rule.value,
                fill_values=policy.fill_values,
            )
            handled_columns.update(columns)

        for column in frame.columns:
            if column in handled_columns or not frame[column].isna().any():
                continue
            strategy = policy.default_numeric if is_numeric_dtype(frame[column]) else policy.default_text
            frame = self._apply_missing_strategy(
                frame,
                [str(column)],
                strategy,
                report,
                value=None,
                fill_values=policy.fill_values,
            )
        return frame

    def _apply_missing_strategy(
        self,
        frame: pd.DataFrame,
        columns: list[str],
        strategy: str,
        report: dict[str, Any],
        *,
        value: Any,
        fill_values: dict[str, Any],
    ) -> pd.DataFrame:
        strategy = self._one_of(
            strategy,
            {"none", "mean", "median", "mode", "constant", "forward_fill", "drop_rows"},
            "missing_policy.strategy",
        )
        if strategy == "none":
            return frame
        if strategy == "drop_rows":
            before = int(len(frame.index))
            mask = frame[columns].isna().any(axis=1)
            cleaned = frame.loc[~mask].copy()
            report["operations"].append(
                {
                    "operation": "missing_values",
                    "strategy": strategy,
                    "columns": columns,
                    "rows_removed": before - int(len(cleaned.index)),
                }
            )
            return cleaned

        for column in columns:
            missing_before = int(frame[column].isna().sum())
            if missing_before == 0:
                continue
            if strategy == "forward_fill":
                frame[column] = frame[column].ffill()
            else:
                fill_value = self._resolve_fill_value(frame[column], strategy, column, value, fill_values, report)
                frame[column] = frame[column].fillna(fill_value)
            report["operations"].append(
                {
                    "operation": "missing_values",
                    "strategy": strategy,
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
        fill_values: dict[str, Any],
        report: dict[str, Any],
    ) -> Any:
        if strategy == "constant":
            return fill_values.get(column, "" if value is None else value)
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

    def _apply_type_corrections(
        self,
        frame: pd.DataFrame,
        corrections: list[TypeCorrection],
        report: dict[str, Any],
    ) -> pd.DataFrame:
        for correction in corrections:
            column = self._require_column(frame, correction.column, "type_corrections.column")
            target_type = self._one_of(
                correction.target_type,
                {"numeric", "integer", "datetime", "text", "boolean"},
                "type_corrections.target_type",
            )
            before_notna = frame[column].notna()
            if target_type == "numeric":
                converted = pd.to_numeric(frame[column], errors="coerce")
            elif target_type == "integer":
                converted = pd.to_numeric(frame[column], errors="coerce").round().astype("Int64")
            elif target_type == "datetime":
                converted = pd.to_datetime(frame[column], errors="coerce", format=correction.date_format)
            elif target_type == "text":
                converted = frame[column].astype("string")
            else:
                converted = self._to_boolean(frame[column])
            coerced_to_null = int((before_notna & converted.isna()).sum())
            frame[column] = converted
            report["operations"].append(
                {
                    "operation": "type_correction",
                    "column": column,
                    "target_type": target_type,
                    "coerced_to_null": coerced_to_null,
                }
            )
        return frame

    def _apply_text_standardization(
        self,
        frame: pd.DataFrame,
        rules: list[TextStandardization],
        report: dict[str, Any],
    ) -> pd.DataFrame:
        for rule in rules:
            if rule.lowercase and rule.uppercase:
                raise ValidationError("Text standardization cannot request both lowercase and uppercase.")
            columns = self._require_columns(frame, rule.columns, "text_standardization.columns")
            for column in columns:
                original = frame[column].copy()
                values = frame[column].astype("string")
                if rule.trim:
                    values = values.str.strip()
                if rule.collapse_whitespace:
                    values = values.str.replace(r"\s+", " ", regex=True)
                if rule.lowercase:
                    values = values.str.lower()
                if rule.uppercase:
                    values = values.str.upper()
                if rule.value_map:
                    values = values.replace(rule.value_map)
                if rule.empty_to_null:
                    values = values.replace(r"^\s*$", pd.NA, regex=True)
                frame[column] = values
                changed = int((original.astype("string") != frame[column].astype("string")).fillna(False).sum())
                report["operations"].append(
                    {
                        "operation": "text_standardization",
                        "column": column,
                        "cells_changed": changed,
                    }
                )
        return frame

    def _apply_validation_rules(
        self,
        frame: pd.DataFrame,
        rules: list[ValidationRule],
        report: dict[str, Any],
    ) -> pd.DataFrame:
        for rule in rules:
            column = self._require_column(frame, rule.column, "validation_rules.column")
            action = self._one_of(rule.action, {"report_only", "drop_rows"}, "validation_rules.action")
            mask = self._validation_mask(frame[column], rule)
            violations = int(mask.sum())
            entry = {
                "name": rule.name or rule.rule,
                "column": column,
                "rule": rule.rule,
                "action": action,
                "violations": violations,
            }
            if action == "drop_rows" and violations:
                frame = frame.loc[~mask].copy()
                entry["rows_removed"] = violations
            report["validation_rules"].append(entry)
        return frame

    def _validation_mask(self, series: pd.Series, rule: ValidationRule) -> pd.Series:
        rule_name = self._one_of(
            rule.rule,
            {"not_null", "non_negative", "min", "max", "allowed_values", "regex"},
            "validation_rules.rule",
        )
        if rule_name == "not_null":
            return series.isna()
        if rule_name == "non_negative":
            return pd.to_numeric(series, errors="coerce") < 0
        if rule_name == "min":
            return pd.to_numeric(series, errors="coerce") < float(rule.value)
        if rule_name == "max":
            return pd.to_numeric(series, errors="coerce") > float(rule.value)
        if rule_name == "allowed_values":
            return ~series.isin(rule.values)
        pattern = re.compile(str(rule.value or ""))
        return ~series.astype("string").fillna("").str.match(pattern)

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
