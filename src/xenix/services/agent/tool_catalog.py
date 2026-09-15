"""Discover and activate registered tools independently of Skill guidance."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ...exceptions import ValidationError
from ..llm.providers import ProviderMessage
from ..llm.tool_protocol import (
    AgentTool,
    AgentToolSpec,
    ToolExecutionContext,
    ToolSuccess,
)
from .tool_inputs import AgentToolsActivateInput


AGENT_TOOLS_ACTIVATE_NAME = "agent.tools.activate"


class AgentToolCatalog:
    """A visibility projection; execution and schemas remain registry-owned."""

    def __init__(self, specs: Iterable[AgentToolSpec]) -> None:
        self._specs = {spec.name: spec for spec in specs}
        self._always_available = {
            name for name in self._specs
            if name.startswith("agent.skill.") or name in {"knowledge.lookup", "result.page"}
        }
        self._on_demand = self._specs.keys() - self._always_available
        self._selections: dict[str, set[str]] = {}
        for name in self._on_demand:
            parts = name.split(".")
            for length in range(1, len(parts) + 1):
                selector = ".".join(parts[:length])
                self._selections.setdefault(selector, set()).add(name)

    def activation_tool(self) -> AgentTool[AgentToolsActivateInput]:
        def activate(arguments: AgentToolsActivateInput, _context: ToolExecutionContext) -> ToolSuccess:
            missing = set(arguments.names) - self._selections.keys()
            if missing:
                raise ValidationError("Unknown tool names or namespaces: " + ", ".join(sorted(missing)))
            return ToolSuccess({"activated_tools": sorted(self._expand_names(arguments.names))})

        return AgentTool(
            name=AGENT_TOOLS_ACTIVATE_NAME,
            provider_name="agent_tools_activate",
            description="Load full tool definitions in one batch for subsequent requests. Does not read Skills.",
            input_model=AgentToolsActivateInput,
            implementation=activate,
            provider_field_enums=(("names", tuple(sorted(self._selections))),),
        )

    def _expand_names(self, names: Iterable[str]) -> set[str]:
        return {tool for name in names for tool in self._selections.get(name, ())}

    def activated_names(self, snapshot: Any) -> set[str]:
        calls = {
            message.id: message for message in snapshot.messages
            if getattr(message, "tool_id", None) == AGENT_TOOLS_ACTIVATE_NAME
        }
        names: set[str] = set()
        for message in snapshot.messages:
            call = calls.get(getattr(message, "tool_call_message_id", None))
            status = getattr(message, "result_status", None)
            if call is not None and getattr(status, "value", status) == "succeeded":
                # Identity belongs to the successful call, even when its result is paged.
                names.update((call.arguments_payload or {}).get("names", []))
        return self._expand_names(names)

    def scope_names(self, snapshot: Any) -> tuple[str, ...]:
        return tuple(sorted(self._always_available | self.activated_names(snapshot) | {AGENT_TOOLS_ACTIVATE_NAME}))

    def provider_message(self, snapshot: Any) -> ProviderMessage | None:
        inactive = self._on_demand - self.activated_names(snapshot)
        if not inactive:
            return None
        lines = [
            f"Available tools: use `{AGENT_TOOLS_ACTIVATE_NAME}` with tool names or namespaces when you need their full "
            "parameter definitions. You may call a tool directly when its arguments are known. Skill reading is independent."
        ]
        lines.extend(f"- {name}: {self._specs[name].description}" for name in sorted(inactive))
        return ProviderMessage(role="system", content="\n".join(lines))
