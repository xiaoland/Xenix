from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from pydantic import BaseModel

BaseModelLike: TypeAlias = type[BaseModel]


@dataclass(frozen=True)
class ModelDefinition:
    model_key: str
    family: str
    display_name: str
    supports_fit: bool
    supports_hyperparameter_tuning: bool
    supports_inference: bool
    param_model: BaseModelLike
    param_grid_model: BaseModelLike | None = None
