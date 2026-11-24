from pathlib import Path

from xenix.services.analysis_graph import AnalysisGraphService, GraphDatasetInput
from xenix.services.audit_contracts import AuditReference, AuditScope
from xenix.services.audit_service import AuditQueryService
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.preprocessing_worker import LocalPreprocessingWorkerRunner


def test_spawned_dataset_registration_preserves_origin_inputs_and_effects(storage, app_paths, tmp_path):
    source = tmp_path / "sales.csv"
    source.write_text("region,sales\nnorth,12\nsouth,15\n")
    datasets = DatasetService(storage.session_factory, app_paths)
    imported = datasets.register_dataset(RegisterDatasetInput(source_path=str(source), name="Sales"))
    result = LocalPreprocessingWorkerRunner().run(
        "data.register_generated_dataset",
        {
            "output_path": str(source),
            "name": "Prepared sales",
            "summary": "Registered",
            "derivation": {
                "operation_name": "data.clean",
                "origin_thread_id": 201,
                "tool_call_message_id": 202,
                "agent_explanation": "Remove duplicate orders before descriptive analysis.",
                "parameters_payload": {"operations": [{"operation": "duplicate.exact_rows"}]},
                "inputs": [{"dataset_id": imported.id, "alias": "sales"}],
            },
            "metadata_payload": {"cleaning_report": {"row_count_before": 2, "row_count_after": 2}},
        },
        paths=app_paths,
    )
    query = AuditQueryService(storage.session_factory)
    ref = AuditReference(kind="dataset", id=result["dataset_id"])
    assert [item.reference for item in query.list_outputs(AuditScope(thread_id=201))] == [ref]
    detail = query.get_detail(ref)
    assert detail.inputs[0].reference.id == imported.id
    assert detail.inputs[0].role == "sales"
    assert detail.evidence["cleaning_report"]["row_count_after"] == 2
    assert detail.summary.rationale.startswith("Remove duplicate")
    assert detail.files[0].available


def test_rendered_chart_records_configuration_without_injected_rows(app_paths, tmp_path):
    source = tmp_path / "sales.csv"
    source.write_text("region,sales\nnorth,12\nsouth,15\n")
    result = AnalysisGraphService(app_paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(source),
            dataset_name="Sales",
            spec={
                "mark": "bar",
                "encoding": {
                    "x": {"field": "region", "type": "nominal"},
                    "y": {"field": "sales", "type": "quantitative"},
                },
                "usermeta": {"note": "Keep this literal business label"},
            },
        )
    )
    assert Path(result.output_path).is_file()
    assert result.effective_parameters["mark"] == "bar"
    assert result.effective_parameters["usermeta"]["note"] == "Keep this literal business label"
    assert result.effective_parameters["data"] == {"name": "data"}
    assert "datasets" not in result.effective_parameters


def test_wordcloud_records_actual_options(app_paths, tmp_path):
    source = tmp_path / "terms.csv"
    source.write_text("word,count\ndemand,12\nstock,15\n")
    result = AnalysisGraphService(app_paths).graph_dataset(GraphDatasetInput(
        source_path=str(source), dataset_name="Topics", wordcloud_spec={"word_field": "word", "count_field": "count"},
    ))
    assert Path(result.output_path).is_file()
    assert result.effective_parameters["random_state"] == 42
    assert result.effective_parameters["width"] > 0
    assert result.effective_parameters["font_size_range"][0] < result.effective_parameters["font_size_range"][1]
    assert result.effective_parameters["colors"].keys() == {"demand", "stock"}


def test_scripted_harness_creates_interprets_and_reopens_actual_chart(storage, app_paths, tmp_path):
    from xenix.services.agent import AgentHarnessService, SubmitUserTurnInput
    from xenix.services.agent._analysis_tools import AnalysisTools
    from xenix.services.agent.audit_tools import register_audit_tools
    from xenix.services.agent.tool_catalog import AgentToolCatalog
    from xenix.services.agent.tool_inputs import AnalysisGraphInput
    from xenix.services.artifact_service import ArtifactService
    from xenix.services.llm import AgentToolRegistry, LLMConversationService, ProviderResponse, ProviderToolCall
    from xenix.services.llm.tool_protocol import AgentTool

    source = tmp_path / "sales.csv"
    source.write_text("region,sales\nnorth,12\nsouth,15\n")
    datasets = DatasetService(storage.session_factory, app_paths)
    dataset = datasets.register_dataset(RegisterDatasetInput(source_path=str(source), name="Sales"))
    registry = AgentToolRegistry(paged_results_dir=tmp_path / "pages")
    tools = AnalysisTools(dataset_service=datasets, artifact_service=ArtifactService(storage.session_factory), analysis_profile_service=None, analysis_graph_service=AnalysisGraphService(app_paths), ml_service=None)
    registry.register(AgentTool(name="analysis.graph", provider_name="analysis_graph", description="Draw a chart", input_model=AnalysisGraphInput, implementation=tools._analysis_graph))
    register_audit_tools(registry, storage.session_factory)
    catalog = AgentToolCatalog(registry.list_specs())
    registry.register(catalog.activation_tool())

    class Provider:
        calls = 0
        artifact_id = None

        def complete(self, messages, definitions):
            self.calls += 1
            if self.calls == 1:
                name, arguments = "agent.tools.activate", {"names": ["analysis.graph", "audit"]}
            elif self.calls in {2, 3}:
                assert "audit.explain" in {item.name for item in definitions}
                name = "analysis.graph"
                arguments = {"dataset_id": dataset.id, "spec": {"mark": "bar", "encoding": {"x": {"field": "region", "type": "nominal"}, "y": {"field": "sales", "type": "quantitative"}}}}
                if self.calls == 3:
                    assert messages[-1].tool_result_value["type"] == "tool_failure"
                    arguments["explanation"] = "Compare regional sales before allocating inventory."
            elif self.calls == 4:
                self.artifact_id = messages[-1].tool_result_value["artifact_id"]
                name, arguments = "audit.inspect", {"reference": {"kind": "artifact", "id": self.artifact_id}}
            elif self.calls == 5:
                assert messages[-1].tool_result_value["effective_parameters"]["mark"] == "bar"
                name, arguments = "audit.explain", {"reference": {"kind": "artifact", "id": self.artifact_id}, "explanation": "South has 15 sales versus 12 in North. This describes these records; it does not predict future demand.", "evidence": [{"kind": "artifact", "id": self.artifact_id}]}
            else:
                assert messages[-1].tool_result_value["saved"]
                return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": f"Review the regional comparison: [chart](artifact://{self.artifact_id})."}])
            return ProviderResponse(tool_calls=[ProviderToolCall(provider_call_id=f"call-{self.calls}", tool_name=name, provider_name=name.replace(".", "_"), arguments=arguments)])

    provider = Provider()
    conversation = LLMConversationService(session_factory=storage.session_factory, tool_registry=registry)
    harness = AgentHarnessService(conversation_service=conversation, provider=provider, tool_name_scope_provider=catalog.scope_names)
    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Compare regions and explain what the chart means."))
    reopened = conversation.get_thread_snapshot(snapshot.thread.id)
    assert reopened.messages[-1].kind.value == "assistant"
    detail = AuditQueryService(storage.session_factory).get_detail(AuditReference(kind="artifact", id=provider.artifact_id))
    assert detail.summary.thread_id == reopened.thread.id
    assert detail.summary.rationale.startswith("Compare regional")
    assert detail.explanations[0].text.startswith("South has 15")
    assert detail.files[0].available
