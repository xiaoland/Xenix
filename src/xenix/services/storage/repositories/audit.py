"""Read audit relationships and append annotations without rewriting domain facts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, and_, case, cast, exists, func, literal, or_, union_all
from sqlalchemy.engine import Row
from sqlmodel import Session, col, select

from ..models import (
    ArtifactDerivationRow,
    ArtifactKind,
    ArtifactRow,
    AuditExplanationRow,
    ConversationMessageKind,
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
    MLTaskType,
    TrainedModelRow,
)
from .datasets import DatasetRepository

if TYPE_CHECKING:
    from ...audit_contracts import AuditReference, AuditScope


_OUTPUT_CATEGORIES = {
    "dataset": {"dataset", "application"},
    "model": {"model"},
    "artifact": {"artifact", "chart", "report"},
}
_OBJECT_TABLES = {"dataset": DatasetRow, "model": TrainedModelRow, "artifact": ArtifactRow, "task": MLTaskRow}
_SQLITE_MAX_INTEGER = (1 << 63) - 1


@dataclass
class AuditCatalog:
    summaries: dict[tuple[str, int], Row] = field(default_factory=dict)
    subject: DatasetRow | TrainedModelRow | ArtifactRow | MLTaskRow | None = None
    task: MLTaskRow | None = None
    evaluation: MLTaskRow | None = None
    dataset_derivation: DatasetDerivationRow | None = None
    dataset_import: DatasetImportRow | None = None
    edges: list[DatasetDerivationInputRow] = field(default_factory=list)
    artifact_derivation: ArtifactDerivationRow | None = None
    dataset_artifacts: list[Row] = field(default_factory=list)
    files: list[Row] = field(default_factory=list)


def _utc_key(value: str) -> str:
    value_at = datetime.fromisoformat(value)
    if value_at.tzinfo is None:
        value_at = value_at.replace(tzinfo=timezone.utc)
    return value_at.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _audit_artifact():
    return ~exists().where(KnowledgeDocumentRow.source_artifact_id == ArtifactRow.id)


def _dataset_artifact_id():
    # Keep Python's numeric ID equality without SQLite coercing string IDs.
    metadata = col(ArtifactRow.metadata_payload)
    return case((
        func.json_type(metadata, "$.dataset_id").in_(("integer", "real", "true")),
        func.json_extract(metadata, "$.dataset_id"),
    ))


def _represented_artifact():
    task_id = col(MLTaskArtifactRow.ml_task_id)
    kind = col(ArtifactRow.kind)
    return or_(
        and_(kind == ArtifactKind.DATASET, exists().where(DatasetRow.id == _dataset_artifact_id())),
        exists().where(
            col(MLTaskArtifactRow.artifact_id) == ArtifactRow.id,
            or_(
                and_(kind == ArtifactKind.MODEL, exists().where(TrainedModelRow.ml_task_id == task_id)),
                and_(
                    or_(
                        kind.in_((ArtifactKind.DATASET, ArtifactKind.PREDICTION)),
                        func.json_extract(ArtifactRow.metadata_payload, "$.ml_task_artifact_kind") == "export_file",
                    ),
                    exists().where(DatasetRow.ml_task_id == task_id),
                ),
            ),
        ),
    )


def _model_title_field(path: str):
    metadata = col(TrainedModelRow.metadata_payload)
    return case((func.json_type(metadata, path) == "text", func.nullif(func.json_extract(metadata, path), "")))


def _id_values(ids: Iterable[int]):
    # A conversation can accumulate more handles than SQLite admits bind parameters.
    return select(func.json_each(json.dumps(list(ids))).table_valued("value").c.value)


def _summary_select(kind: str):
    table = _OBJECT_TABLES[kind]
    object_id = col(table.id)
    category = literal(kind)
    origin = literal(None)
    explanation = literal(None)
    if kind == "task":
        task_id = object_id
        title = cast(MLTaskRow.task_type, String)
    elif kind == "dataset":
        task_id = col(DatasetRow.ml_task_id)
        title = col(DatasetRow.name)
        category = case((col(MLTaskRow.task_type) == MLTaskType.APPLY, "application"), else_="dataset")
        origin = col(DatasetDerivationRow.origin_thread_id)
        explanation = col(DatasetDerivationRow.agent_explanation)
    elif kind == "model":
        task_id = col(TrainedModelRow.ml_task_id)
        title = func.coalesce(
            _model_title_field("$.run_name"), _model_title_field("$.display_name"), TrainedModelRow.model_key,
        )
    else:
        # The former full table scan picked the first link in SQLite rowid order.
        task_id = (
            select(MLTaskArtifactRow.ml_task_id)
            .where(MLTaskArtifactRow.artifact_id == object_id)
            .order_by(col(MLTaskArtifactRow.id))
            .limit(1)
            .correlate(ArtifactRow)
            .scalar_subquery()
        )
        title = col(ArtifactRow.title)
        artifact_kind = col(ArtifactRow.kind)
        category = case(
            (artifact_kind == ArtifactKind.IMAGE, "chart"),
            (artifact_kind.in_((ArtifactKind.REPORT, ArtifactKind.METRICS)), "report"),
            else_="artifact",
        )
        payload = col(ArtifactDerivationRow.payload)
        origin = cast(func.json_extract(payload, "$.origin.thread_id"), Integer)
        explanation = func.json_extract(payload, "$.origin.explanation")

    thread_id = case(
        (col(MLTaskRow.id).is_not(None), func.coalesce(func.nullif(origin, 0), MLTaskRow.origin_thread_id)),
        else_=origin,
    )
    rationale = case(
        (col(MLTaskRow.id).is_not(None), func.coalesce(func.nullif(explanation, ""), MLTaskRow.agent_explanation)),
        else_=explanation,
    )
    statement = select(
        object_id.label("object_id"),
        title.label("title"),
        literal(kind).label("kind"),
        col(table.created_at).label("created_at"),
        task_id.label("task_id"),
        category.label("category"),
        thread_id.label("thread_id"),
        rationale.label("rationale"),
        col(MLTaskRow.status).label("status"),
        col(ConversationThreadRow.title).label("thread_title"),
        col(ConversationThreadRow.id).is_not(None).label("thread_available"),
        exists().where(AuditExplanationRow.object_kind == kind, AuditExplanationRow.object_id == object_id)
        .label("interpretation_available"),
    ).select_from(table)
    if kind == "dataset":
        statement = statement.outerjoin(DatasetDerivationRow, col(DatasetDerivationRow.dataset_id) == object_id)
    if kind == "artifact":
        statement = statement.outerjoin(ArtifactDerivationRow, col(ArtifactDerivationRow.artifact_id) == object_id)
        statement = statement.where(_audit_artifact())
    if kind != "task":
        statement = statement.outerjoin(MLTaskRow, col(MLTaskRow.id) == task_id)
    return statement.outerjoin(ConversationThreadRow, col(ConversationThreadRow.id) == thread_id)


class AuditRepository:
    def list_summaries(
        self,
        session: Session,
        thread_id: int | None,
        scope: AuditScope,
        *,
        category: str,
        search: str,
        task_id: int | None,
        limit: int,
        offset: int,
    ) -> list[Row]:
        if (not scope.all_threads and scope.thread_id is None) or offset > _SQLITE_MAX_INTEGER:
            return []
        if task_id is not None and not -_SQLITE_MAX_INTEGER - 1 <= task_id <= _SQLITE_MAX_INTEGER:
            return []
        references = self.thread_references(session, thread_id) if not scope.all_threads and thread_id else set()
        referenced_tasks = _id_values(object_id for kind, object_id in references if kind == "task")
        statements = []
        for kind, categories in _OUTPUT_CATEGORIES.items():
            if category and category not in categories:
                continue
            statement = _summary_select(kind)
            columns = statement.selected_columns
            if kind == "artifact":
                statement = statement.where(~_represented_artifact())
            if category and len(categories) > 1:
                statement = statement.where(columns.category == category)
            if task_id is not None:
                statement = statement.where(columns.task_id == task_id)
            membership = literal("generated")
            if not scope.all_threads:
                generated = columns.thread_id == scope.thread_id
                referenced_objects = _id_values(object_id for ref_kind, object_id in references if ref_kind == kind)
                statement = statement.where(or_(
                    generated,
                    columns.object_id.in_(referenced_objects),
                    columns.task_id.in_(referenced_tasks),
                ))
                membership = case((generated, "generated"), else_="referenced")
            key = literal(f"{kind}:") + cast(columns.object_id, String)
            statements.append(statement.add_columns(key.label("ref_key"), membership.label("membership")))
        if not statements:
            return []

        # Keep Unicode casefolding and full timestamp precision when filtering
        # and paginating older databases whose datetime text may vary in format.
        connection = session.connection().connection.driver_connection
        connection.create_function("xenix_audit_utc", 1, _utc_key, deterministic=True)
        outputs = union_all(*statements).subquery()
        statement = select(*outputs.c).order_by(func.xenix_audit_utc(outputs.c.created_at).desc(), outputs.c.ref_key.desc())
        needle = search.strip().casefold()
        if needle:
            connection.create_function("xenix_audit_casefold", 1, str.casefold, deterministic=True)
            haystack = outputs.c.title + literal(" ") + outputs.c.ref_key
            statement = statement.where(func.instr(func.xenix_audit_casefold(haystack), needle) > 0)
        return list(session.exec(statement.limit(min(max(1, limit), _SQLITE_MAX_INTEGER)).offset(max(0, offset))))

    def catalog(
        self,
        session: Session,
        *,
        details: bool = True,
        reference: AuditReference | None = None,
        summary_rows: Iterable[Row] = (),
    ) -> AuditCatalog:
        catalog = AuditCatalog(summaries={(row.kind, row.object_id): row for row in summary_rows})
        if not details:
            return catalog
        assert reference is not None
        self.load_summaries(session, catalog, (reference,))
        summary = catalog.summaries.get((reference.kind, reference.id))
        if summary is None:
            return catalog

        record = session.get(_OBJECT_TABLES[reference.kind], reference.id)
        catalog.subject = record
        if summary.task_id is not None:
            catalog.task = session.get(MLTaskRow, summary.task_id)
        task_ids = {catalog.task.id} if catalog.task else set()
        artifact_ids: set[int] = set()
        if isinstance(record, DatasetRow):
            datasets = DatasetRepository()
            catalog.dataset_derivation = datasets.get_derivation(session, record.id)
            if catalog.dataset_derivation:
                catalog.edges = datasets.list_derivation_inputs(session, record.id)
            elif record.import_id is not None:
                catalog.dataset_import = session.get(DatasetImportRow, record.import_id)
            catalog.dataset_artifacts = self._dataset_artifacts(session, record.id)
            artifact_ids.update(row.id for row in catalog.dataset_artifacts)
        elif isinstance(record, TrainedModelRow):
            evaluation_id = record.metadata_payload.get("evaluation_ml_task_id")
            if isinstance(evaluation_id, (int, float)):
                catalog.evaluation = session.get(MLTaskRow, evaluation_id)
            if catalog.evaluation:
                task_ids.add(catalog.evaluation.id)
        elif isinstance(record, ArtifactRow):
            catalog.artifact_derivation = session.get(ArtifactDerivationRow, record.id)
            artifact_ids.add(record.id)
        catalog.files = self._evidence_files(session, artifact_ids, task_ids)
        return catalog

    def load_summaries(self, session: Session, catalog: AuditCatalog, references: Iterable[AuditReference]) -> None:
        ids_by_kind: dict[str, set[int]] = {}
        for ref in references:
            if (ref.kind, ref.id) not in catalog.summaries:
                ids_by_kind.setdefault(ref.kind, set()).add(ref.id)
        for kind, ids in ids_by_kind.items():
            statement = _summary_select(kind)
            rows = session.exec(statement.where(statement.selected_columns.object_id.in_(_id_values(ids))))
            catalog.summaries.update({(kind, row.object_id): row for row in rows})

    def _dataset_artifacts(self, session: Session, dataset_id: int) -> list[Row]:
        statement = (
            select(ArtifactRow.id, ArtifactRow.metadata_payload)
            .where(_audit_artifact(), ArtifactRow.kind == ArtifactKind.DATASET, _dataset_artifact_id() == dataset_id)
            .order_by(col(ArtifactRow.id))
        )
        return list(session.exec(statement))

    def _evidence_files(self, session: Session, artifact_ids: set[int], task_ids: set[int]) -> list[Row]:
        if not artifact_ids and not task_ids:
            return []
        task_files = select(MLTaskArtifactRow.artifact_id).where(col(MLTaskArtifactRow.ml_task_id).in_(task_ids))
        statement = (
            select(ArtifactRow.id, ArtifactRow.title, ArtifactRow.absolute_path, ArtifactRow.ready_to_open)
            .where(_audit_artifact(), or_(col(ArtifactRow.id).in_(artifact_ids), col(ArtifactRow.id).in_(task_files)))
            .order_by(col(ArtifactRow.id))
        )
        return list(session.exec(statement))

    def explanations(self, session: Session, kind: str, object_id: int) -> list[AuditExplanationRow]:
        return list(session.exec(select(AuditExplanationRow).where(
            AuditExplanationRow.object_kind == kind, AuditExplanationRow.object_id == object_id,
        )))

    def thread_exists(self, session: Session, thread_id: int) -> bool:
        return session.exec(select(ConversationThreadRow.id).where(ConversationThreadRow.id == thread_id)).first() is not None

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

        table = ConversationMessageRow
        messages = session.exec(
            select(table.kind, table.tool_id, table.content_payload, table.arguments_payload, table.value_payload).where(
                table.thread_id == thread_id,
                col(table.kind).in_((
                    ConversationMessageKind.USER, ConversationMessageKind.TOOL_CALL, ConversationMessageKind.TOOL_RESULT,
                )),
            )
        )
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
                    dataset_id = session.exec(select(DatasetColumnBindingRow.dataset_id).where(
                        DatasetColumnBindingRow.id == binding_id,
                    )).first()
                    add("dataset", dataset_id)
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
