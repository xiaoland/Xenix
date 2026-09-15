"""Ordered DataFrame operations; no filesystem, workers or storage ownership."""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd
from pandas.api.types import is_numeric_dtype

from ...exceptions import ValidationError
from .contracts import CleanOperation
from . import parameters


def apply_operation(
    frame: pd.DataFrame,
    operation: CleanOperation,
    report: dict[str, Any],
) -> pd.DataFrame:
    operation_name = str(operation.operation or "").strip()
    params = dict(operation.params or {})
    if not operation_name:
        raise ValidationError("cleaning operation cannot be empty.")

    if operation_name.startswith("schema."):
        return _apply_schema_operation(frame, operation_name, params, report)
    if operation_name == "duplicate.exact_rows":
        return _apply_duplicate_exact_rows(frame, operation_name, params, report)
    if operation_name == "duplicate.key_columns":
        return _apply_duplicate_key_columns(frame, operation_name, params, report)
    if operation_name.startswith("missing."):
        return _apply_missing_operation(frame, operation_name, params, report)
    if operation_name == "type.convert":
        return _apply_type_convert(frame, operation_name, params, report)
    if operation_name.startswith("text."):
        return _apply_text_operation(frame, operation_name, params, report)
    if operation_name.startswith("validation."):
        return _apply_validation_operation(frame, operation_name, params, report)
    if operation_name.startswith("outlier."):
        return _apply_outlier_operation(frame, operation_name, params, report)
    if operation_name.startswith("encoding."):
        return _apply_encoding_operation(frame, operation_name, params, report)
    if operation_name.startswith("scaling."):
        return _apply_scaling_operation(frame, operation_name, params, report)
    raise ValidationError(f"Unsupported cleaning operation '{operation_name}'.")


def _apply_schema_operation(
    frame: pd.DataFrame,
    operation_name: str,
    params: dict[str, Any],
    report: dict[str, Any],
) -> pd.DataFrame:
    if operation_name != "schema.normalize_column_names":
        raise ValidationError(f"Unsupported cleaning operation '{operation_name}'.")
    style = parameters.one_of(
        str(params.get("style") or "snake_case"),
        {"snake_case"},
        f"{operation_name}.params.style",
    )
    ascii_lower = parameters.bool_param(params, "ascii_lower", default=True, operation_name=operation_name)
    original_columns = [str(column) for column in frame.columns]
    bases: list[str] = []
    generated_empty: list[dict[str, Any]] = []
    for index, column in enumerate(original_columns):
        base, was_empty = parameters.normalize_column_name_base(column, index, ascii_lower=ascii_lower)
        bases.append(base)
        if was_empty:
            generated_empty.append({"column_index": index, "new": base})
    new_columns, duplicate_collisions = parameters.dedupe_normalized_names(bases)
    cleaned = frame.copy()
    cleaned.columns = new_columns
    mapping = [{"old": old, "new": new} for old, new in zip(original_columns, new_columns, strict=False)]
    report["operations"].append(
        {
            "operation": operation_name,
            "style": style,
            "ascii_lower": ascii_lower,
            "columns_changed": sum(1 for old, new in zip(original_columns, new_columns, strict=False) if old != new),
            "mapping": mapping,
            "generated_empty_names": generated_empty,
            "duplicate_collisions": duplicate_collisions,
        }
    )
    return cleaned


def _apply_duplicate_exact_rows(
    frame: pd.DataFrame,
    operation_name: str,
    params: dict[str, Any],
    report: dict[str, Any],
) -> pd.DataFrame:
    keep = parameters.keep_value(params, operation_name)
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
    frame: pd.DataFrame,
    operation_name: str,
    params: dict[str, Any],
    report: dict[str, Any],
) -> pd.DataFrame:
    columns = parameters.params_columns(frame, params, operation_name)
    keep = parameters.keep_value(params, operation_name)
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
        "missing.drop_high_missing_columns": "drop_high_missing_columns",
    }
    strategy = strategy_by_operation.get(operation_name)
    if strategy is None:
        raise ValidationError(f"Unsupported cleaning operation '{operation_name}'.")
    if strategy == "drop_high_missing_columns":
        return _apply_drop_high_missing_columns(frame, operation_name, params, report)

    columns = parameters.params_columns(frame, params, operation_name)
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
        resolved_fill_value: Any | None = None
        if strategy == "forward_fill":
            frame[column] = frame[column].ffill()
        else:
            fill_value = _resolve_fill_value(frame[column], strategy, column, params.get("value"), report)
            frame[column] = frame[column].fillna(fill_value)
            resolved_fill_value = _report_scalar(fill_value)
        operation_report = {
            "operation": operation_name,
            "column": column,
            "cells_filled": missing_before - int(frame[column].isna().sum()),
        }
        if strategy != "forward_fill":
            operation_report["resolved_fill_value"] = resolved_fill_value
        report["operations"].append(operation_report)
    return frame


def _apply_drop_high_missing_columns(
    frame: pd.DataFrame,
    operation_name: str,
    params: dict[str, Any],
    report: dict[str, Any],
) -> pd.DataFrame:
    threshold = parameters.ratio_param(params, "threshold", operation_name)
    columns = parameters.params_optional_columns(frame, params, operation_name)
    ratios = {column: float(frame[column].isna().mean()) for column in columns}
    dropped_columns = [column for column, ratio in ratios.items() if ratio > threshold]
    cleaned = frame.drop(columns=dropped_columns) if dropped_columns else frame
    report["operations"].append(
        {
            "operation": operation_name,
            "threshold": threshold,
            "evaluated_columns": columns,
            "missing_ratios": ratios,
            "dropped_columns": dropped_columns,
            "columns_removed": len(dropped_columns),
        }
    )
    return cleaned


def _resolve_fill_value(
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


def _report_scalar(value: Any) -> str | int | float | bool | None:
    """Normalize one resolved operation value for JSON report persistence."""

    item = value
    scalar_item = getattr(item, "item", None)
    if callable(scalar_item):
        try:
            item = scalar_item()
        except TypeError, ValueError:
            item = value
    if isinstance(item, float) and not math.isfinite(item):
        return str(item)
    if item is None or isinstance(item, str | int | float | bool):
        return item
    isoformat = getattr(item, "isoformat", None)
    if callable(isoformat):
        try:
            return str(isoformat())
        except TypeError, ValueError:
            pass
    return str(item)


def _apply_type_convert(
    frame: pd.DataFrame,
    operation_name: str,
    params: dict[str, Any],
    report: dict[str, Any],
) -> pd.DataFrame:
    column = parameters.params_column(frame, params, operation_name)
    target_type = parameters.one_of(
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
        converted = parameters.to_boolean(frame[column])
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
    frame: pd.DataFrame,
    operation_name: str,
    params: dict[str, Any],
    report: dict[str, Any],
) -> pd.DataFrame:
    columns = parameters.params_columns(frame, params, operation_name)
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
    frame: pd.DataFrame,
    operation_name: str,
    params: dict[str, Any],
    report: dict[str, Any],
) -> pd.DataFrame:
    column = parameters.params_column(frame, params, operation_name)
    action = parameters.one_of(
        str(params.get("action") or "report_only"),
        {"report_only", "drop_rows"},
        f"{operation_name}.params.action",
    )
    mask = _validation_mask(frame[column], operation_name, params).fillna(False).astype(bool)
    violations = int(mask.sum())
    entry = {
        "name": str(params.get("name") or operation_name).strip() or operation_name,
        "column": column,
        "operation": operation_name,
        "action": action,
        "violations": violations,
    }
    if action == "drop_rows" and violations:
        row_count_before = int(len(frame.index))
        frame = frame.loc[~mask].copy()
        entry["rows_removed"] = row_count_before - int(len(frame.index))
    report["validation_rules"].append(entry)
    return frame


def _validation_mask(series: pd.Series, operation_name: str, params: dict[str, Any]) -> pd.Series:
    if operation_name == "validation.not_null":
        return series.isna()
    if operation_name == "validation.non_negative":
        return pd.to_numeric(series, errors="coerce") < 0
    if operation_name == "validation.min":
        return pd.to_numeric(series, errors="coerce") < parameters.float_param(params, operation_name)
    if operation_name == "validation.max":
        return pd.to_numeric(series, errors="coerce") > parameters.float_param(params, operation_name)
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


def _apply_outlier_operation(
    frame: pd.DataFrame,
    operation_name: str,
    params: dict[str, Any],
    report: dict[str, Any],
) -> pd.DataFrame:
    if operation_name != "outlier.clip_iqr":
        raise ValidationError(f"Unsupported cleaning operation '{operation_name}'.")
    columns = parameters.params_columns(frame, params, operation_name)
    multiplier = parameters.positive_float_param(params, "multiplier", operation_name, default=1.5)
    summaries: list[dict[str, Any]] = []
    for column in columns:
        parameters.require_numeric_column(frame, column, operation_name)
        series = frame[column]
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        if pd.isna(q1) or pd.isna(q3):
            report["warnings"].append(f"Column '{column}' has no numeric values for IQR clipping.")
            summaries.append(
                {
                    "column": column,
                    "q1": None,
                    "q3": None,
                    "iqr": None,
                    "lower_bound": None,
                    "upper_bound": None,
                    "cells_clipped": 0,
                }
            )
            continue
        iqr = q3 - q1
        lower_bound = q1 - multiplier * iqr
        upper_bound = q3 + multiplier * iqr
        clipped = series.clip(lower=lower_bound, upper=upper_bound)
        cells_clipped = int((series.notna() & (series != clipped)).sum())
        frame[column] = clipped
        summaries.append(
            {
                "column": column,
                "q1": float(q1),
                "q3": float(q3),
                "iqr": float(iqr),
                "lower_bound": float(lower_bound),
                "upper_bound": float(upper_bound),
                "cells_clipped": cells_clipped,
            }
        )
    report["operations"].append(
        {
            "operation": operation_name,
            "columns": columns,
            "multiplier": multiplier,
            "columns_summary": summaries,
        }
    )
    return frame


def _apply_encoding_operation(
    frame: pd.DataFrame,
    operation_name: str,
    params: dict[str, Any],
    report: dict[str, Any],
) -> pd.DataFrame:
    if operation_name != "encoding.one_hot":
        raise ValidationError(f"Unsupported cleaning operation '{operation_name}'.")
    columns = parameters.params_columns(frame, params, operation_name)
    drop_first = parameters.bool_param(params, "drop_first", default=False, operation_name=operation_name)
    max_categories = parameters.positive_int_param(params, "max_categories", operation_name, default=50)
    used_columns = {str(column) for column in frame.columns if str(column) not in columns}
    generated_frames: list[pd.DataFrame] = []
    encoded_columns: list[str] = []
    skipped_columns: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for column in columns:
        series = frame[column]
        categories = sorted(series.dropna().unique().tolist(), key=lambda value: str(value))
        if len(categories) > max_categories:
            skipped_columns.append(
                {
                    "column": column,
                    "category_count": len(categories),
                    "max_categories": max_categories,
                    "reason": "too_many_categories",
                }
            )
            report["warnings"].append(
                f"Column '{column}' has {len(categories)} categories, above max_categories={max_categories}; it was not encoded."
            )
            continue
        emitted_categories = categories[1:] if drop_first else categories
        generated_data: dict[str, pd.Series] = {}
        generated_names: list[str] = []
        category_columns: list[dict[str, str]] = []
        for category in emitted_categories:
            raw_name = f"{column}_{category}"
            generated_name = parameters.normalized_unique_column_name(raw_name, used_columns)
            used_columns.add(generated_name)
            generated_data[generated_name] = series.eq(category).fillna(False).astype(int)
            generated_names.append(generated_name)
            category_columns.append({"category": str(category), "column": generated_name})
        if generated_data:
            generated_frames.append(pd.DataFrame(generated_data, index=frame.index))
        encoded_columns.append(column)
        summaries.append(
            {
                "column": column,
                "category_count": len(categories),
                "encoded_category_count": len(emitted_categories),
                "drop_first": drop_first,
                "generated_columns": generated_names,
                "category_columns": category_columns,
            }
        )

    cleaned = frame.drop(columns=encoded_columns) if encoded_columns else frame
    if generated_frames:
        cleaned = pd.concat([cleaned, *generated_frames], axis=1)
    report["operations"].append(
        {
            "operation": operation_name,
            "columns": columns,
            "drop_first": drop_first,
            "max_categories": max_categories,
            "encoded_columns": encoded_columns,
            "skipped_columns": skipped_columns,
            "columns_summary": summaries,
        }
    )
    return cleaned


def _apply_scaling_operation(
    frame: pd.DataFrame,
    operation_name: str,
    params: dict[str, Any],
    report: dict[str, Any],
) -> pd.DataFrame:
    columns = parameters.params_columns(frame, params, operation_name)
    if operation_name == "scaling.minmax":
        feature_min, feature_max = parameters.feature_range_param(params, operation_name)
        summaries = []
        for column in columns:
            parameters.require_numeric_column(frame, column, operation_name)
            series = frame[column]
            original_min = series.min()
            original_max = series.max()
            if pd.isna(original_min) or pd.isna(original_max) or original_min == original_max:
                report["warnings"].append(f"Column '{column}' is empty or constant; minmax scaling left it unchanged.")
                summaries.append(
                    {
                        "column": column,
                        "original_min": None if pd.isna(original_min) else float(original_min),
                        "original_max": None if pd.isna(original_max) else float(original_max),
                        "target_min": feature_min,
                        "target_max": feature_max,
                        "scaled": False,
                    }
                )
                continue
            frame[column] = ((series - original_min) / (original_max - original_min)) * (
                feature_max - feature_min
            ) + feature_min
            summaries.append(
                {
                    "column": column,
                    "original_min": float(original_min),
                    "original_max": float(original_max),
                    "target_min": feature_min,
                    "target_max": feature_max,
                    "scaled": True,
                }
            )
        report["operations"].append(
            {
                "operation": operation_name,
                "columns": columns,
                "feature_range": [feature_min, feature_max],
                "columns_summary": summaries,
            }
        )
        return frame

    if operation_name == "scaling.standard":
        summaries = []
        for column in columns:
            parameters.require_numeric_column(frame, column, operation_name)
            series = frame[column]
            mean = series.mean()
            std = series.std(ddof=0)
            if pd.isna(mean) or pd.isna(std) or std == 0:
                report["warnings"].append(
                    f"Column '{column}' is empty or constant; standard scaling left it unchanged."
                )
                summaries.append(
                    {
                        "column": column,
                        "mean": None if pd.isna(mean) else float(mean),
                        "std": None if pd.isna(std) else float(std),
                        "scaled": False,
                    }
                )
                continue
            frame[column] = (series - mean) / std
            summaries.append(
                {
                    "column": column,
                    "mean": float(mean),
                    "std": float(std),
                    "scaled": True,
                }
            )
        report["operations"].append(
            {
                "operation": operation_name,
                "columns": columns,
                "columns_summary": summaries,
            }
        )
        return frame

    raise ValidationError(f"Unsupported cleaning operation '{operation_name}'.")
