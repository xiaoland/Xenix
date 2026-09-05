"""Compact routing hints for data.clean.metadata, not an execution schema.

Keep each operation's name, explanation and parameter hints together. Execution
validates inputs against the current intermediate frame in operations.py.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Operation:
    name: str
    summary: str
    params: tuple[str, ...]


@dataclass(frozen=True)
class Group:
    summary: str
    operations: tuple[Operation, ...]


_GROUPS = {
    "schema": Group(
        "Normalize names",
        (
            Operation(
                "schema.normalize_column_names", "Normalize names", ("style?: snake_case", "ascii_lower?: boolean")
            ),
        ),
    ),
    "duplicates": Group(
        "Drop duplicates",
        (
            Operation("duplicate.exact_rows", "Drop duplicates", ("keep?: first|last|false",)),
            Operation("duplicate.key_columns", "Drop key duplicates", ("multiple_columns", "keep?: first|last|false")),
        ),
    ),
    "missing": Group(
        "Fill/drop missing",
        (
            Operation("missing.fill_mean", "Fill mean", ("multiple_columns",)),
            Operation("missing.fill_median", "Fill median", ("multiple_columns",)),
            Operation("missing.fill_mode", "Fill mode", ("multiple_columns",)),
            Operation("missing.fill_constant", "Fill constant", ("multiple_columns", "value")),
            Operation("missing.forward_fill", "Forward-fill gaps", ("multiple_columns",)),
            Operation("missing.drop_rows", "Drop missing rows", ("multiple_columns",)),
            Operation(
                "missing.drop_high_missing_columns",
                "Drop sparse columns",
                ("multiple_columns?", "threshold: number 0..1"),
            ),
        ),
    ),
    "types": Group(
        "Convert types",
        (
            Operation(
                "type.convert",
                "Convert type",
                ("single_column", "target_type: numeric|integer|datetime|text|boolean", "date_format?: string"),
            ),
        ),
    ),
    "text": Group(
        "Clean text",
        (
            Operation("text.trim", "Trim text", ("multiple_columns",)),
            Operation("text.lowercase", "Lowercase", ("multiple_columns",)),
            Operation("text.uppercase", "Uppercase", ("multiple_columns",)),
            Operation("text.collapse_whitespace", "Collapse spaces", ("multiple_columns",)),
            Operation("text.empty_to_null", "Empty to null", ("multiple_columns",)),
            Operation("text.map_values", "Map text", ("multiple_columns", "value_map: object")),
        ),
    ),
    "validation": Group(
        "Check values",
        (
            Operation(
                "validation.not_null",
                "Find nulls",
                ("single_column", "action?: report_only|drop_rows", "name?: string"),
            ),
            Operation(
                "validation.non_negative",
                "Find negatives",
                ("single_column", "action?: report_only|drop_rows", "name?: string"),
            ),
            Operation(
                "validation.min",
                "Find below min",
                ("single_column", "value", "action?: report_only|drop_rows", "name?: string"),
            ),
            Operation(
                "validation.max",
                "Find above max",
                ("single_column", "value", "action?: report_only|drop_rows", "name?: string"),
            ),
            Operation(
                "validation.allowed_values",
                "Find disallowed",
                ("single_column", "values: value[]", "action?: report_only|drop_rows", "name?: string"),
            ),
            Operation(
                "validation.regex",
                "Find regex misses",
                ("single_column", "value", "action?: report_only|drop_rows", "name?: string"),
            ),
        ),
    ),
    "outliers": Group(
        "Clip outliers",
        (Operation("outlier.clip_iqr", "Clip outliers by IQR", ("multiple_columns", "multiplier?: number")),),
    ),
    "encoding": Group(
        "One-hot encode",
        (
            Operation(
                "encoding.one_hot",
                "One-hot encode",
                ("multiple_columns", "drop_first?: boolean", "max_categories?: integer"),
            ),
        ),
    ),
    "scaling": Group(
        "Scale values",
        (
            Operation("scaling.minmax", "Scale to range", ("multiple_columns", "feature_range?: number[2]")),
            Operation("scaling.standard", "Standardize", ("multiple_columns",)),
        ),
    ),
}


def cleaning_operation_group_names() -> tuple[str, ...]:
    """Return the stable, provider-advertised cleaning metadata group names."""
    return tuple(_GROUPS)


def cleaning_operation_metadata(groups: list[str] | None = None) -> dict[str, Any]:
    """Return fresh routing hints; unknown groups are reported alongside valid ones."""
    names = list(dict.fromkeys(str(group or "").strip() for group in groups or ()))
    names = [name for name in names if name] or list(_GROUPS)
    selected = [name for name in names if name in _GROUPS]
    invalid = [name for name in names if name not in _GROUPS]
    result: dict[str, Any] = {
        "column_reference": {
            "index_base": 0,
            "single": "column_index preferred; column_name fallback; choose one",
            "multiple": "column_indexes preferred; column_names fallback; choose one",
        },
        "groups": [
            {
                "group": name,
                "summary": _GROUPS[name].summary,
                "operations": [
                    {"operation": op.name, "summary": op.summary, "params": list(op.params)}
                    for op in _GROUPS[name].operations
                ],
            }
            for name in selected
        ],
        "group_names": list(_GROUPS),
        "operation_count": sum(len(_GROUPS[name].operations) for name in selected),
    }
    if invalid:
        result["invalid_groups"] = [{"group": name, "error_code": "unknown_group"} for name in invalid]
    return result
