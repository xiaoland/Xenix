"""Read audit relationships and append annotations without rewriting domain facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select
from sqlalchemy.orm import defer

from ..models import (
    ArtifactDerivationRow,
    ArtifactRow,
    AuditExplanationRow,
    ConversationMessageRow,
    ConversationThreadRow,
    DatasetColumnBindingRow,
    DatasetDerivationInputRow,
    DatasetDerivationRow,
    DatasetImportRow,
    DatasetRow,
    KnowledgeDocumentRow,
    MLTaskArtifactRow,
    MLTaskRow,
    TrainedModelRow,
)


@dataclass
class AuditCatalog:
    datasets: dict[int, DatasetRow]
    derivations: dict[int, DatasetDerivationRow]
    edges: list[DatasetDerivationInputRow]
    models: dict[int, TrainedModelRow]
    tasks: dict[int, MLTaskRow]
    artifacts: dict[int, ArtifactRow]
    artifact_derivations: dict[int, ArtifactDerivationRow]
    task_artifacts: list[MLTaskArtifactRow]
    threads: dict[int, ConversationThreadRow]
    imports: dict[int, DatasetImportRow]
    explanations: list[AuditExplanationRow]
    references: set[tuple[str, int]]


class AuditRepository:
    def catalog(self, session: Session, thread_id: int | None, *, details: bool = True) -> AuditCatalog:
        def indexed(model: Any, key: str = "id") -> dict:
            statement = select(model)
            if not details:
                omitted = {
                    MLTaskRow: (MLTaskRow.request_payload, MLTaskRow.result_payload, MLTaskRow.submitted_parameters),
                    DatasetDerivationRow: (DatasetDerivationRow.parameters_payload,),
                }
                for column in omitted.get(model, ()):
                    statement = statement.options(defer(column))
            return {getattr(row, key): row for row in session.exec(statement)}

        knowledge_ids = set(session.exec(select(KnowledgeDocumentRow.source_artifact_id)))
        artifacts = indexed(ArtifactRow)
        artifacts = {key: row for key, row in artifacts.items() if key not in knowledge_ids}
        return AuditCatalog(
            datasets=indexed(DatasetRow),
            derivations=indexed(DatasetDerivationRow, "dataset_id"),
            edges=list(session.exec(select(DatasetDerivationInputRow))) if details else [],
            models=indexed(TrainedModelRow),
            tasks=indexed(MLTaskRow),
            artifacts=artifacts,
            artifact_derivations=indexed(ArtifactDerivationRow, "artifact_id"),
            task_artifacts=list(session.exec(select(MLTaskArtifactRow))),
            threads=indexed(ConversationThreadRow),
            imports=indexed(DatasetImportRow),
            explanations=list(
                session.exec(
                    select(AuditExplanationRow)
                    .options(
                        *([] if details else [defer(AuditExplanationRow.text), defer(AuditExplanationRow.evidence)])
                    )
                    .order_by(AuditExplanationRow.created_at.desc(), AuditExplanationRow.id.desc())
                )
            ),
            references=self.thread_references(session, thread_id) if thread_id else set(),
        )

    def thread_references(self, session: Session, thread_id: int) -> set[tuple[str, int]]:
        references: set[tuple[str, int]] = set()

        def add(kind: str, value: object) -> None:
            if type(value) is int and value > 0:
                references.add((kind, value))

        def handles(payload: object) -> None:
            if not isinstance(payload, dict):
                return
            for key, kind in {
                "dataset_id": "dataset",
                "result_dataset_id": "dataset",
                "trained_model_id": "model",
                "artifact_id": "artifact",
                "ml_task_id": "task",
            }.items():
                add(kind, payload.get(key))
            for key, kind in {
                "task_ids": "task",
                "trained_model_ids": "model",
                "dataset_ids": "dataset",
                "source_dataset_ids": "dataset",
            }.items():
                for value in payload.get(key, []) if isinstance(payload.get(key), list) else []:
                    add(kind, value)
            # Only documented public result containers, never arbitrary JSON or text.
            for key in ("models", "artifacts", "tasks"):
                for child in payload.get(key, []) if isinstance(payload.get(key), list) else []:
                    handles(child)
            handles(payload.get("result"))

        messages = session.exec(select(ConversationMessageRow).where(ConversationMessageRow.thread_id == thread_id))
        for message in messages:
            if message.kind.value == "user":
                for block in message.content_payload.get("content_blocks", message.content_payload.get("blocks", [])):
                    if isinstance(block, dict) and block.get("type") == "dataset":
                        add("dataset", block.get("dataset_id"))
            elif message.kind.value == "tool_call" and (message.tool_id or "").startswith(
                ("data.", "model.", "analysis.")
            ):
                arguments = message.arguments_payload or {}
                handles(arguments)
                datasets = arguments.get("datasets")
                if isinstance(datasets, dict):
                    for value in datasets.values():
                        add("dataset", value)
                binding_id = arguments.get("binding_id")
                if type(binding_id) is int:
                    binding = session.get(DatasetColumnBindingRow, binding_id)
                    if binding:
                        add("dataset", binding.dataset_id)
                for value in (
                    arguments.get("input_sources", []) if isinstance(arguments.get("input_sources"), list) else []
                ):
                    if type(value) is int:
                        add("dataset", value)
                    elif isinstance(value, str) and value.startswith("artifact://") and value[11:].isdigit():
                        add("artifact", int(value[11:]))
            elif message.kind.value == "tool_call" and message.tool_id == "audit.inspect":
                reference = (message.arguments_payload or {}).get("reference")
                if isinstance(reference, dict) and reference.get("kind") in {"dataset", "model", "artifact", "task"}:
                    add(reference["kind"], reference.get("id"))
            elif message.kind.value == "tool_result":
                handles(message.value_payload)
        return references

    def append_explanation(self, session: Session, row: AuditExplanationRow) -> AuditExplanationRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row
