"""Black-box replay for the compact preprocessing Agent Harness contract.

The provider is deliberately local and scripted.  The test exercises the same
composition boundary as the desktop runtime while keeping the runtime home,
database, source workbook, and provider transcript under ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from xenix.app import _agent_skill_tool_scope_names
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.observability import LLM_USAGE_JOURNAL_FILE_NAME, LocalLLMUsageObservability
from xenix.services.agent import (
    AgentHarnessService,
    AgentSkillCatalog,
    SourceAttachmentInput,
    SubmitUserTurnInput,
)
from xenix.services.agent.tools import AgentToolRegistry as ConcreteAgentToolRegistry
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_inspection import detect_source_format, load_dataframe
from xenix.services.dataset_service import DatasetService
from xenix.services.llm import (
    AgentToolRegistry,
    AgentToolSpec,
    LLMConversationService,
    ProviderMessage,
    ProviderResponse,
    ProviderToolCall,
    canonical_json_bytes,
)
from xenix.services.llm.messages import DatasetBlock
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.preprocessing_worker import InlinePreprocessingWorkerRunner
from xenix.services.storage import StorageBootstrapService


class RecordingScriptedProvider:
    """Scripted provider that records bounded request/definition wire sizes."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
    ) -> ProviderResponse:
        dataset_id, call_number = self._record_request(messages, tools)

        if call_number == 1:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="activate-1",
                        tool_name="agent.skill.activate",
                        provider_name="agent_skill_activate",
                        arguments={"name": "xenix-data-preprocessing"},
                    )
                ],
                usage_payload={
                    "input_tokens": 510,
                    "cached_input_tokens": 0,
                    "output_tokens": 40,
                    "total_tokens": 550,
                },
            )
        if call_number == 2:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="query-1",
                        tool_name="data.query",
                        provider_name="data_query",
                        arguments={
                            "dataset_id": dataset_id,
                            "sql": (
                                'SELECT "customer_id", "amount", "segment" '
                                'FROM input ORDER BY "customer_id"'
                            ),
                            "limit": 50,
                        },
                    )
                ],
                usage_payload={
                    "input_tokens": 570,
                    "cached_input_tokens": 128,
                    "output_tokens": 50,
                    "total_tokens": 620,
                },
            )
        if call_number == 3:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="clean-1",
                        tool_name="data.clean",
                        provider_name="data_clean",
                        arguments={
                            "dataset_id": dataset_id,
                            "name": "Customers cleaned",
                            "operations": [
                                {
                                    "operation": "missing.fill_constant",
                                    "params": {"column_indexes": [1], "value": 0},
                                },
                                {
                                    "operation": "missing.fill_mode",
                                    "params": {"column_indexes": [2]},
                                },
                                {"operation": "duplicate.exact_rows", "params": {"keep": "first"}},
                            ],
                        },
                    )
                ],
                usage_payload={
                    "input_tokens": 640,
                    "cached_input_tokens": 256,
                    "output_tokens": 60,
                    "total_tokens": 700,
                },
            )
        if call_number == 4:
            return ProviderResponse(
                assistant_content_blocks=[
                    {"type": "text", "text": "数据已完成预处理，清洗后的数据集已生成。"}
                ],
                usage_payload={
                    "input_tokens": 680,
                    "cached_input_tokens": 384,
                    "output_tokens": 30,
                    "total_tokens": 710,
                },
            )
        raise AssertionError(f"unexpected provider call {call_number}")

    def _record_request(
        self,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
    ) -> tuple[str, int]:
        tool_names = [spec.name for spec in tools]
        message_payload = [message.model_dump(mode="json") for message in messages]
        tool_payload = [spec.model_dump(mode="json") for spec in tools]
        request_payload = {"messages": message_payload, "tools": tool_payload}
        request_bytes = len(canonical_json_bytes(request_payload))
        tool_definition_bytes = len(canonical_json_bytes(tool_payload))
        self.calls.append(
            {
                "messages": messages,
                "tool_names": tool_names,
                "request_bytes": request_bytes,
                "tool_definition_bytes": tool_definition_bytes,
            }
        )
        return _dataset_id_from_messages(messages), len(self.calls)


class IndexedRoleBindingProvider(RecordingScriptedProvider):
    """Replay the Unicode-header regression without spelling source headers."""

    def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
    ) -> ProviderResponse:
        dataset_id, call_number = self._record_request(messages, tools)
        if call_number == 1:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="activate-1",
                        tool_name="agent.skill.activate",
                        provider_name="agent_skill_activate",
                        arguments={"name": "xenix-data-preprocessing"},
                    )
                ],
                usage_payload={
                    "input_tokens": 510,
                    "cached_input_tokens": 0,
                    "output_tokens": 40,
                    "total_tokens": 550,
                },
            )
        if call_number == 2:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="query-1",
                        tool_name="data.query",
                        provider_name="data_query",
                        arguments={
                            "dataset_id": dataset_id,
                            "column_reference": "indexes",
                            "sql": "SELECT c2 AS last_month_commission, c5 AS churn FROM input",
                        },
                    )
                ],
                usage_payload={
                    "input_tokens": 570,
                    "cached_input_tokens": 128,
                    "output_tokens": 50,
                    "total_tokens": 620,
                },
            )
        if call_number == 3:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="bind-1",
                        tool_name="data.feature.select",
                        provider_name="data_feature_select",
                        arguments={
                            "dataset_id": dataset_id,
                            "role_bindings": [
                                {"role": "feature", "column_indexes": [0, 1, 2, 3, 4]},
                                {"role": "target", "column_indexes": [5]},
                            ],
                        },
                    )
                ],
                usage_payload={
                    "input_tokens": 640,
                    "cached_input_tokens": 256,
                    "output_tokens": 60,
                    "total_tokens": 700,
                },
            )
        if call_number == 4:
            return ProviderResponse(
                assistant_content_blocks=[
                    {"type": "text", "text": "字段角色已按索引绑定。"}
                ],
                usage_payload={
                    "input_tokens": 680,
                    "cached_input_tokens": 384,
                    "output_tokens": 30,
                    "total_tokens": 710,
                },
            )
        raise AssertionError(f"unexpected provider call {call_number}")


class IndexedTokenizationProvider(RecordingScriptedProvider):
    """Replay tokenization by source indexes, without spelling Unicode headers."""

    def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
    ) -> ProviderResponse:
        dataset_id, call_number = self._record_request(messages, tools)
        if call_number == 1:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="activate-1",
                        tool_name="agent.skill.activate",
                        provider_name="agent_skill_activate",
                        arguments={"name": "xenix-data-preprocessing"},
                    )
                ],
                usage_payload={
                    "input_tokens": 510,
                    "cached_input_tokens": 0,
                    "output_tokens": 40,
                    "total_tokens": 550,
                },
            )
        if call_number == 2:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="tokenize-1",
                        tool_name="data.tokenize",
                        provider_name="data_tokenize",
                        arguments={
                            "dataset_id": dataset_id,
                            "name": "Unicode reviews tokenized",
                            "text_column_index": 1,
                            "id_column_indexes": [0],
                            "output": "token_rows",
                        },
                    )
                ],
                usage_payload={
                    "input_tokens": 570,
                    "cached_input_tokens": 128,
                    "output_tokens": 50,
                    "total_tokens": 620,
                },
            )
        if call_number == 3:
            return ProviderResponse(
                assistant_content_blocks=[
                    {"type": "text", "text": "已按索引完成中文文本分词。"}
                ],
                usage_payload={
                    "input_tokens": 640,
                    "cached_input_tokens": 256,
                    "output_tokens": 30,
                    "total_tokens": 670,
                },
            )
        raise AssertionError(f"unexpected provider call {call_number}")


def _dataset_id_from_messages(messages: list[ProviderMessage]) -> str:
    for message in messages:
        for block in message.content_blocks:
            if isinstance(block, DatasetBlock):
                return block.dataset_id
    raise AssertionError("the provider request did not contain the attached dataset")


def _build_runtime(monkeypatch, tmp_path: Path, *, provider=None):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "isolated-runtime"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    dataset_service = DatasetService(storage.session_factory, paths)
    worker = InlinePreprocessingWorkerRunner()
    cleaning_service = DataCleaningService(paths, worker_runner=worker)
    query_service = DataQueryTransformService(paths, worker_runner=worker)
    ml_task_service = MLTaskService(storage.session_factory, paths)
    ml_service = MLService(paths, storage.session_factory, dataset_service, ml_task_service)
    artifact_service = ArtifactService(storage.session_factory)

    concrete_registry = ConcreteAgentToolRegistry(
        paths=paths,
        dataset_service=dataset_service,
        data_cleaning_service=cleaning_service,
        data_transform_service=query_service,
        ml_service=ml_service,
        artifact_service=artifact_service,
        preprocessing_worker_runner=worker,
    )
    llm_registry = AgentToolRegistry()
    concrete_registry.register_with_llm(llm_registry)

    skill_catalog = AgentSkillCatalog.from_default_catalog()
    activation = skill_catalog.activation_tool_spec()
    assert activation is not None
    llm_registry.register(
        activation,
        lambda arguments, _context: skill_catalog.activate(str(arguments["name"])),
    )

    def context_messages(snapshot):
        activation_call_ids = {
            message.id
            for message in snapshot.messages
            if getattr(message, "tool_id", None) == "agent.skill.activate"
        }
        activated = {
            str(message.value_payload["skill_name"])
            for message in snapshot.messages
            if getattr(message, "tool_call_message_id", None) in activation_call_ids
            and isinstance(getattr(message, "value_payload", None), dict)
            and isinstance(message.value_payload.get("skill_name"), str)
        }
        context = skill_catalog.catalog_provider_message(activated_skill_names=activated)
        return [context] if context is not None else []

    conversation = LLMConversationService(
        session_factory=storage.session_factory,
        tool_registry=llm_registry,
        context_messages_provider=context_messages,
        usage_observability=LocalLLMUsageObservability(paths.logs / LLM_USAGE_JOURNAL_FILE_NAME),
    )
    provider = provider or RecordingScriptedProvider()
    harness = AgentHarnessService(
        conversation_service=conversation,
        provider=provider,
        dataset_service=dataset_service,
        tool_name_scope_provider=_agent_skill_tool_scope_names,
    )
    return harness, provider, dataset_service, conversation


def test_harness_replays_compact_indexed_cleaning_without_metadata_roundtrip(
    monkeypatch,
    tmp_path: Path,
) -> None:
    harness, provider, dataset_service, conversation = _build_runtime(monkeypatch, tmp_path)
    source = tmp_path / "customers.xlsx"
    pd.DataFrame(
        [
            [1, 10, "A"],
            [2, None, "B"],
            [2, None, "B"],
            [3, 30, None],
        ],
        columns=["customer_id", "amount", "segment"],
    ).to_excel(source, index=False)

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(
            text="请先预处理这个客户表，再告诉我结果。",
            source_attachments=[SourceAttachmentInput(file_path=str(source))],
            client_submission_id="cleaning-efficiency-replay",
        )
    )

    assert [message.kind.value for message in snapshot.messages] == [
        "user",
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "assistant",
    ]
    assert not [message for message in snapshot.messages if message.kind.value == "pending_llm_sampling"]

    calls = [message for message in snapshot.messages if message.kind.value == "tool_call"]
    results = [message for message in snapshot.messages if message.kind.value == "tool_result"]
    assert [message.tool_id for message in calls] == [
        "agent.skill.activate",
        "data.query",
        "data.clean",
    ]
    assert len(calls) == len(results) == 3
    assert all(result.tool_call_message_id == call.id for call, result in zip(calls, results, strict=True))
    assert [result.result_status for result in results] == ["succeeded", "succeeded", "succeeded"]
    assert results[0].value_payload["skill_name"] == "xenix-data-preprocessing"
    assert results[1].value_payload["columns"]["_schema"] == {"name": 0, "type": 1, "index": 2}
    clean_arguments = calls[2].arguments_payload
    assert clean_arguments["operations"][0]["params"] == {"column_indexes": [1], "value": 0}
    assert clean_arguments["operations"][1]["params"] == {"column_indexes": [2]}
    assert "columns" not in json.dumps(clean_arguments, ensure_ascii=False)
    assert snapshot.messages[-1].text == "数据已完成预处理，清洗后的数据集已生成。"
    assert any(
        '"active":true' in message.content.replace(" ", "")
        for message in provider.calls[1]["messages"]
        if message.role == "system" and "available_agent_skills" in message.content
    )

    # Exactly the three useful tools ran: activation, evidence query, clean.
    # In particular, no metadata discovery call is needed for this known plan.
    assert [call.tool_id for call in calls].count("data.clean.metadata") == 0
    assert len(provider.calls) == 4
    assert all(call["request_bytes"] > call["tool_definition_bytes"] > 0 for call in provider.calls)
    assert max(call["request_bytes"] for call in provider.calls) < 80_000
    usage = conversation.usage_overviews(snapshot)
    assert len(usage) == 1
    assert usage[0].usage.to_payload() == {
        "request_count": 4,
        "input_tokens": 2_400,
        "cached_input_tokens": 768,
        "output_tokens": 180,
        "total_tokens": 2_580,
    }
    full_scope = provider.calls[0]
    scoped_calls = provider.calls[1:]
    assert "model.train" in full_scope["tool_names"]
    assert all("model.train" not in call["tool_names"] for call in scoped_calls)
    assert all(
        set(call["tool_names"])
        == {
            "agent.skill.activate",
            "data.integrate",
            "data.clean",
            "data.clean.metadata",
            "data.tokenize",
            "data.query",
            "data.transform",
            "data.feature.select",
        }
        for call in scoped_calls
    )
    assert all(call["tool_definition_bytes"] < full_scope["tool_definition_bytes"] for call in scoped_calls)
    assert len({call["tool_definition_bytes"] for call in scoped_calls}) == 1

    clean_result = results[2].value_payload
    assert clean_result["cleaning_report"]["operation_count"] == 3
    assert len(canonical_json_bytes(clean_result)) < 16_000
    derived = dataset_service.get_dataset(clean_result["dataset_id"])
    assert derived.derived_from_dataset_id == _dataset_id_from_messages(provider.calls[0]["messages"])
    frame = load_dataframe(Path(derived.source_path), detect_source_format(Path(derived.source_path)))
    assert frame.to_dict(orient="records") == [
        {"customer_id": 1, "amount": 10, "segment": "A"},
        {"customer_id": 2, "amount": 0, "segment": "B"},
        {"customer_id": 3, "amount": 30, "segment": "B"},
    ]


def test_harness_replays_indexed_query_and_role_binding_for_unicode_headers(
    monkeypatch,
    tmp_path: Path,
) -> None:
    provider = IndexedRoleBindingProvider()
    harness, provider, _dataset_service, _conversation = _build_runtime(
        monkeypatch,
        tmp_path,
        provider=provider,
    )
    source = tmp_path / "unicode-churn.xlsx"
    pd.DataFrame(
        [[22686.5, 297, 149.25, 2029.85, 0, 0]],
        columns=[
            "Account Balance (Yuan)",
            "Days Since Last Transaction",
            "Last Month’s Trading Commission (Yuan)",
            "Total Trading Commission (Yuan)",
            "Years with This Brokerage",
            "Customer Churn (Yes/No)",
        ],
    ).to_excel(source, index=False)

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(
            text="请按字段角色准备这个客户流失数据。",
            source_attachments=[SourceAttachmentInput(file_path=str(source))],
            client_submission_id="indexed-role-binding-replay",
        )
    )

    calls = [message for message in snapshot.messages if message.kind.value == "tool_call"]
    results = [message for message in snapshot.messages if message.kind.value == "tool_result"]
    assert [call.tool_id for call in calls] == [
        "agent.skill.activate",
        "data.query",
        "data.feature.select",
    ]
    assert [result.result_status for result in results] == ["succeeded", "succeeded", "succeeded"]
    assert calls[1].arguments_payload["column_reference"] == "indexes"
    assert calls[1].arguments_payload["sql"] == "SELECT c2 AS last_month_commission, c5 AS churn FROM input"
    assert calls[2].arguments_payload["role_bindings"] == [
        {"role": "feature", "column_indexes": [0, 1, 2, 3, 4]},
        {"role": "target", "column_indexes": [5]},
    ]
    assert results[1].value_payload["rows"]["data"] == [[149.25, 0]]
    bindings_by_role = {
        binding["role"]: binding["columns"]
        for binding in results[2].value_payload["role_bindings"]
    }
    assert bindings_by_role["feature"][2] == "Last Month’s Trading Commission (Yuan)"
    assert bindings_by_role["target"] == ["Customer Churn (Yes/No)"]
    assert snapshot.messages[-1].text == "字段角色已按索引绑定。"


def test_harness_replays_indexed_tokenization_for_unicode_headers(
    monkeypatch,
    tmp_path: Path,
) -> None:
    provider = IndexedTokenizationProvider()
    harness, provider, dataset_service, _conversation = _build_runtime(
        monkeypatch,
        tmp_path,
        provider=provider,
    )
    source = tmp_path / "unicode-reviews.xlsx"
    pd.DataFrame(
        [
            ["r1", "订单 退款 速度 快"],
            ["r2", "服务 热情 环境 舒适"],
        ],
        columns=["Review ID (编号)", "Review’s Text"],
    ).to_excel(source, index=False)

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(
            text="请把这个中文评论字段分词。",
            source_attachments=[SourceAttachmentInput(file_path=str(source))],
            client_submission_id="indexed-tokenization-replay",
        )
    )

    calls = [message for message in snapshot.messages if message.kind.value == "tool_call"]
    results = [message for message in snapshot.messages if message.kind.value == "tool_result"]
    assert [call.tool_id for call in calls] == [
        "agent.skill.activate",
        "data.tokenize",
    ]
    assert [result.result_status for result in results] == ["succeeded", "succeeded"]
    tokenize_arguments = calls[1].arguments_payload
    assert tokenize_arguments["text_column_index"] == 1
    assert tokenize_arguments["id_column_indexes"] == [0]
    assert "Review’s Text" not in json.dumps(tokenize_arguments, ensure_ascii=False)
    assert "Review ID (编号)" not in json.dumps(tokenize_arguments, ensure_ascii=False)
    assert snapshot.messages[-1].text == "已按索引完成中文文本分词。"
    assert len(provider.calls) == 3

    source_dataset_id = _dataset_id_from_messages(provider.calls[0]["messages"])
    tokenize_result = results[1].value_payload
    derived = dataset_service.get_dataset(tokenize_result["dataset_id"])
    assert derived.derived_from_dataset_id == source_dataset_id
    frame = load_dataframe(Path(derived.source_path), detect_source_format(Path(derived.source_path)))
    assert frame.to_dict(orient="records") == [
        {"source_row_number": 1, "Review ID (编号)": "r1", "token_index": 1, "token": "订单"},
        {"source_row_number": 1, "Review ID (编号)": "r1", "token_index": 2, "token": "退款"},
        {"source_row_number": 1, "Review ID (编号)": "r1", "token_index": 3, "token": "速度"},
        {"source_row_number": 2, "Review ID (编号)": "r2", "token_index": 1, "token": "服务"},
        {"source_row_number": 2, "Review ID (编号)": "r2", "token_index": 2, "token": "热情"},
        {"source_row_number": 2, "Review ID (编号)": "r2", "token_index": 3, "token": "环境"},
        {"source_row_number": 2, "Review ID (编号)": "r2", "token_index": 4, "token": "舒适"},
    ]
