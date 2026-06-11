from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.observability import stable_hash
from xenix.services.agent import AgentHarnessService, ProviderResponse, ProviderToolCall, SubmitUserTurnInput
from xenix.services.agent.providers import AgentToolSpec
from xenix.services.agent.tools import ToolExecutionContext, ToolExecutionResult
import xenix.services.agent.harness_service as harness_module
from xenix.services.storage import StorageBootstrapService


@dataclass
class CapturedSpan:
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value


class _CapturedSpanScope:
    def __init__(self, span: CapturedSpan) -> None:
        self._span = span

    def __enter__(self) -> CapturedSpan:
        return self._span

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class TelemetryCapture:
    def __init__(self, monkeypatch) -> None:
        self.spans: list[CapturedSpan] = []
        self.counters: list[tuple[str, int, dict[str, Any]]] = []
        self.histograms: list[tuple[str, float, dict[str, Any], str | None]] = []

        def start_span(name: str, attributes: dict[str, Any] | None = None):
            span = CapturedSpan(name=name, attributes=dict(attributes or {}))
            self.spans.append(span)
            return _CapturedSpanScope(span)

        monkeypatch.setattr(harness_module, "start_span", start_span)
        monkeypatch.setattr(
            harness_module,
            "record_counter",
            lambda name, value=1, attributes=None: self.counters.append((name, value, dict(attributes or {}))),
        )
        monkeypatch.setattr(
            harness_module,
            "record_histogram",
            lambda name, value, attributes=None, unit=None: self.histograms.append(
                (name, value, dict(attributes or {}), unit)
            ),
        )

    def spans_named(self, name: str) -> list[CapturedSpan]:
        return [span for span in self.spans if span.name == name]


class UsageProvider:
    provider_key = "openai"
    model = "gpt-4o-test"

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": "Done without echoing secrets."}],
            tool_calls=[],
            usage_payload={
                "input_tokens": 12,
                "cached_input_tokens": 3,
                "output_tokens": 5,
                "total_tokens": 17,
                "provider_usage": {"raw": "not exported"},
            },
        )


class HiddenToolProvider:
    provider_key = "openai"
    model = "gpt-4o-test"

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        return ProviderResponse(
            tool_calls=[
                ProviderToolCall(
                    provider_call_id="call-hidden-train",
                    tool_name="model.train",
                    arguments={"secret": "do-not-export"},
                )
            ]
        )


class ToolThenDoneProvider:
    provider_key = "openai"
    model = "gpt-4o-test"

    def __init__(self) -> None:
        self._calls = 0

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        self._calls += 1
        if self._calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="call-peek",
                        tool_name="data.peek",
                        arguments={"name": "secret dataset label"},
                    )
                ],
                usage_payload={"input_tokens": 20, "output_tokens": 4, "total_tokens": 24},
            )
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": "Ready."}],
            usage_payload={"input_tokens": 30, "output_tokens": 6, "total_tokens": 36},
        )


class StaticRegistry:
    def list_specs(self) -> list[AgentToolSpec]:
        return [
            AgentToolSpec(
                name="data.peek",
                provider_name="data_peek",
                description="Inspect a dataset.",
                parameters_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            ),
            AgentToolSpec(
                name="data.integrate",
                provider_name="data_integrate",
                description="Register a file.",
                parameters_schema={"type": "object", "properties": {}},
            ),
            AgentToolSpec(
                name="model.train",
                provider_name="model_train",
                description="Train a model.",
                parameters_schema={"type": "object", "properties": {}},
            ),
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        if tool_name == "data.peek":
            return ToolExecutionResult(
                payload={"dataset_id": "dataset-1", "secret_result": "not exported"},
                content_blocks=[{"type": "markdown", "text": "Dataset ready."}],
            )
        raise AssertionError(f"Unexpected tool execution: {tool_name}")


def _build_harness(monkeypatch, tmp_path: Path, *, provider: Any, registry: Any | None = None) -> AgentHarnessService:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    return AgentHarnessService(
        session_factory=context.session_factory,
        tool_registry=registry or StaticRegistry(),
        provider=provider,
    )


def test_provider_request_projects_ai_shape_usage_and_tool_exposure(monkeypatch, tmp_path: Path) -> None:
    telemetry = TelemetryCapture(monkeypatch)
    harness = _build_harness(monkeypatch, tmp_path, provider=UsageProvider())

    harness.submit_user_turn(
        SubmitUserTurnInput(
            text="Please analyze SECRET_CUSTOMER_FIELD",
            file_paths=["customers.csv"],
        )
    )

    turn_span = telemetry.spans_named("agent.turn")[0]
    assert turn_span.attributes["openinference.span.kind"] == "AGENT"
    assert turn_span.attributes["gen_ai.operation.name"] == "invoke_agent"
    assert "xenix.ai.turn.id_hash" in turn_span.attributes

    provider_span = telemetry.spans_named("agent.provider_request")[0]
    assert provider_span.attributes["openinference.span.kind"] == "LLM"
    assert provider_span.attributes["gen_ai.operation.name"] == "chat"
    assert provider_span.attributes["gen_ai.provider.name"] == "openai"
    assert provider_span.attributes["gen_ai.request.stream"] is False
    assert provider_span.attributes["xenix.ai.loop.step_index"] == 1
    assert provider_span.attributes["xenix.ai.request.message_count"] == 2
    assert provider_span.attributes["xenix.ai.request.message.system_count"] == 1
    assert provider_span.attributes["xenix.ai.request.message.user_count"] == 1
    assert provider_span.attributes["xenix.ai.request.system_present"] is True
    assert provider_span.attributes["xenix.ai.tools.exposed.count"] == 2
    assert provider_span.attributes["xenix.ai.tools.exposed.data_count"] == 2
    assert provider_span.attributes["xenix.ai.response.assistant_text_present"] is True
    assert provider_span.attributes["xenix.ai.response.tool_call_count"] == 0
    assert provider_span.attributes["xenix.ai.provider_request.status"] == "succeeded"
    assert provider_span.attributes["xenix.ai.usage.present"] is True
    assert provider_span.attributes["gen_ai.usage.input_tokens"] == 12
    assert provider_span.attributes["gen_ai.usage.cache_read.input_tokens"] == 3
    assert provider_span.attributes["gen_ai.usage.output_tokens"] == 5
    assert provider_span.attributes["llm.token_count.total"] == 17
    assert provider_span.attributes["xenix.ai.model.hash"] == stable_hash("gpt-4o-test")
    assert "gen_ai.request.model" not in provider_span.attributes

    token_histograms = [item for item in telemetry.histograms if item[0] == "gen_ai.client.token.usage"]
    assert [(value, attrs["gen_ai.token.type"], unit) for _name, value, attrs, unit in token_histograms] == [
        (12, "input", "{token}"),
        (5, "output", "{token}"),
    ]

    exported_values = " ".join(str(value) for span in telemetry.spans for value in span.attributes.values())
    assert "SECRET_CUSTOMER_FIELD" not in exported_values
    assert "not exported" not in exported_values
    assert "provider_usage" not in exported_values


def test_tool_call_span_keeps_parent_provider_context(monkeypatch, tmp_path: Path) -> None:
    telemetry = TelemetryCapture(monkeypatch)
    harness = _build_harness(monkeypatch, tmp_path, provider=ToolThenDoneProvider())

    harness.submit_user_turn(SubmitUserTurnInput(text="Inspect the uploaded file", file_paths=["customers.csv"]))

    provider_spans = telemetry.spans_named("agent.provider_request")
    tool_span = telemetry.spans_named("agent.tool_call")[0]
    first_provider_hash = provider_spans[0].attributes["xenix.ai.provider_request.id_hash"]

    assert len(provider_spans) == 2
    assert provider_spans[1].attributes["xenix.ai.request.tool_result_present"] is True
    assert provider_spans[1].attributes["xenix.ai.request.message.tool_count"] == 1
    assert tool_span.attributes["openinference.span.kind"] == "TOOL"
    assert tool_span.attributes["gen_ai.operation.name"] == "execute_tool"
    assert tool_span.attributes["gen_ai.tool.name"] == "data.peek"
    assert tool_span.attributes["xenix.ai.tool.category"] == "data"
    assert tool_span.attributes["xenix.ai.provider_request.id_hash"] == first_provider_hash
    assert tool_span.attributes["xenix.ai.loop.step_index"] == 1

    exported_values = " ".join(str(value) for span in telemetry.spans for value in span.attributes.values())
    assert "secret dataset label" not in exported_values
    assert "secret_result" not in exported_values


def test_invalid_tool_call_is_classified_without_arguments(monkeypatch, tmp_path: Path) -> None:
    telemetry = TelemetryCapture(monkeypatch)
    harness = _build_harness(monkeypatch, tmp_path, provider=HiddenToolProvider())

    with pytest.raises(ValidationError):
        harness.submit_user_turn(SubmitUserTurnInput(text="Train a model without context"))

    provider_span = telemetry.spans_named("agent.provider_request")[0]
    assert provider_span.attributes["xenix.ai.failure.category"] == "invalid_tool_call"
    assert provider_span.attributes["xenix.ai.provider_request.status"] == "failed"
    assert provider_span.attributes["xenix.ai.invalid_tool_call.count"] == 1
    assert provider_span.attributes["xenix.ai.invalid_tool_call.first_name_hash"] == stable_hash("model.train")
    assert "model.train" not in str(provider_span.attributes["xenix.ai.invalid_tool_call.first_name_hash"])

    provider_counts = [item for item in telemetry.counters if item[0] == "xenix.agent.provider_request.count"]
    assert provider_counts[-1][2]["status"] == "failed"

    exported_values = " ".join(str(value) for span in telemetry.spans for value in span.attributes.values())
    assert "do-not-export" not in exported_values
