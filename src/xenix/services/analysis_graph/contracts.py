from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ConfigDict, Field
from sqlmodel import SQLModel

from ...exceptions import ValidationError

MIN_WIDTH = 200
MAX_WIDTH = 1600
MIN_HEIGHT = 160
MAX_HEIGHT = 1200
MAX_SPEC_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_COLUMNS_IN_ERROR = 30


class GraphDatasetInput(SQLModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    dataset_name: str
    spec: dict[str, Any] | None = None
    wordcloud_spec: dict[str, Any] | None = None


class GraphDatasetResult(SQLModel):
    effective_parameters: dict[str, Any] = Field(default_factory=dict)
    output_path: str
    graph_metadata: dict[str, Any] = Field(default_factory=dict)


class _FieldScan(SQLModel):
    referenced_fields: set[str] = Field(default_factory=set)
    generated_fields: set[str] = Field(default_factory=set)


class _PreparedSpec(SQLModel):
    spec: dict[str, Any]
    title: str
    schema_url: str
    rendered_row_count: int
    truncated: bool
    referenced_fields: list[str]
    generated_fields: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class _PreparedWordcloud:
    title: str
    width: int
    height: int
    referenced_fields: list[str]
    rendered_row_count: int
    truncated: bool
    warnings: list[str]
    frequencies: dict[str, float]
    tooltip_by_word: dict[str, str]
    color_by_word: dict[str, str]
    min_font_size: int
    max_font_size: int
    prefer_horizontal: float
    contains_cjk: bool
    color_mode: str
    color_field: str | None
    top_n: int


def spec_json(spec: dict[str, Any], *, field_name: str) -> str:
    try:
        return json.dumps(spec, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"analysis.graph {field_name} must be JSON-serializable.") from exc
