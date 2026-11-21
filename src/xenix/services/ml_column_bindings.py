"""Validate and persist dataset column roles and their immutable source snapshots."""

from __future__ import annotations

import difflib
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..exceptions import DatasetSourceMissingError, ValidationError
from .dataset_inspection import DatasetInspection, InspectDatasetInput
from .dataset_service import DatasetService
from .ml.contracts import DatasetSnapshotFact
from .ml.registry import get_model_catalog_entry
from .ml.types import ColumnRoleBinding, ColumnRoleKind, ModelRoleSchema
from .storage.models import DatasetColumnBindingRow, DatasetRow
from .storage.repositories import DatasetColumnBindingRepository
from .tabular import resolve_tabular_column_index, resolve_tabular_schema

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


class CreateColumnBindingInput(SQLModel):
    dataset_id: int
    role_bindings: list[dict[str, Any]] = Field(default_factory=list)
    model_key: str | None = None


@dataclass(frozen=True)
class _ResolvedColumnBinding:
    dataset: DatasetRow
    role_bindings: list[ColumnRoleBinding]
    feature_columns: list[str]
    target_columns: list[str]
    inspection: DatasetInspection
    dataset_snapshot: DatasetSnapshotFact


class ColumnBindingService:
    def __init__(self, session_factory: sessionmaker, dataset_service: DatasetService) -> None:
        self._session_factory = session_factory
        self._dataset_service = dataset_service
        self._bindings = DatasetColumnBindingRepository()

    def create(self, input_data: CreateColumnBindingInput) -> DatasetColumnBindingRow:
        dataset_id = input_data.dataset_id
        if not dataset_id:
            raise ValidationError("Column binding requires a dataset.")

        dataset = self._dataset_service.get_dataset(dataset_id)
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")
        inspection = self._dataset_service.inspect_source_file(InspectDatasetInput(source_path=dataset.source_path))
        dataset_snapshot = self._build_dataset_snapshot(dataset, inspection)
        available_columns = {column.name for column in inspection.columns}
        catalog = get_model_catalog_entry(input_data.model_key) if input_data.model_key else None
        role_bindings = self._normalize_role_bindings(
            input_data.role_bindings,
            train_role_schema=catalog.train_role_schema if catalog is not None else None,
            inspection_column_names=[column.name for column in inspection.columns],
        )
        missing_by_role = {
            binding.role: [column for column in binding.columns if column not in available_columns]
            for binding in role_bindings
        }
        missing_by_role = {role: columns for role, columns in missing_by_role.items() if columns}
        if missing_by_role:
            raise ValidationError(
                self._column_binding_error_message(
                    missing_by_role=missing_by_role,
                    available_columns=[column.name for column in inspection.columns],
                )
            )
        self._validate_feature_target_projection(role_bindings)

        with self._session_factory() as session:
            row = self._bindings.create(
                session,
                DatasetColumnBindingRow(
                    dataset_id=dataset.id,
                    role_bindings=[binding.model_dump(mode="json") for binding in role_bindings],
                    dataset_snapshot_payload=dataset_snapshot.model_dump(mode="json"),
                    model_key=catalog.model_key if catalog is not None else None,
                    model_family=catalog.model_family.value if catalog is not None else None,
                    model_task_kind=catalog.model_task_kind.value if catalog is not None else None,
                    schema_version=2,
                ),
            )
            session.commit()
            session.refresh(row)
            return row

    def get(self, binding_id: int) -> DatasetColumnBindingRow:
        with self._session_factory() as session:
            row = self._bindings.get(session, binding_id)
            if row is None:
                raise ValidationError("The selected column binding is invalid.")
            session.expunge(row)
            return row

    def resolve(self, binding_id: int, *, model_key: str) -> "_ResolvedColumnBinding":
        normalized_binding_id = binding_id
        if not normalized_binding_id:
            raise ValidationError("Training requires a column binding.")
        with self._session_factory() as session:
            binding = self._bindings.get(session, normalized_binding_id)
            if binding is None:
                raise ValidationError("The selected column binding is invalid.")
            session.expunge(binding)

        catalog = get_model_catalog_entry(model_key)
        role_bindings = self._normalize_role_bindings(
            binding.role_bindings,
            train_role_schema=catalog.train_role_schema,
        )
        self._validate_feature_target_projection(role_bindings)
        feature_columns, target_columns = self._feature_target_columns(role_bindings)

        dataset = self._dataset_service.get_dataset(binding.dataset_id)
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")
        inspection = self._dataset_service.inspect_source_file(InspectDatasetInput(source_path=dataset.source_path))
        if binding.schema_version < 2 or not binding.dataset_snapshot_payload:
            raise ValidationError(
                "This column binding predates immutable Dataset identity. Re-create the column binding before training."
            )
        try:
            stored_snapshot = DatasetSnapshotFact.model_validate(binding.dataset_snapshot_payload)
        except Exception as exc:
            raise ValidationError(
                "The stored Dataset identity is invalid. Re-create the column binding before training."
            ) from exc
        current_snapshot = self._build_dataset_snapshot(dataset, inspection)
        if stored_snapshot.model_dump(exclude={"sampling_fingerprint"}) != current_snapshot.model_dump(exclude={"sampling_fingerprint"}):
            raise ValidationError(
                "The Dataset contents changed after its column roles were bound. Re-create the column binding "
                "to review roles against the current data."
            )
        available_columns = {column.name for column in inspection.columns}
        missing_by_role = {
            role_binding.role: [column for column in role_binding.columns if column not in available_columns]
            for role_binding in role_bindings
        }
        missing_by_role = {role: columns for role, columns in missing_by_role.items() if columns}
        if missing_by_role:
            raise ValidationError("The stored column binding is invalid for the current dataset file.")
        return _ResolvedColumnBinding(
            dataset=dataset,
            role_bindings=role_bindings,
            feature_columns=feature_columns,
            target_columns=target_columns,
            inspection=inspection,
            dataset_snapshot=stored_snapshot,
        )

    def _build_dataset_snapshot(
        self,
        dataset: DatasetRow,
        inspection: DatasetInspection,
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

    def _normalize_role_bindings(
        self,
        raw_bindings: list[dict[str, Any]],
        *,
        train_role_schema: ModelRoleSchema | None,
        inspection_column_names: list[str] | None = None,
    ) -> list[ColumnRoleBinding]:
        if not raw_bindings:
            raise ValidationError("At least one column role binding is required.")
        schema_by_role = {
            role.name: role
            for role in train_role_schema.roles
        } if train_role_schema is not None else {}
        normalized: list[ColumnRoleBinding] = []
        seen_roles: set[str] = set()
        for raw_binding in raw_bindings:
            binding_payload = self._canonicalize_role_binding_columns(
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
            columns = self._normalize_role_columns(binding.columns, role)
            role_kind = binding.role_kind or (
                role_definition.kind if role_definition is not None else self._infer_role_kind(columns)
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

    def _canonicalize_role_binding_columns(
        self,
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
            payload["columns"] = self._resolve_role_column_indexes(
                raw_binding["column_indexes"],
                role=str(raw_binding.get("role") or ""),
                inspection_column_names=inspection_column_names,
            )
        payload.pop("column_indexes", None)
        return payload

    def _resolve_role_column_indexes(
        self,
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

    def _normalize_role_columns(self, columns: list[str], role: str) -> list[str]:
        normalized = [column.strip() for column in columns if column.strip()]
        if not normalized:
            raise ValidationError(f"Column role '{role}' must bind at least one column.")
        if len(set(normalized)) != len(normalized):
            raise ValidationError(f"Duplicate columns are not allowed for role '{role}'.")
        return normalized

    def _infer_role_kind(self, columns: list[str]) -> ColumnRoleKind:
        return ColumnRoleKind.SINGLE_COLUMN if len(columns) == 1 else ColumnRoleKind.MANY_COLUMNS

    def _feature_target_columns(self, role_bindings: list[ColumnRoleBinding]) -> tuple[list[str], list[str]]:
        feature_columns: list[str] = []
        target_columns: list[str] = []
        for binding in role_bindings:
            if binding.role == "feature":
                feature_columns = list(binding.columns)
            elif binding.role == "target":
                target_columns = list(binding.columns)
        return feature_columns, target_columns

    def _validate_feature_target_projection(self, role_bindings: list[ColumnRoleBinding]) -> None:
        role_by_column: dict[str, str] = {}
        for binding in role_bindings:
            for column in binding.columns:
                previous = role_by_column.get(column)
                if previous is not None and previous != binding.role:
                    raise ValidationError(
                        f"Column '{column}' cannot be bound to multiple roles: '{previous}' and '{binding.role}'."
                    )
                role_by_column[column] = binding.role

    def _column_binding_error_message(
        self,
        *,
        missing_by_role: dict[str, list[str]],
        available_columns: list[str],
    ) -> str:
        lines = ["Bound columns must exist in the dataset."]
        missing_columns: list[str] = []
        for role, columns in missing_by_role.items():
            missing_columns.extend(columns)
            lines.append(f"Missing columns for role '{role}': {_format_column_names(columns)}.")
        suggestions = _column_name_suggestions(
            missing_columns,
            available_columns,
        )
        if suggestions:
            lines.append("Closest available column suggestions:")
            for missing, matches in suggestions.items():
                lines.append(f"- `{missing}` -> {_format_column_names(matches)}")
        lines.append(f"Available columns: {_format_column_names(available_columns)}.")
        lines.append("Use the exact column names returned by data.query or dataset inspection.")
        return "\n".join(lines)


def _format_column_names(columns: list[str]) -> str:
    return ", ".join(f"`{column}`" for column in columns) if columns else "none"


def _column_name_suggestions(missing_columns: list[str], available_columns: list[str]) -> dict[str, list[str]]:
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


def _normalize_column_name_for_match(value: str) -> str:
    return (
        unicodedata.normalize("NFKC", value)
        .translate(_COLUMN_NAME_NORMALIZATION_TRANSLATION)
        .casefold()
        .strip()
    )
