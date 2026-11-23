from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event
from sqlmodel import select

from xenix.exceptions import ValidationError
from xenix.services import audit_service
from xenix.services.artifact_service import ArtifactService, RegisterArtifactInput
from xenix.services.audit_contracts import ArtifactDerivation, AuditReference, AuditScope, ExecutionOrigin
from xenix.services.audit_service import AuditExplanationService, AuditQueryService
from xenix.services.job_service import JobQueryService
from xenix.services.storage.models import (
    ArtifactKind,
    ArtifactRow,
    AuditExplanationRow,
    ConversationThreadRow,
    ConversationMessageRow,
    ConversationMessageKind,
    DatasetRow,
    DatasetSourceFormat,
    MLTaskArtifactKind,
    MLTaskArtifactRow,
    MLTaskRow,
    MLTaskStatus,
    MLTaskType,
    ProjectRow,
    TrainedModelRow,
)


@pytest.fixture
def recorded_model(storage):
    with storage.session_factory() as session:
        session.add_all(
            [
                ProjectRow(id=101, name="Sales"),
                ConversationThreadRow(id=201, title="Demand"),
                ConversationThreadRow(id=202, title="Other"),
            ]
        )
        session.commit()
        session.add(
            DatasetRow(
                id=102, project_id=101, name="Sales", source_path="sales.csv", source_format=DatasetSourceFormat.CSV
            )
        )
        session.commit()
        session.add_all(
            [
                MLTaskRow(
                    id=103,
                    project_id=101,
                    dataset_id=102,
                    task_type=MLTaskType.FIT,
                    status=MLTaskStatus.SUCCEEDED,
                    origin_thread_id=201,
                    agent_explanation="Use a simple baseline to forecast demand.",
                    submitted_parameters={"test_size": 0.2},
                    request_payload={"seed": 42, "test_size": 0.2},
                ),
                MLTaskRow(
                    id=104,
                    project_id=101,
                    dataset_id=102,
                    task_type=MLTaskType.EVALUATE,
                    status=MLTaskStatus.SUCCEEDED,
                    origin_thread_id=201,
                    result_payload={"evaluation": {"mae": 12}, "split_facts": {"test_rows": 20}},
                ),
                MLTaskRow(
                    id=106,
                    project_id=101,
                    dataset_id=102,
                    task_type=MLTaskType.FIT,
                    status=MLTaskStatus.RUNNING,
                    origin_thread_id=202,
                ),
            ]
        )
        session.commit()
        session.add(
            TrainedModelRow(
                id=105,
                dataset_id=102,
                ml_task_id=103,
                model_key="linear_regression",
                artifact_path="model.pkl",
                metadata_payload={"evaluation_ml_task_id": 104, "best_params": {"alpha": 1}},
            )
        )
        session.commit()
    return AuditReference(kind="model", id=105)


def test_scopes_evidence_and_versioned_interpretation(storage, recorded_model):
    query = AuditQueryService(storage.session_factory)
    assert query.list_outputs(AuditScope()) == []
    assert [s.reference for s in query.list_outputs(AuditScope(thread_id=201))] == [recorded_model]
    assert query.list_outputs(AuditScope(thread_id=202)) == []
    jobs = JobQueryService(storage.session_factory)
    assert {j.raw_reference for j in jobs.list_jobs(scope=AuditScope(thread_id=201))} == {103, 104}
    assert jobs.list_jobs(scope=AuditScope()) == []
    detail = query.get_detail(recorded_model)
    assert detail.submitted_parameters == {"test_size": 0.2}
    assert detail.effective_parameters == {"seed": 42, "test_size": 0.2}
    assert detail.selected_parameters == {"alpha": 1}
    assert detail.evidence["evaluation"]["evaluation"]["mae"] == 12
    assert detail.explanations == []
    writer = AuditExplanationService(storage.session_factory)
    for text in [
        "Average error is 12 units on held-out data.",
        "Correction: this test does not establish seasonal accuracy.",
    ]:
        writer.explain(
            recorded_model,
            text=text,
            evidence=[AuditReference(kind="task", id=104)],
            thread_id=201,
            tool_call_message_id=None,
        )
    detail = query.get_detail(recorded_model)
    assert len(detail.explanations) == 2
    assert detail.explanations[0].text.startswith("Correction:")
    assert detail.evidence["evaluation"]["evaluation"]["mae"] == 12
    with pytest.raises(ValidationError, match="associated"):
        writer.explain(
            recorded_model, text="Unrelated", evidence=[recorded_model], thread_id=202, tool_call_message_id=None
        )
    with pytest.raises(ValidationError, match="Wait"):
        writer.explain(
            AuditReference(kind="task", id=106),
            text="Premature conclusion",
            evidence=[AuditReference(kind="task", id=106)],
            thread_id=202,
            tool_call_message_id=None,
        )


def test_artifact_origin_survives_missing_tool_result_and_deleted_conversation(storage, tmp_path):
    with storage.session_factory() as session:
        session.add(ConversationThreadRow(id=201, title="Graph"))
        session.commit()
    path = tmp_path / "chart.svg"
    path.write_text("<svg/>")
    artifact = ArtifactService(storage.session_factory).register_artifact(
        RegisterArtifactInput(
            kind=ArtifactKind.IMAGE,
            title="Demand",
            absolute_path=str(path),
            mime_type="image/svg+xml",
            derivation=ArtifactDerivation(
                operation="analysis.graph",
                origin=ExecutionOrigin(thread_id=201, explanation="Show demand by region."),
                effective_parameters={"mark": "bar"},
            ),
        )
    )
    ref = AuditReference(kind="artifact", id=artifact.id)
    query = AuditQueryService(storage.session_factory)
    assert [item.reference for item in query.list_outputs(AuditScope(thread_id=201))] == [ref]
    AuditExplanationService(storage.session_factory).explain(
        ref,
        text="Compare regions; this is descriptive, not causal.",
        evidence=[ref],
        thread_id=201,
        tool_call_message_id=None,
    )
    with storage.session_factory() as session:
        session.delete(session.get(ConversationThreadRow, 201))
        session.commit()
        assert len(list(session.exec(select(AuditExplanationRow)))) == 1
    [item] = query.list_outputs(AuditScope(all_threads=True))
    assert item.thread_id == 201
    assert not item.thread_available
    assert item.interpretation_available
    path.unlink()
    detail = query.get_detail(ref)
    assert not detail.summary.thread_available
    assert detail.summary.thread_id == 201
    assert detail.explanations[0].text.startswith("Compare")
    assert not detail.files[0].available
    assert detail.effective_parameters == {"mark": "bar"}


def test_reused_model_explanation_is_attributed_to_new_conversation(storage, recorded_model):
    with storage.session_factory() as session:
        session.add(
            ConversationMessageRow(
                id=301,
                thread_id=202,
                sequence_index=0,
                kind=ConversationMessageKind.TOOL_CALL,
                tool_id="audit.inspect",
                arguments_payload={"reference": recorded_model.model_dump()},
            )
        )
        session.commit()
    query = AuditQueryService(storage.session_factory)
    [item] = query.list_outputs(AuditScope(thread_id=202))
    assert item.reference == recorded_model
    assert item.membership == "referenced"
    assert item.thread_id == 201
    AuditExplanationService(storage.session_factory).explain(
        recorded_model,
        text="For this purchasing plan, allow a buffer of 12 units; seasonality is untested.",
        evidence=[AuditReference(kind="task", id=104)],
        thread_id=202,
        tool_call_message_id=None,
    )
    detail = query.get_detail(recorded_model, thread_id=202)
    assert detail.explanations[0].thread_id == 202
    assert detail.summary.thread_id == 201
    assert {
        job.raw_reference for job in JobQueryService(storage.session_factory).list_jobs(scope=AuditScope(thread_id=202))
    } == {106}


def test_list_applies_filters_before_paging_and_keeps_the_reference_key_order(storage, recorded_model, monkeypatch):
    tie = datetime(2025, 1, 2, tzinfo=timezone.utc)
    older = tie - timedelta(days=1)
    with storage.session_factory() as session:
        model = session.get(TrainedModelRow, recorded_model.id)
        model.created_at = tie
        model.metadata_payload = {**model.metadata_payload, "run_name": "", "display_name": "Straße forecast"}
        session.get(DatasetRow, 102).created_at = older - timedelta(days=1)
        session.add(MLTaskRow(
            id=107, project_id=101, dataset_id=102, task_type=MLTaskType.APPLY,
            status=MLTaskStatus.SUCCEEDED, origin_thread_id=201,
        ))
        session.flush()
        session.add(DatasetRow(id=850, project_id=101, name="Predictions", source_path="apply.csv",
                               ml_task_id=107, created_at=tie))
        session.add_all([
            ArtifactRow(id=9, kind=ArtifactKind.REPORT, title="Task report", absolute_path="/report", created_at=tie),
            ArtifactRow(id=10, kind=ArtifactKind.IMAGE, title="Tied chart", absolute_path="/chart", created_at=tie),
            ArtifactRow(id=11, kind=ArtifactKind.MODEL, title="Model file", absolute_path="/model", created_at=tie),
            ArtifactRow(id=12, kind=ArtifactKind.DATASET, title="Dataset file", absolute_path="/dataset",
                        metadata_payload={"dataset_id": 102}, created_at=tie),
            ArtifactRow(id=301, kind=ArtifactKind.IMAGE, title="Straße detail", absolute_path="/old", created_at=older),
            ArtifactRow(id=999, kind=ArtifactKind.IMAGE, title="Latest", absolute_path="/latest",
                        created_at=tie + timedelta(microseconds=1)),
        ])
        session.flush()
        session.add_all([
            MLTaskArtifactRow(id=450, ml_task_id=103, artifact_id=9, artifact_kind=MLTaskArtifactKind.TRAINING_REPORT,
                              absolute_path="/report"),
            MLTaskArtifactRow(id=451, ml_task_id=106, artifact_id=9, artifact_kind=MLTaskArtifactKind.TRAINING_REPORT,
                              absolute_path="/report"),
            MLTaskArtifactRow(id=452, ml_task_id=103, artifact_id=11, artifact_kind=MLTaskArtifactKind.MODEL,
                              absolute_path="/model"),
            ConversationMessageRow(
                id=302, thread_id=202, sequence_index=0, kind=ConversationMessageKind.TOOL_CALL,
                tool_id="model.task", arguments_payload={"ml_task_id": 103},
            ),
        ])
        # Older databases can contain ISO datetime text with an explicit offset.
        session.connection().exec_driver_sql(
            "UPDATE artifact SET created_at = ? WHERE id = 10", ("2025-01-02T01:00:00+01:00",),
        )
        session.commit()

    query = AuditQueryService(storage.session_factory)
    scope = AuditScope(all_threads=True)

    def keys(scope=scope, **kwargs):
        return [item.reference.key for item in query.list_outputs(scope, **kwargs)]

    expected = ["artifact:999", "model:105", "dataset:850", "artifact:9", "artifact:10", "artifact:301", "dataset:102"]
    assert keys() == expected
    assert keys(limit=2) + keys(limit=2, offset=2) + keys(offset=4) == expected
    assert keys(offset=len(expected)) == []
    assert keys(limit=0, offset=-1) == expected[:1]
    assert keys(limit=2**63) == expected
    assert keys(offset=2**63) == []
    assert keys(task_id=2**63) == []
    assert keys(category="application", task_id=107) == ["dataset:850"]
    assert keys(category="report", task_id=103) == ["artifact:9"]
    assert keys(category="report", task_id=106) == []
    assert keys(search="  STRASSE  ", limit=1) == ["model:105"]
    assert keys(search="  STRASSE  ", category="chart", limit=1) == ["artifact:301"]
    assert keys(search="ARTIFACT:301", limit=1) == ["artifact:301"]
    assert keys(search="%", limit=1) == []
    assert keys(AuditScope(thread_id=201)) == ["model:105", "dataset:850", "artifact:9"]
    referenced = query.list_outputs(AuditScope(thread_id=202))
    assert [(item.reference.key, item.membership, item.thread_id) for item in referenced] == [
        ("model:105", "referenced", 201), ("artifact:9", "referenced", 201),
    ]
    assert [file.artifact_id for file in query.get_detail(AuditReference(kind="artifact", id=11)).files] == [9, 11]

    projected, statements = [], []
    original = audit_service._summary

    def project(catalog, reference, **kwargs):
        projected.append(reference.key)
        return original(catalog, reference, **kwargs)

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    monkeypatch.setattr(audit_service, "_summary", project)
    event.listen(storage.engine, "before_cursor_execute", capture)
    try:
        assert keys(limit=1, offset=3) == ["artifact:9"]
    finally:
        event.remove(storage.engine, "before_cursor_execute", capture)
    assert projected == ["artifact:9"]
    [statement] = statements
    assert {"UNION", "LIMIT", "OFFSET"} <= set(statement.split())


def test_public_audit_tools_save_interpretation_with_validated_evidence(storage, recorded_model):
    from xenix.services.agent.audit_tools import register_audit_tools
    from xenix.services.llm.tool_registry import AgentToolRegistry
    from xenix.services.llm.tool_protocol import ToolExecutionContext

    registry = AgentToolRegistry()
    register_audit_tools(registry, storage.session_factory)
    context = ToolExecutionContext(thread_id=201, tool_call_message_id=None)
    result = registry.invoke(
        tool_name="audit.inspect", arguments={"reference": recorded_model.model_dump()}, context=context
    )
    assert result.value["evidence"]["evaluation"]["evaluation"]["mae"] == 12
    saved = registry.invoke(
        tool_name="audit.explain",
        arguments={
            "reference": recorded_model.model_dump(),
            "explanation": "Average held-out error is 12 units. Check whether this buffer is affordable before purchasing.",
            "evidence": [{"kind": "task", "id": 104}],
        },
        context=context,
    )
    assert saved.value["saved"] is True
    with pytest.raises(ValidationError):
        registry.invoke(
            tool_name="audit.explain",
            arguments={
                "reference": recorded_model.model_dump(),
                "explanation": "   ",
                "evidence": [{"kind": "task", "id": 104}],
            },
            context=context,
        )
