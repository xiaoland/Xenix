"""Resolve parameters against the current frame, including column identity."""

from __future__ import annotations

import unicodedata
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from ...exceptions import ValidationError
from ..tabular import resolve_tabular_column_index, resolve_tabular_schema


def float_param(params: dict[str, Any], operation_name: str) -> float:
    if "value" not in params:
        raise ValidationError(f"{operation_name}.params.value is required.")
    try:
        return float(params.get("value"))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{operation_name}.params.value must be numeric.") from exc


def ratio_param(params: dict[str, Any], key: str, operation_name: str) -> float:
    if key not in params:
        raise ValidationError(f"{operation_name}.params.{key} is required.")
    try:
        value = float(params.get(key))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{operation_name}.params.{key} must be numeric.") from exc
    if value < 0 or value > 1:
        raise ValidationError(f"{operation_name}.params.{key} must be between 0 and 1.")
    return value


def positive_float_param(
    params: dict[str, Any],
    key: str,
    operation_name: str,
    *,
    default: float,
) -> float:
    raw_value = params.get(key, default)
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{operation_name}.params.{key} must be numeric.") from exc
    if value <= 0:
        raise ValidationError(f"{operation_name}.params.{key} must be greater than 0.")
    return value


def positive_int_param(
    params: dict[str, Any],
    key: str,
    operation_name: str,
    *,
    default: int,
) -> int:
    raw_value = params.get(key, default)
    if isinstance(raw_value, bool):
        raise ValidationError(f"{operation_name}.params.{key} must be an integer.")
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{operation_name}.params.{key} must be an integer.") from exc
    if value < 1:
        raise ValidationError(f"{operation_name}.params.{key} must be greater than 0.")
    return value


def bool_param(
    params: dict[str, Any],
    key: str,
    *,
    default: bool,
    operation_name: str,
) -> bool:
    if key not in params:
        return default
    value = params.get(key)
    if not isinstance(value, bool):
        raise ValidationError(f"{operation_name}.params.{key} must be a boolean.")
    return value


def feature_range_param(params: dict[str, Any], operation_name: str) -> tuple[float, float]:
    raw_value = params.get("feature_range", [0, 1])
    if not isinstance(raw_value, list) or len(raw_value) != 2:
        raise ValidationError(f"{operation_name}.params.feature_range must be a two-number list.")
    try:
        feature_min = float(raw_value[0])
        feature_max = float(raw_value[1])
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{operation_name}.params.feature_range values must be numeric.") from exc
    if feature_min >= feature_max:
        raise ValidationError(f"{operation_name}.params.feature_range first value must be less than second value.")
    return feature_min, feature_max


def keep_value(params: dict[str, Any], operation_name: str) -> str | bool:
    keep = one_of(str(params.get("keep") or "first"), {"first", "last", "false"}, f"{operation_name}.params.keep")
    return False if keep == "false" else keep


def params_columns(frame: pd.DataFrame, params: dict[str, Any], operation_name: str) -> list[str]:
    return _resolve_column_list_reference(
        frame,
        params,
        operation_name,
        required=True,
    )


def params_optional_columns(frame: pd.DataFrame, params: dict[str, Any], operation_name: str) -> list[str]:
    return _resolve_column_list_reference(
        frame,
        params,
        operation_name,
        required=False,
    )


def params_column(frame: pd.DataFrame, params: dict[str, Any], operation_name: str) -> str:
    active_keys = _active_reference_keys(
        params,
        ("column_index", "column_name", "column"),
    )
    if len(active_keys) > 1:
        raise ValidationError(f"{operation_name}.params must use either column_index or column_name, not both.")
    if not active_keys:
        raise ValidationError(f"{operation_name}.params requires column_index or column_name.")
    key = active_keys[0]
    if key == "column_index":
        return _column_at_index(
            frame,
            params.get(key),
            f"{operation_name}.params.column_index",
        )
    return _require_column(frame, str(params.get(key) or ""), f"{operation_name}.params.{key}")


def _resolve_column_list_reference(
    frame: pd.DataFrame,
    params: dict[str, Any],
    operation_name: str,
    *,
    required: bool,
) -> list[str]:
    active_keys = _active_reference_keys(
        params,
        ("column_indexes", "column_names", "columns"),
    )
    if len(active_keys) > 1:
        raise ValidationError(f"{operation_name}.params must use either column_indexes or column_names, not both.")
    if not active_keys:
        if required:
            raise ValidationError(f"{operation_name}.params requires column_indexes or column_names.")
        return [str(column) for column in frame.columns]
    key = active_keys[0]
    values = params.get(key)
    if not isinstance(values, list):
        raise ValidationError(f"{operation_name}.params.{key} must be a list.")
    if key == "column_indexes":
        if not values:
            raise ValidationError(f"{operation_name}.params.column_indexes cannot be empty.")
        return [_column_at_index(frame, value, f"{operation_name}.params.column_indexes") for value in values]
    return _require_columns(frame, values, f"{operation_name}.params.{key}")


def _active_reference_keys(params: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if key in params and params.get(key) is not None]


def _column_at_index(frame: pd.DataFrame, value: Any, field_name: str) -> str:
    schema = resolve_tabular_schema(frame.columns)
    return resolve_tabular_column_index(schema, value, field_name=field_name)


def require_numeric_column(frame: pd.DataFrame, column: str, operation_name: str) -> None:
    if not is_numeric_dtype(frame[column]) or is_bool_dtype(frame[column]):
        raise ValidationError(f"Column '{column}' must be numeric for {operation_name}.")


def normalize_column_name_base(
    value: str,
    index: int,
    *,
    ascii_lower: bool = True,
) -> tuple[str, bool]:
    normalized = unicodedata.normalize("NFKC", str(value or "").strip())
    parts: list[str] = []
    previous_was_separator = False
    for char in normalized:
        if char.isalnum():
            if ascii_lower and "A" <= char <= "Z":
                char = char.lower()
            parts.append(char)
            previous_was_separator = False
        elif not previous_was_separator:
            parts.append("_")
            previous_was_separator = True
    candidate = "".join(parts).strip("_")
    if not candidate:
        return f"column_{index + 1}", True
    return candidate, False


def dedupe_normalized_names(bases: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    used: set[str] = set()
    seen_by_base: dict[str, int] = {}
    names: list[str] = []
    collisions: list[dict[str, Any]] = []
    for index, base in enumerate(bases):
        count = seen_by_base.get(base, 0) + 1
        seen_by_base[base] = count
        candidate = base if count == 1 else f"{base}_{count}"
        while candidate in used:
            count += 1
            seen_by_base[base] = count
            candidate = f"{base}_{count}"
        if candidate != base:
            collisions.append(
                {
                    "column_index": index,
                    "base_name": base,
                    "resolved_name": candidate,
                }
            )
        names.append(candidate)
        used.add(candidate)
    return names, collisions


def normalized_unique_column_name(value: str, used_names: set[str]) -> str:
    base, _was_empty = normalize_column_name_base(value, len(used_names), ascii_lower=True)
    candidate = base
    suffix = 2
    while candidate in used_names:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def to_boolean(series: pd.Series) -> pd.Series:
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


def _require_columns(frame: pd.DataFrame, columns: list[str], field_name: str) -> list[str]:
    normalized = [_require_column(frame, column, field_name) for column in columns if str(column).strip()]
    if not normalized:
        raise ValidationError(f"{field_name} cannot be empty.")
    return normalized


def _require_column(frame: pd.DataFrame, column: str, field_name: str) -> str:
    normalized = str(column or "").strip()
    if not normalized:
        raise ValidationError(f"{field_name} cannot be empty.")
    if normalized not in frame.columns:
        raise ValidationError(f"Column '{normalized}' does not exist.")
    return normalized


def one_of(value: str, allowed: set[str], field_name: str) -> str:
    normalized = str(value or "").strip()
    if normalized not in allowed:
        raise ValidationError(f"{field_name} must be one of: {', '.join(sorted(allowed))}.")
    return normalized
