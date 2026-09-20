"""Public audit tools: read domain evidence and append attributed interpretations."""

from pydantic import Field

from ..audit_contracts import AuditReference, AuditScope, ExplanationText
from ..audit_service import AuditExplanationService, AuditQueryService
from ..llm.tool_protocol import AgentTool, ToolExecutionContext, ToolSuccess
from .tool_inputs import AgentToolInput


class AuditListInput(AgentToolInput):
    search: str = ""
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


class AuditInspectInput(AgentToolInput):
    reference: AuditReference


class AuditExplainInput(AgentToolInput):
    reference: AuditReference
    explanation: ExplanationText = Field(
        description="Explain observed results in business language, cite the evidence, and state limitations and useful checks. Do not claim the explanation is system-verified."
    )
    evidence: list[AuditReference] = Field(min_length=1)


def register_audit_tools(registry, session_factory) -> None:
    query = AuditQueryService(session_factory)
    writer = AuditExplanationService(session_factory)

    def list_outputs(arguments: AuditListInput, context: ToolExecutionContext) -> ToolSuccess:
        items = query.list_outputs(
            AuditScope(thread_id=context.thread_id),
            search=arguments.search,
            limit=arguments.limit + 1,
            offset=arguments.offset,
        )
        return ToolSuccess(
            {
                "outputs": [item.model_dump(mode="json") for item in items[: arguments.limit]],
                "next_offset": arguments.offset + arguments.limit if len(items) > arguments.limit else None,
            }
        )

    def inspect(arguments: AuditInspectInput, context: ToolExecutionContext) -> ToolSuccess:
        return ToolSuccess(query.get_detail(arguments.reference, thread_id=context.thread_id).model_dump(mode="json"))

    def explain(arguments: AuditExplainInput, context: ToolExecutionContext) -> ToolSuccess:
        annotation_id = writer.explain(
            arguments.reference,
            text=arguments.explanation,
            evidence=arguments.evidence,
            thread_id=context.thread_id,
            tool_call_message_id=context.tool_call_message_id,
        )
        return ToolSuccess(
            {"explanation_id": annotation_id, "reference": arguments.reference.model_dump(mode="json"), "saved": True}
        )

    for tool in (
        AgentTool(
            name="audit.list",
            provider_name="audit_list",
            input_model=AuditListInput,
            implementation=list_outputs,
            description="Find this conversation's retained outputs and missing interpretations, including work completed in the background. Returns typed references for audit.inspect and audit.explain.",
        ),
        AgentTool(
            name="audit.inspect",
            provider_name="audit_inspect",
            input_model=AuditInspectInput,
            implementation=inspect,
            description="Read recorded inputs, actual parameters, evaluation evidence, and earlier Agent explanations for a Dataset, model, Artifact or ML task. Does not execute work.",
        ),
        AgentTool(
            name="audit.explain",
            provider_name="audit_explain",
            input_model=AuditExplainInput,
            implementation=explain,
            description="After inspecting completed results, save a business-readable interpretation with recorded evidence and limitations for each delivered output. Append corrections without overwriting history; never invent metrics. A pre-execution rationale alone is not a result interpretation.",
        ),
    ):
        registry.register(tool)
