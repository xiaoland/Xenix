"""Serializable cleaning requests/results, independent of persistence and pandas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CleanOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    params: dict[str, Any] = Field(default_factory=dict)


class CleanDatasetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    name: str
    operations: list[CleanOperation] = Field(default_factory=list)


class CleanDatasetResult(BaseModel):
    output_path: str
    report: dict[str, Any] = Field(default_factory=dict)
