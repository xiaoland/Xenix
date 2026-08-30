from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import AgentHarnessService, DatasetAttachmentInput, SubmitUserTurnInput
from xenix.services.agent.tools import AgentToolRegistry
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.llm import (
    AgentToolRegistry as LLMToolRegistry,
    LLMConversationService,
    ProviderResponse,
    ProviderToolCall,
    ToolExecutionContext,
)
from xenix.services.preprocessing_worker import InlinePreprocessingWorkerRunner
from xenix.services.storage import StorageBootstrapService


class _TransformThenAnswerProvider:
    def __init__(self, *, left_dataset_id: str, right_dataset_id: str) -> None:
        self._left_dataset_id = left_dataset_id
        self._right_dataset_id = right_dataset_id
        self.calls = 0

    def complete(self, _messages, _tools):
        self.calls += 1
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="provider-transform-1",
                        tool_name="data.transform",
                        provider_name="data_transform",
                        arguments={
                            "bindings": [
                                {"alias": "orders", "dataset_id": self._left_dataset_id},
                                {"alias": "regions", "dataset_id": self._right_dataset_id},
                            ],
                            "sql": (
                                "SELECT orders.order_id, orders.amount, regions.region "
                                "FROM orders JOIN regions USING (region_id)"
                            ),
                            "name": "Orders with regions",
                            "explanation": (
                                "Adds the region label needed to compare order values by market."
                            ),
                        },
                    )
                ]
            )
        return ProviderResponse(
            assistant_content_blocks=[{"type": "text", "text": "Done."}]
        )


def test_multi_input_transform_records_and_projects_dataset_audit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    datasets = DatasetService(storage.session_factory, paths)
    artifacts = ArtifactService(storage.session_factory)
    inline_worker = InlinePreprocessingWorkerRunner()

    orders_path = tmp_path / "orders.csv"
    orders_path.write_text(
        "order_id,region_id,amount\n1,10,25\n2,20,40\n",
        encoding="utf-8",
    )
    regions_path = tmp_path / "regions.csv"
    regions_path.write_text(
        "region_id,region\n10,North\n20,South\n",
        encoding="utf-8",
    )
    orders = datasets.register_dataset(
        RegisterDatasetInput(source_path=str(orders_path.resolve()), name="Orders")
    )
    regions = datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(regions_path.resolve()),
            project_id=orders.project_id,
            name="Regions",
        )
    )

    concrete_tools = AgentToolRegistry(
        paths=paths,
        dataset_service=datasets,
        data_cleaning_service=Mock(),
        data_transform_service=DataQueryTransformService(
            paths,
            worker_runner=inline_worker,
        ),
        ml_service=Mock(),
        artifact_service=artifacts,
        preprocessing_worker_runner=inline_worker,
    )
    llm_tools = LLMToolRegistry()
    concrete_tools.register_with_llm(llm_tools)
    provider = _TransformThenAnswerProvider(
        left_dataset_id=orders.id,
        right_dataset_id=regions.id,
    )
    harness = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=storage.session_factory,
            tool_registry=llm_tools,
        ),
        tool_presentation_registry=concrete_tools,
        provider=provider,
        dataset_service=datasets,
    )

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(
            text="Compare orders by market.",
            dataset_attachments=[
                DatasetAttachmentInput(
                    dataset_id=orders.id,
                    name=orders.name,
                    row_count=2,
                    column_count=3,
                ),
                DatasetAttachmentInput(
                    dataset_id=regions.id,
                    name=regions.name,
                    row_count=2,
                    column_count=2,
                ),
            ],
        )
    )

    tool_call = next(message for message in snapshot.messages if message.kind.value == "tool_call")
    audits = datasets.resolve_dataset_audits_for_tool_call(tool_call.id)
    assert len(audits) == 1
    audit = audits[0]
    assert audit.operation_name == "data.transform"
    assert audit.generation == 1
    assert audit.agent_explanation == (
        "Adds the region label needed to compare order values by market."
    )
    assert [(item.dataset_id, item.alias) for item in audit.inputs] == [
        (orders.id, "orders"),
        (regions.id, "regions"),
    ]
    assert audit.parameters_payload == {
        "sql": (
            "SELECT orders.order_id, orders.amount, regions.region "
            "FROM orders JOIN regions USING (region_id)"
        ),
        "column_reference": "names",
        "name": "Orders with regions",
    }

    generated = datasets.get_dataset(audit.dataset_id)
    assert generated.derived_from_dataset_id is None
    assert generated.id not in {row.id for row in datasets.list_source_datasets()}
    assert generated.id in {row.id for row in datasets.list_generated_datasets()}
    assert generated.id in {row.id for row in datasets.list_derived_datasets(orders.id)}
    assert generated.id in {row.id for row in datasets.list_derived_datasets(regions.id)}

    tool_event = next(
        event
        for event in harness.project_chatbot_events(snapshot)
        if event.tool_call_id == tool_call.id
    )
    assert isinstance(tool_event.tool_result_value, str)
    audit_block = next(
        block for block in tool_event.detail_blocks if block.get("type") == "dataset_audit"
    )
    assert audit_block["dataset_id"] == generated.id
    assert audit_block["generation"] == 1
    assert audit_block["agent_explanation"] == audit.agent_explanation

    session_audits = harness.resolve_session_dataset_audits(snapshot.thread.id)
    assert [audit.dataset_id for audit in session_audits] == [generated.id]

    concrete_tools.execute(
        "data.transform",
        {
            "dataset_id": generated.id,
            "sql": "SELECT * FROM input WHERE amount >= 30",
            "name": "High-value regional orders",
        },
        ToolExecutionContext(
            thread_id=snapshot.thread.id,
            tool_call_message_id="tool-call-generation-2",
            dataset_ids=(generated.id,),
        ),
    )
    second_audit = datasets.resolve_dataset_audits_for_tool_call(
        "tool-call-generation-2"
    )[0]
    assert second_audit.generation == 2
    assert second_audit.inputs[0].dataset_id == generated.id
    assert datasets.get_dataset(second_audit.dataset_id).derived_from_dataset_id == generated.id
