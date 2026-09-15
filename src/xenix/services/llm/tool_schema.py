"""Derive advertised Tool definitions from their executable input models."""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from typing import Any, cast

from pydantic import BaseModel

from ...exceptions import ValidationError
from .tool_protocol import AgentTool, AgentToolSpec, ensure_bounded_json


def project_tool_spec(tool: AgentTool[Any]) -> AgentToolSpec:
    """Build a provider definition without making projection an execution prerequisite."""
    schema = project_provider_tool_schema(tool.input_model, field_enums=dict(tool.provider_field_enums))
    ensure_bounded_json(schema, label=f"Tool '{tool.name}' parameter schema")
    return AgentToolSpec(
        name=tool.name,
        provider_name=tool.provider_name,
        description=tool.description,
        parameters_schema=schema,
    )


_FORBIDDEN_PROVIDER_SCHEMA_KEYWORDS = frozenset(
    {
        "allOf",
        "anyOf",
        "dependentRequired",
        "dependentSchemas",
        "else",
        "if",
        "not",
        "oneOf",
        "then",
    }
)
_SIMPLE_JSON_TYPES = frozenset({"array", "boolean", "integer", "null", "number", "object", "string"})


def project_provider_tool_schema(
    input_model: type[BaseModel],
    *,
    field_enums: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    """Project a Pydantic input authority into the portable provider subset."""

    raw_schema = input_model.model_json_schema(mode="validation")
    raw_defs = raw_schema.get("$defs", {})
    if not isinstance(raw_defs, dict):
        raise ValidationError(
            "Tool parameter schema is invalid.",
            error_code="llm_tool_schema_invalid",
        )
    projected = cast(
        dict[str, Any],
        _project_provider_schema_node(
            raw_schema,
            definitions=raw_defs,
            resolving=(),
        ),
    )
    projected.pop("$defs", None)
    if projected.get("type") != "object" or projected.get("additionalProperties") is not False:
        raise ValidationError(
            "Tool input models must project to a closed top-level object.",
            error_code="llm_tool_schema_invalid",
        )

    properties = projected.get("properties")
    if not isinstance(properties, dict):
        raise ValidationError(
            "Tool parameter schema is invalid.",
            error_code="llm_tool_schema_invalid",
        )
    for field_name, raw_values in (field_enums or {}).items():
        field_schema = properties.get(field_name)
        values = tuple(dict.fromkeys(raw_values))
        enum_schema = field_schema
        if (
            isinstance(field_schema, dict)
            and field_schema.get("type") == "array"
            and isinstance(field_schema.get("items"), dict)
        ):
            enum_schema = field_schema["items"]
        if not values or not isinstance(enum_schema, dict) or enum_schema.get("type") != "string":
            raise ValidationError(
                "Tool provider enum projection is invalid.",
                error_code="llm_tool_schema_invalid",
            )
        enum_schema["enum"] = list(values)

    _reject_nonportable_provider_schema(projected)
    return projected


def _project_provider_schema_node(
    raw_node: Any,
    *,
    definitions: dict[str, Any],
    resolving: tuple[str, ...],
) -> Any:
    if isinstance(raw_node, list):
        return [
            _project_provider_schema_node(
                item,
                definitions=definitions,
                resolving=resolving,
            )
            for item in raw_node
        ]
    if not isinstance(raw_node, dict):
        return copy.deepcopy(raw_node)

    node = copy.deepcopy(raw_node)
    reference = node.pop("$ref", None)
    if reference is not None:
        if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
            raise ValidationError(
                "Tool parameter schema contains an unsupported reference.",
                error_code="llm_tool_schema_invalid",
            )
        definition_name = reference.removeprefix("#/$defs/")
        if definition_name in resolving or definition_name not in definitions:
            raise ValidationError(
                "Tool parameter schema contains an invalid reference.",
                error_code="llm_tool_schema_invalid",
            )
        target = _project_provider_schema_node(
            definitions[definition_name],
            definitions=definitions,
            resolving=(*resolving, definition_name),
        )
        if not isinstance(target, dict):
            raise ValidationError(
                "Tool parameter schema contains an invalid reference.",
                error_code="llm_tool_schema_invalid",
            )
        target.update(node)
        node = target

    for combinator in ("anyOf", "oneOf", "allOf"):
        if combinator not in node:
            continue
        raw_variants = node.pop(combinator)
        if not isinstance(raw_variants, list) or not raw_variants:
            raise ValidationError(
                "Tool parameter schema contains an unsupported combinator.",
                error_code="llm_tool_schema_invalid",
            )
        variants = [
            _project_provider_schema_node(
                variant,
                definitions=definitions,
                resolving=resolving,
            )
            for variant in raw_variants
        ]
        collapsed = _collapse_provider_schema_union(variants, combinator=combinator)
        collapsed.update(node)
        if collapsed.get("default") is None:
            collapsed.pop("default", None)
        node = collapsed

    projected: dict[str, Any] = {}
    for key, value in node.items():
        if key == "$defs":
            continue
        if key == "title" and isinstance(value, str):
            continue
        if key == "const":
            projected["enum"] = [copy.deepcopy(value)]
            continue
        if key == "properties":
            if not isinstance(value, dict):
                raise ValidationError(
                    "Tool parameter schema properties are invalid.",
                    error_code="llm_tool_schema_invalid",
                )
            projected[key] = {
                property_name: _project_provider_schema_node(
                    property_schema,
                    definitions=definitions,
                    resolving=resolving,
                )
                for property_name, property_schema in value.items()
            }
            continue
        projected[key] = _project_provider_schema_node(
            value,
            definitions=definitions,
            resolving=resolving,
        )
    return projected


def _collapse_provider_schema_union(
    variants: list[Any],
    *,
    combinator: str,
) -> dict[str, Any]:
    if combinator == "allOf" and len(variants) == 1 and isinstance(variants[0], dict):
        return variants[0]
    if combinator == "allOf":
        raise ValidationError(
            "Tool parameter schema contains an unsupported combinator.",
            error_code="llm_tool_schema_invalid",
        )
    if not all(isinstance(variant, dict) for variant in variants):
        raise ValidationError(
            "Tool parameter schema contains an unsupported union.",
            error_code="llm_tool_schema_invalid",
        )

    typed_variants = [
        variant
        for variant in variants
        if isinstance(variant.get("type"), str) and variant["type"] in _SIMPLE_JSON_TYPES
    ]
    if len(typed_variants) != len(variants):
        raise ValidationError(
            "Tool parameter schema contains an unsupported union.",
            error_code="llm_tool_schema_invalid",
        )

    non_null = [variant for variant in typed_variants if variant["type"] != "null"]
    if len(non_null) == 1 and len(non_null) != len(typed_variants):
        return cast(dict[str, Any], non_null[0])
    if all(set(variant) <= {"type"} for variant in typed_variants):
        types = list(dict.fromkeys(variant["type"] for variant in typed_variants))
        if "number" in types and "integer" in types:
            types.remove("integer")
        return {"type": types[0] if len(types) == 1 else types}
    raise ValidationError(
        "Tool parameter schema contains an unsupported union.",
        error_code="llm_tool_schema_invalid",
    )


def _reject_nonportable_provider_schema(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _reject_nonportable_provider_schema(item)
        return
    if not isinstance(value, dict):
        return
    forbidden = _FORBIDDEN_PROVIDER_SCHEMA_KEYWORDS & set(value)
    if forbidden or "$ref" in value or "$defs" in value:
        raise ValidationError(
            "Tool parameter schema contains unsupported provider keywords.",
            error_code="llm_tool_schema_invalid",
        )
    for item in value.values():
        _reject_nonportable_provider_schema(item)
