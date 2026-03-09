from __future__ import annotations

from pydantic import BaseModel

from .types import ModelDefinition


class EmptyParams(BaseModel):
    pass


_MODEL_DEFINITIONS: dict[str, ModelDefinition] = {}


def list_model_keys() -> list[str]:
    return list(_MODEL_DEFINITIONS.keys())


def get_model_definition(model_key: str) -> ModelDefinition:
    if model_key not in _MODEL_DEFINITIONS:
        raise ValueError(f"Unknown model definition: {model_key}")
    return _MODEL_DEFINITIONS[model_key]


def list_model_definitions() -> list[ModelDefinition]:
    return list(_MODEL_DEFINITIONS.values())
