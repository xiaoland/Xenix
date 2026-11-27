from __future__ import annotations

import difflib
import unicodedata
from typing import Any

from ...exceptions import ValidationError
from ..ml.types import ColumnRoleBinding, ColumnRoleKind, ModelRoleSchema
from ..tabular import resolve_tabular_column_index, resolve_tabular_schema

_COLUMN_NAME_NORMALIZATION_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
)


def normalize_role_bindings(
    raw_bindings: list[dict[str, Any]],
    *,
    train_role_schema: ModelRoleSchema | None,
    inspection_column_names: list[str] | None = None,
) -> list[ColumnRoleBinding]:
    if not raw_bindings:
        raise ValidationError("At least one column role binding is required.")
    schema_by_role = (
        {role.name: role for role in train_role_schema.roles}
        if train_role_schema is not None
        else {}
    )
    normalized: list[ColumnRoleBinding] = []
    seen_roles: set[str] = set()
    for raw_binding in raw_bindings:
        binding_payload = canonicalize_role_binding_columns(
            raw_binding,
            inspection_column_names=inspection_column_names,
        )
        try:
            binding = ColumnRoleBinding.model_validate(binding_payload)
        except Exception as exc:
            raise ValidationError("Column role bindings must be valid role binding objects.") from exc
        role = binding.role.strip()
        if not role:
            raise ValidationError("Column role binding names cannot be empty.")
        if role in seen_roles:
            raise ValidationError(f"Duplicate column role binding '{role}' is not allowed.")
        seen_roles.add(role)
        role_definition = schema_by_role.get(role)
        if train_role_schema is not None and role_definition is None and not train_role_schema.additional_roles:
            raise ValidationError(f"Column role '{role}' is not accepted by the selected model.")
        columns = normalize_role_columns(binding.columns, role)
        role_kind = binding.role_kind or (
            role_definition.kind if role_definition is not None else infer_role_kind(columns)
        )
        if role_definition is not None and role_kind != role_definition.kind:
            raise ValidationError(f"Column role '{role}' must use role kind '{role_definition.kind.value}'.")
        if role_kind is ColumnRoleKind.SINGLE_COLUMN and len(columns) != 1:
            raise ValidationError(f"Column role '{role}' must bind exactly one column.")
        if role_kind is ColumnRoleKind.MANY_COLUMNS and not columns:
            raise ValidationError(f"Column role '{role}' must bind at least one column.")
        normalized.append(
            ColumnRoleBinding(
                role=role,
                columns=columns,
                role_kind=role_kind,
                required=role_definition.required if role_definition is not None else binding.required,
                metadata=dict(binding.metadata),
            )
        )

    if train_role_schema is not None:
        missing_roles = [
            role.name
            for role in train_role_schema.roles
            if role.required and role.name not in seen_roles
        ]
        if missing_roles:
            raise ValidationError(f"Missing required column roles: {', '.join(missing_roles)}.")
    return normalized


def canonicalize_role_binding_columns(
    raw_binding: dict[str, Any],
    *,
    inspection_column_names: list[str] | None,
) -> dict[str, Any]:
    if not isinstance(raw_binding, dict):
        raise ValidationError("Column role bindings must be valid role binding objects.")

    reference_keys = [
        key
        for key in ("columns", "column_indexes")
        if key in raw_binding and raw_binding[key] is not None
    ]
    if len(reference_keys) > 1:
        raise ValidationError("Column role bindings must use either columns or column_indexes, not both.")
    if not reference_keys:
        raise ValidationError("Column role bindings require columns or column_indexes.")

    payload = dict(raw_binding)
    if reference_keys[0] == "column_indexes":
        payload["columns"] = resolve_role_column_indexes(
            raw_binding["column_indexes"],
            role=str(raw_binding.get("role") or ""),
            inspection_column_names=inspection_column_names,
        )
    payload.pop("column_indexes", None)
    return payload


def resolve_role_column_indexes(
    raw_indexes: Any,
    *,
    role: str,
    inspection_column_names: list[str] | None,
) -> list[str]:
    role_label = role.strip() or "<unnamed>"
    if inspection_column_names is None:
        raise ValidationError("Column indexes can only be resolved while creating a column binding.")
    if not isinstance(raw_indexes, list):
        raise ValidationError(f"Column role '{role_label}' column_indexes must be a list.")
    if not raw_indexes:
        raise ValidationError(f"Column role '{role_label}' column_indexes cannot be empty.")

    schema = resolve_tabular_schema(inspection_column_names)
    columns: list[str] = []
    for index in raw_indexes:
        field_name = f"Column role '{role_label}' column_indexes"
        try:
            columns.append(resolve_tabular_column_index(schema, index, field_name=field_name))
        except ValidationError as exc:
            # Keep the role-binding contract's actionable wording while
            # delegating strict type/range semantics to the shared helper.
            if isinstance(index, bool) or not isinstance(index, int):
                raise ValidationError(
                    f"Column role '{role_label}' column_indexes must contain zero-based integer indexes."
                ) from exc
            raise ValidationError(
                f"Column role '{role_label}' column_indexes index {index} is outside the available "
                "zero-based column range."
            ) from exc
    return columns


def normalize_role_columns(columns: list[str], role: str) -> list[str]:
    normalized = [column.strip() for column in columns if column.strip()]
    if not normalized:
        raise ValidationError(f"Column role '{role}' must bind at least one column.")
    if len(set(normalized)) != len(normalized):
        raise ValidationError(f"Duplicate columns are not allowed for role '{role}'.")
    return normalized


def infer_role_kind(columns: list[str]) -> ColumnRoleKind:
    return ColumnRoleKind.SINGLE_COLUMN if len(columns) == 1 else ColumnRoleKind.MANY_COLUMNS


def feature_target_columns(role_bindings: list[ColumnRoleBinding]) -> tuple[list[str], list[str]]:
    feature_columns: list[str] = []
    target_columns: list[str] = []
    for binding in role_bindings:
        if binding.role == "feature":
            feature_columns = list(binding.columns)
        elif binding.role == "target":
            target_columns = list(binding.columns)
    return feature_columns, target_columns


def validate_feature_target_projection(role_bindings: list[ColumnRoleBinding]) -> None:
    role_by_column: dict[str, str] = {}
    for binding in role_bindings:
        for column in binding.columns:
            previous = role_by_column.get(column)
            if previous is not None and previous != binding.role:
                raise ValidationError(
                    f"Column '{column}' cannot be bound to multiple roles: '{previous}' and '{binding.role}'."
                )
            role_by_column[column] = binding.role


def apply_columns_from_metadata(metadata: Any) -> list[str]:
    schema_roles = metadata.apply_role_schema.get("roles") if isinstance(metadata.apply_role_schema, dict) else None
    role_names = [
        str(role.get("name"))
        for role in schema_roles or []
        if isinstance(role, dict) and role.get("required", True)
    ]
    if not role_names:
        role_names = ["feature"]
    columns: list[str] = []
    for role_name in role_names:
        columns.extend(role_columns(metadata.train_role_bindings, role_name))
    return columns


def normalize_columns(columns: list[str], label: str) -> list[str]:
    normalized = [column.strip() for column in columns if column.strip()]
    if not normalized:
        raise ValidationError(f"At least one {label} column must be selected.")
    if len(set(normalized)) != len(normalized):
        raise ValidationError(f"Duplicate {label} columns are not allowed.")
    return normalized


def column_binding_error_message(
    *,
    missing_by_role: dict[str, list[str]],
    available_columns: list[str],
) -> str:
    lines = ["Bound columns must exist in the dataset."]
    missing_columns: list[str] = []
    for role, columns in missing_by_role.items():
        missing_columns.extend(columns)
        lines.append(f"Missing columns for role '{role}': {format_column_names(columns)}.")
    suggestions = column_name_suggestions(missing_columns, available_columns)
    if suggestions:
        lines.append("Closest available column suggestions:")
        for missing, matches in suggestions.items():
            lines.append(f"- `{missing}` -> {format_column_names(matches)}")
    lines.append(f"Available columns: {format_column_names(available_columns)}.")
    lines.append("Use the exact column names returned by data.query or dataset inspection.")
    return "\n".join(lines)


def format_column_names(columns: list[str]) -> str:
    return ", ".join(f"`{column}`" for column in columns) if columns else "none"


def column_name_suggestions(missing_columns: list[str], available_columns: list[str]) -> dict[str, list[str]]:
    available_by_normalized: dict[str, list[str]] = {}
    for column in available_columns:
        available_by_normalized.setdefault(_normalize_column_name_for_match(column), []).append(column)

    suggestions: dict[str, list[str]] = {}
    normalized_available = list(available_by_normalized)
    for missing in missing_columns:
        normalized_missing = _normalize_column_name_for_match(missing)
        matches = list(available_by_normalized.get(normalized_missing) or [])
        if not matches:
            close_keys = difflib.get_close_matches(normalized_missing, normalized_available, n=3, cutoff=0.84)
            for key in close_keys:
                matches.extend(available_by_normalized[key])
        if matches:
            suggestions[missing] = matches[:3]
    return suggestions


def role_columns(role_bindings: list[dict[str, Any]], role: str) -> list[str]:
    for binding in role_bindings:
        if binding.get("role") == role:
            columns = binding.get("columns")
            if isinstance(columns, list):
                return [str(column) for column in columns]
    return []


def _normalize_column_name_for_match(value: str) -> str:
    return (
        unicodedata.normalize("NFKC", value)
        .translate(_COLUMN_NAME_NORMALIZATION_TRANSLATION)
        .casefold()
        .strip()
    )
