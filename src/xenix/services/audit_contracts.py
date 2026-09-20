"""Typed audit references and presentation; domain services retain result authority."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, StringConstraints

ExplanationText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]


class AuditReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["dataset", "model", "artifact", "task"]
    id: PositiveInt

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.id}"


class ExecutionOrigin(BaseModel):
    """Internal context supplied by the tool adapter, never provider-authored identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    thread_id: PositiveInt
    tool_call_message_id: PositiveInt | None = None
    explanation: ExplanationText
    submitted_parameters: dict[str, Any] = Field(default_factory=dict)


class ArtifactDerivation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    operation: str
    origin: ExecutionOrigin
    inputs: list[AuditReference] = Field(default_factory=list)
    effective_parameters: dict[str, Any] = Field(default_factory=dict)


class AuditScope(BaseModel):
    all_threads: bool = False
    thread_id: int | None = None


class AuditSummary(BaseModel):
    reference: AuditReference
    title: str
    category: str
    created_at: datetime
    thread_id: int | None = None
    thread_title: str | None = None
    thread_available: bool = False
    task_id: int | None = None
    status: str | None = None
    interpretation_available: bool = False
    rationale: str | None = None
    membership: str = "generated"


class AuditExplanation(BaseModel):
    id: int
    text: str
    thread_id: int
    created_at: datetime
    evidence: list[AuditReference] = Field(default_factory=list)


class AuditInput(BaseModel):
    reference: AuditReference
    title: str
    role: str = ""


class AuditFile(BaseModel):
    artifact_id: int
    title: str
    available: bool


class AuditDetail(BaseModel):
    summary: AuditSummary
    inputs: list[AuditInput] = Field(default_factory=list)
    submitted_parameters: dict[str, Any] | None = None
    effective_parameters: dict[str, Any] | None = None
    selected_parameters: dict[str, Any] | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    files: list[AuditFile] = Field(default_factory=list)
    explanations: list[AuditExplanation] = Field(default_factory=list)
