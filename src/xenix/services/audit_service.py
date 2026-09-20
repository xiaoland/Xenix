"""Service-owned, read-only audit projection and separately owned Agent annotations."""

from __future__ import annotations

from pathlib import Path
from datetime import timezone
from typing import Any

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
from .storage.models import AuditExplanationRow
from .storage.repositories.audit import AuditCatalog, AuditRepository


class AuditQueryService:
    def __init__(self, session_factory) -> None:
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
            catalog = self._repository.catalog(session, scope.thread_id, details=False)
            return self._list(
                catalog, scope, category=category, search=search, limit=limit, task_id=task_id, offset=offset
            )

    def _list(
        self,
        catalog: AuditCatalog,
        scope: AuditScope,
        *,
        category: str = "",
        search: str = "",
        limit: int = 50,
        task_id: int | None = None,
        offset: int = 0,
    ) -> list[AuditSummary]:
        summaries = []
        for kind, rows in (("dataset", catalog.datasets), ("model", catalog.models), ("artifact", catalog.artifacts)):
            for object_id in rows:
                summary = self._summary(catalog, AuditReference(kind=kind, id=object_id))
                if kind == "artifact" and self._represented_file(catalog, object_id):
                    continue
                generated = scope.thread_id is not None and summary.thread_id == scope.thread_id
                referenced = (kind, object_id) in catalog.references or ("task", summary.task_id) in catalog.references
                if not scope.all_threads and not (generated or referenced):
                    continue
                if category and summary.category != category:
                    continue
                if task_id is not None and summary.task_id != task_id:
                    continue
                if search.strip().casefold() not in f"{summary.title} {summary.reference.key}".casefold():
                    continue
                summary.membership = "generated" if generated or scope.all_threads else "referenced"
                summaries.append(summary)
        summaries.sort(key=lambda item: (item.created_at, item.reference.key), reverse=True)
        return summaries[max(0, offset) : max(0, offset) + max(1, limit)]

    @staticmethod
    def _represented_file(catalog: AuditCatalog, artifact_id: int) -> bool:
        artifact = catalog.artifacts[artifact_id]
        if artifact.kind.value == "dataset" and artifact.metadata_payload.get("dataset_id") in catalog.datasets:
            return True
        for link in catalog.task_artifacts:
            if link.artifact_id == artifact_id:
                if artifact.kind.value == "model" and any(
                    model.ml_task_id == link.ml_task_id for model in catalog.models.values()
                ):
                    return True
                if any(dataset.ml_task_id == link.ml_task_id for dataset in catalog.datasets.values()) and (
                    artifact.kind.value in {"dataset", "prediction"}
                    or artifact.metadata_payload.get("ml_task_artifact_kind") == "export_file"
                ):
                    return True
        return False

    def _summary(self, catalog: AuditCatalog, reference: AuditReference) -> AuditSummary:
        kind, object_id = reference.kind, reference.id
        rows = {
            "dataset": catalog.datasets,
            "model": catalog.models,
            "artifact": catalog.artifacts,
            "task": catalog.tasks,
        }[kind]
        row = rows.get(object_id)
        if row is None:
            raise NotFoundError(f"Audit object '{reference.key}' was not found.")
        task_id = getattr(row, "ml_task_id", None)
        rationale = None
        thread_id = None
        category = kind
        if kind == "dataset":
            title = row.name
            derivation = catalog.derivations.get(object_id)
            if derivation:
                thread_id, rationale = derivation.origin_thread_id, derivation.agent_explanation
            if task_id and catalog.tasks[task_id].task_type.value == "apply":
                category = "application"
        elif kind == "model":
            title = row.metadata_payload.get("run_name") or row.metadata_payload.get("display_name") or row.model_key
        elif kind == "task":
            title, task_id = row.task_type.value, row.id
        else:
            title = row.title
            category = (
                "chart"
                if row.kind.value == "image"
                else "report"
                if row.kind.value in {"report", "metrics"}
                else "artifact"
            )
            link = next((link for link in catalog.task_artifacts if link.artifact_id == object_id), None)
            task_id = link.ml_task_id if link else None
            derivation = catalog.artifact_derivations.get(object_id)
            if derivation:
                origin = ArtifactDerivation.model_validate(derivation.payload).origin
                thread_id, rationale = origin.thread_id, origin.explanation
        task = catalog.tasks.get(task_id)
        if task:
            thread_id = thread_id or task.origin_thread_id
            rationale = rationale or task.agent_explanation
        thread = catalog.threads.get(thread_id)
        explanations = [
            item for item in catalog.explanations if item.object_kind == kind and item.object_id == object_id
        ]
        return AuditSummary(
            reference=reference,
            title=title,
            category=category,
            created_at=row.created_at.replace(tzinfo=timezone.utc) if row.created_at.tzinfo is None else row.created_at,
            thread_id=thread_id,
            thread_title=thread.title if thread else None,
            thread_available=thread is not None,
            task_id=task_id,
            status=task.status.value if task else None,
            rationale=rationale,
            interpretation_available=bool(explanations),
        )

    def get_detail(self, reference: AuditReference, *, thread_id: int | None = None) -> AuditDetail:
        with self._session_factory() as session:
            catalog = self._repository.catalog(session, thread_id)
            return self._detail(catalog, reference, thread_id)

    def _detail(self, catalog: AuditCatalog, reference: AuditReference, thread_id: int | None) -> AuditDetail:
        summary = self._summary(catalog, reference)
        detail = AuditDetail(summary=summary)
        file_ids: set[int] = set()
        task = catalog.tasks.get(summary.task_id)

        def add_input(kind: str, object_id: int | None, role: str = "") -> None:
            if not object_id:
                return
            ref = AuditReference(kind=kind, id=object_id)
            if ref == reference or any(item.reference == ref and item.role == role for item in detail.inputs):
                return
            try:
                title = self._summary(catalog, ref).title
            except NotFoundError:
                title = ref.key
            detail.inputs.append(AuditInput(reference=ref, title=title, role=role))

        if task:
            detail.submitted_parameters = (
                self._public_record(task.submitted_parameters) if task.submitted_parameters is not None else None
            )
            detail.effective_parameters = self._public_record(task.request_payload)
            detail.evidence = self._public_record(task.result_payload or {})
            detail.evidence["task_status"] = task.status.value
            if task.error_summary:
                detail.evidence["error"] = task.error_summary
            for link in catalog.task_artifacts:
                if link.ml_task_id == task.id and link.artifact_id:
                    file_ids.add(link.artifact_id)
            if task.task_type.value == "apply":
                payload = task.result_payload or {}
                for source in payload.get("source_dataset_ids", []):
                    add_input("dataset", source, "apply input")
                for source in payload.get("source_artifact_ids", []):
                    add_input("artifact", source, "apply input")
                add_input("model", (task.request_payload.get("apply_model") or {}).get("trained_model_id"), "model")
            else:
                add_input("dataset", task.dataset_id, "training input")
        if reference.kind == "dataset":
            row = catalog.datasets[reference.id]
            derivation = catalog.derivations.get(row.id)
            if derivation:
                detail.submitted_parameters = derivation.parameters_payload
                detail.effective_parameters = None
                detail.evidence["operation"] = derivation.operation_name
                for edge in sorted(catalog.edges, key=lambda item: item.input_position):
                    if edge.derivation_dataset_id == row.id:
                        add_input("dataset", edge.input_dataset_id, edge.alias or "input")
            elif row.import_id in catalog.imports:
                imported = catalog.imports[row.import_id]
                detail.evidence.update(source_file=imported.original_file_name, sheet=row.sheet_name)
            elif row.derived_from_dataset_id:
                add_input("dataset", row.derived_from_dataset_id, "recorded parent")
            for artifact in sorted(catalog.artifacts.values(), key=lambda item: item.id):
                if artifact.metadata_payload.get("dataset_id") == row.id and artifact.kind.value == "dataset":
                    file_ids.add(artifact.id)
                    for key in ("cleaning_report", "tokenization_report"):
                        if key in artifact.metadata_payload:
                            detail.evidence[key] = self._public_record(artifact.metadata_payload[key])

        elif reference.kind == "model":
            model = catalog.models[reference.id]
            metadata = model.metadata_payload
            detail.selected_parameters = metadata.get("best_params") or None
            detail.evidence["model"] = self._public_record(metadata)
            evaluation_id = metadata.get("evaluation_ml_task_id")
            evaluation = catalog.tasks.get(evaluation_id)
            if evaluation:
                add_input("task", evaluation_id, "evaluation")
                detail.evidence["evaluation"] = self._public_record(evaluation.result_payload or {})
                detail.evidence["evaluation_status"] = evaluation.status.value
                for link in catalog.task_artifacts:
                    if link.ml_task_id == evaluation_id and link.artifact_id:
                        file_ids.add(link.artifact_id)
        elif reference.kind == "artifact":
            artifact = catalog.artifacts[reference.id]
            file_ids.add(artifact.id)
            derivation = catalog.artifact_derivations.get(artifact.id)
            if derivation:
                record = ArtifactDerivation.model_validate(derivation.payload)
                detail.submitted_parameters = record.origin.submitted_parameters
                detail.effective_parameters = record.effective_parameters
                for input_ref in record.inputs:
                    add_input(input_ref.kind, input_ref.id)
            else:
                add_input("dataset", artifact.metadata_payload.get("dataset_id"))
            detail.evidence.update(self._public_record(artifact.metadata_payload))
        for object_id in sorted(file_ids):
            artifact = catalog.artifacts.get(object_id)
            if artifact:
                detail.files.append(
                    AuditFile(
                        artifact_id=object_id,
                        title=artifact.title,
                        available=artifact.ready_to_open and Path(artifact.absolute_path).is_file(),
                    )
                )
        explanations = [
            item
            for item in catalog.explanations
            if item.object_kind == reference.kind and item.object_id == reference.id
        ]
        preferred = thread_id or summary.thread_id
        explanations.sort(key=lambda item: (item.thread_id == preferred, item.created_at, item.id), reverse=True)
        detail.explanations = [
            AuditExplanation(
                id=item.id,
                text=item.text,
                thread_id=item.thread_id,
                created_at=item.created_at.replace(tzinfo=timezone.utc)
                if item.created_at.tzinfo is None
                else item.created_at,
                evidence=[AuditReference.model_validate(ref) for ref in item.evidence],
            )
            for item in explanations
        ]
        return detail

    @classmethod
    def _public_record(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Do not turn internal filesystem paths into UI link authorities."""

        def value(item: Any) -> Any:
            if isinstance(item, dict):
                return cls._public_record(item)
            if isinstance(item, list):
                return [value(child) for child in item]
            return item

        return {
            key: value(item)
            for key, item in payload.items()
            if not key.endswith(("_path", "_paths")) and key not in {"preview_rows", "input_rows"}
        }


class AuditExplanationService:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self._repository = AuditRepository()
        self._query = AuditQueryService(session_factory)

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
            catalog = self._repository.catalog(session, thread_id)
            if thread_id not in catalog.threads:
                raise NotFoundError("The authoring conversation no longer exists.")
            summary = self._query._summary(catalog, reference)
            if (
                summary.thread_id != thread_id
                and (reference.kind, reference.id) not in catalog.references
                and ("task", summary.task_id) not in catalog.references
            ):
                raise ValidationError(f"'{reference.key}' is not associated with this conversation.")
            if summary.status in {"pending", "running"}:
                raise ValidationError("Wait for this task to finish before interpreting its result.")
            # A reused model grants access to its recorded supporting evidence, not
            # to unrelated objects that happen to share its original conversation.
            detail = self._query._detail(catalog, reference, thread_id)
            allowed = {
                reference,
                *(item.reference for item in detail.inputs),
                *(AuditReference(kind="artifact", id=item.artifact_id) for item in detail.files),
            }
            if summary.task_id:
                allowed.add(AuditReference(kind="task", id=summary.task_id))
            for ref in evidence:
                item = self._query._summary(catalog, ref)
                if ref not in allowed and item.thread_id != thread_id and (ref.kind, ref.id) not in catalog.references:
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
