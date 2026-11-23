"""Service-owned, read-only audit projection and separately owned Agent annotations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

from ..exceptions import NotFoundError, ValidationError
from .audit_contracts import (
    ArtifactDerivation,
    AuditDetail,
    AuditExplanation,
    AuditFile,
    AuditInput,
    AuditReference,
    AuditScope,
    AuditSummary,
    ExplanationText,
)
from .storage.models import ArtifactRow, AuditExplanationRow, DatasetRow, MLTaskStatus, TrainedModelRow
from .storage.repositories.audit import AuditCatalog, AuditRepository

if TYPE_CHECKING:
    from sqlalchemy.engine import Row
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import Session


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _require_audit_row(catalog: AuditCatalog, reference: AuditReference) -> Row[Any]:
    row = catalog.summaries.get((reference.kind, reference.id))
    if row is None:
        raise NotFoundError(f"Audit object '{reference.key}' was not found.")
    return row


def _directly_associated(
    reference: AuditReference,
    origin_thread_id: int | None,
    thread_id: int,
    references: set[tuple[str, int]],
) -> bool:
    return origin_thread_id == thread_id or (reference.kind, reference.id) in references


def _summary(catalog: AuditCatalog, reference: AuditReference, *, membership: str = "generated") -> AuditSummary:
    row = _require_audit_row(catalog, reference)
    return AuditSummary(
        reference=reference,
        title=row.title,
        category=row.category,
        created_at=_utc(row.created_at),
        thread_id=row.thread_id,
        thread_title=row.thread_title,
        thread_available=row.thread_available,
        task_id=row.task_id,
        status=row.status.value if row.status is not None else None,
        rationale=row.rationale,
        interpretation_available=row.interpretation_available,
        membership=membership,
    )


def _input_references(
    catalog: AuditCatalog, reference: AuditReference, artifact_record: ArtifactDerivation | None,
) -> list[tuple[AuditReference, str]]:
    inputs: dict[tuple[AuditReference, str], None] = {}

    def add(kind: str, object_id: int | None, role: str = "") -> None:
        if object_id:
            ref = AuditReference(kind=kind, id=object_id)
            if ref != reference:
                inputs[(ref, role)] = None

    task = catalog.task
    if task:
        if task.task_type.value == "apply":
            payload = task.result_payload or {}
            for source in payload.get("source_dataset_ids", []):
                add("dataset", source, "apply input")
            for source in payload.get("source_artifact_ids", []):
                add("artifact", source, "apply input")
            add("model", (task.request_payload.get("apply_model") or {}).get("trained_model_id"), "model")
        else:
            add("dataset", task.dataset_id, "training input")
    row = catalog.subject
    if isinstance(row, DatasetRow):
        if catalog.dataset_derivation:
            for edge in catalog.edges:
                add("dataset", edge.input_dataset_id, edge.alias or "input")
        elif not catalog.dataset_import:
            add("dataset", row.derived_from_dataset_id, "recorded parent")
    elif isinstance(row, TrainedModelRow) and catalog.evaluation:
        add("task", catalog.evaluation.id, "evaluation")
    elif isinstance(row, ArtifactRow):
        if artifact_record:
            for ref in artifact_record.inputs:
                add(ref.kind, ref.id)
        else:
            add("dataset", row.metadata_payload.get("dataset_id"))
    return list(inputs)


def _artifact_record(catalog: AuditCatalog) -> ArtifactDerivation | None:
    if catalog.artifact_derivation:
        return ArtifactDerivation.model_validate(catalog.artifact_derivation.payload)
    return None


def _public_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Do not turn internal filesystem paths into UI link authorities."""

    def value(item: Any) -> Any:
        if isinstance(item, dict):
            return _public_record(item)
        if isinstance(item, list):
            return [value(child) for child in item]
        return item

    return {
        key: value(item)
        for key, item in payload.items()
        if not key.endswith(("_path", "_paths")) and key not in {"preview_rows", "input_rows"}
    }


def _detail(
    repository: AuditRepository, session: Session, catalog: AuditCatalog, reference: AuditReference,
    thread_id: int | None,
) -> AuditDetail:
    summary = _summary(catalog, reference)
    detail = AuditDetail(summary=summary)
    artifact_record = _artifact_record(catalog)
    inputs = _input_references(catalog, reference, artifact_record)
    repository.load_summaries(session, catalog, (ref for ref, _ in inputs))
    for ref, role in inputs:
        row = catalog.summaries.get((ref.kind, ref.id))
        detail.inputs.append(AuditInput(reference=ref, title=row.title if row is not None else ref.key, role=role))

    task = catalog.task
    if task:
        detail.submitted_parameters = (
            _public_record(task.submitted_parameters) if task.submitted_parameters is not None else None
        )
        detail.effective_parameters = _public_record(task.request_payload)
        detail.evidence = _public_record(task.result_payload or {})
        detail.evidence["task_status"] = task.status.value
        if task.error_summary:
            detail.evidence["error"] = task.error_summary

    row = catalog.subject
    if isinstance(row, DatasetRow):
        derivation = catalog.dataset_derivation
        if derivation:
            detail.submitted_parameters = derivation.parameters_payload
            detail.effective_parameters = None
            detail.evidence["operation"] = derivation.operation_name
        elif catalog.dataset_import:
            detail.evidence.update(source_file=catalog.dataset_import.original_file_name, sheet=row.sheet_name)
        for artifact in catalog.dataset_artifacts:
            for key in ("cleaning_report", "tokenization_report"):
                if key in artifact.metadata_payload:
                    detail.evidence[key] = _public_record(artifact.metadata_payload[key])
    elif isinstance(row, TrainedModelRow):
        detail.selected_parameters = row.metadata_payload.get("best_params") or None
        detail.evidence["model"] = _public_record(row.metadata_payload)
        if catalog.evaluation:
            detail.evidence["evaluation"] = _public_record(catalog.evaluation.result_payload or {})
            detail.evidence["evaluation_status"] = catalog.evaluation.status.value
    elif isinstance(row, ArtifactRow):
        if artifact_record:
            detail.submitted_parameters = artifact_record.origin.submitted_parameters
            detail.effective_parameters = artifact_record.effective_parameters
        detail.evidence.update(_public_record(row.metadata_payload))

    detail.files = [
        AuditFile(artifact_id=file.id, title=file.title, available=file.ready_to_open and Path(file.absolute_path).is_file())
        for file in catalog.files
    ]
    preferred = thread_id or summary.thread_id
    explanations = repository.explanations(session, reference.kind, reference.id)
    explanations.sort(key=lambda item: (item.thread_id == preferred, item.created_at, item.id), reverse=True)
    detail.explanations = [
        AuditExplanation(
            id=item.id,
            text=item.text,
            thread_id=item.thread_id,
            created_at=_utc(item.created_at),
            evidence=[AuditReference.model_validate(ref) for ref in item.evidence],
        )
        for item in explanations
    ]
    return detail


class AuditQueryService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._repository = AuditRepository()

    def list_outputs(
        self,
        scope: AuditScope,
        *,
        category: str = "",
        search: str = "",
        limit: int = 50,
        task_id: int | None = None,
        offset: int = 0,
    ) -> list[AuditSummary]:
        if not scope.all_threads and scope.thread_id is None:
            return []
        with self._session_factory() as session:
            return self._list(
                session, scope, category=category, search=search, limit=limit, task_id=task_id, offset=offset
            )

    def _list(
        self, session: Session, scope: AuditScope, *, category: str, search: str, limit: int,
        task_id: int | None, offset: int,
    ) -> list[AuditSummary]:
        rows = self._repository.list_summaries(
            session, scope.thread_id, scope, category=category, search=search, task_id=task_id, limit=limit, offset=offset
        )
        catalog = self._repository.catalog(session, details=False, summary_rows=rows)
        return [
            _summary(catalog, AuditReference(kind=row.kind, id=row.object_id), membership=row.membership)
            for row in rows
        ]

    def get_detail(self, reference: AuditReference, *, thread_id: int | None = None) -> AuditDetail:
        with self._session_factory() as session:
            catalog = self._repository.catalog(session, reference=reference)
            return _detail(self._repository, session, catalog, reference, thread_id)


class AuditExplanationService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._repository = AuditRepository()

    def explain(
        self,
        reference: AuditReference,
        *,
        text: str,
        evidence: list[AuditReference],
        thread_id: int,
        tool_call_message_id: int | None,
    ) -> int:
        text = TypeAdapter(ExplanationText).validate_python(text)
        if not evidence:
            raise ValidationError("An interpretation must reference its recorded evidence.")
        with self._session_factory() as session:
            if not self._repository.thread_exists(session, thread_id):
                raise NotFoundError("The authoring conversation no longer exists.")
            catalog = self._repository.catalog(session, reference=reference)
            target = _require_audit_row(catalog, reference)
            references = self._repository.thread_references(session, thread_id)
            if (
                not _directly_associated(reference, target.thread_id, thread_id, references)
                and ("task", target.task_id) not in references
            ):
                raise ValidationError(f"'{reference.key}' is not associated with this conversation.")
            if target.status in {MLTaskStatus.PENDING, MLTaskStatus.RUNNING}:
                raise ValidationError("Wait for this task to finish before interpreting its result.")
            # A reused model grants access to its recorded supporting evidence, not
            # to unrelated objects that happen to share its original conversation.
            allowed = {
                reference,
                *(ref for ref, _ in _input_references(catalog, reference, _artifact_record(catalog))),
                *(AuditReference(kind="artifact", id=file.id) for file in catalog.files),
            }
            if target.task_id:
                allowed.add(AuditReference(kind="task", id=target.task_id))
            self._repository.load_summaries(session, catalog, evidence)
            for ref in evidence:
                item = _require_audit_row(catalog, ref)
                if ref not in allowed and not _directly_associated(ref, item.thread_id, thread_id, references):
                    raise ValidationError(f"'{ref.key}' is not recorded supporting evidence for this conversation.")
            row = self._repository.append_explanation(
                session,
                AuditExplanationRow(
                    object_kind=reference.kind,
                    object_id=reference.id,
                    thread_id=thread_id,
                    tool_call_message_id=tool_call_message_id,
                    text=text,
                    evidence=[item.model_dump(mode="json") for item in evidence],
                ),
            )
            session.commit()
            return row.id
