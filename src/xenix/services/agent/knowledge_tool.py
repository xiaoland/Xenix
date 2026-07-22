from __future__ import annotations

from typing import Any

from ...exceptions import ValidationError
from ..knowledge_service import (
    MAX_KNOWLEDGE_QUERY_CHARS,
    KnowledgeRetrievalUnavailable,
    KnowledgeService,
)
from ..llm import AgentToolSpec, ToolFailure, ToolSuccess

KNOWLEDGE_LOOKUP_TOOL_NAME = "knowledge.lookup"
_LOOKUP_ARGUMENTS = frozenset({"query", "mode"})
_LOOKUP_MODES = ("auto", "keyword", "semantic", "hybrid")
_RESULT_LIMIT = 5
_MAX_SOURCE_CHARS = 240
_MAX_EXCERPT_CHARS = 1600


def knowledge_lookup_tool_spec() -> AgentToolSpec:
    return AgentToolSpec(
        name=KNOWLEDGE_LOOKUP_TOOL_NAME,
        provider_name="knowledge_lookup",
        description=(
            "Search the user's Knowledge Library for business rules, definitions, "
            "assumptions, and experience relevant to the current data task. Ask in "
            "business language; choose a retrieval mode only when useful, and use "
            "returned source excerpts as guidance alongside computed data evidence."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_KNOWLEDGE_QUERY_CHARS,
                    "description": (
                        "The business question, rule, definition, assumption, or "
                        "experience needed for the current analysis, preprocessing, "
                        "or modeling task. Do not provide SQL or internal IDs."
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": list(_LOOKUP_MODES),
                    "default": "auto",
                    "description": (
                        "Retrieval mode: 'auto' selects the best ready mode; "
                        "'keyword' matches explicit terms and phrases; 'semantic' "
                        "matches meaning when wording differs; 'hybrid' combines "
                        "term and meaning matches. Semantic or hybrid can return a "
                        "typed unavailable result when that capability is not ready."
                    ),
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    )


def register_knowledge_lookup_tool(registry: Any, service: KnowledgeService) -> None:
    def lookup(arguments: dict[str, Any], _context: Any):
        try:
            query, mode = _validated_lookup_arguments(arguments)
        except ValidationError as exc:
            return ToolFailure(code="invalid_knowledge_lookup", message=str(exc))

        try:
            result = service.retrieve(query, mode=mode, top_k=_RESULT_LIMIT)
        except KnowledgeRetrievalUnavailable as exc:
            return ToolFailure(
                code=exc.error_code or "knowledge_retrieval_mode_unavailable",
                message=str(exc),
                details=dict(exc.error_details),
                repair_hints=tuple(exc.repair_hints),
                retryable=bool(exc.retryable),
            )
        except Exception:
            return ToolFailure(
                code="knowledge_lookup_failed",
                message="Knowledge lookup could not be completed.",
            )

        return ToolSuccess(
            value={
                "mode": result.mode,
                "results": _public_results(result.matches),
            }
        )

    registry.register(knowledge_lookup_tool_spec(), lookup)


def _validated_lookup_arguments(arguments: dict[str, Any]) -> tuple[str, str]:
    if set(arguments) - _LOOKUP_ARGUMENTS:
        raise ValidationError("knowledge.lookup accepts only 'query' and 'mode'.")

    raw_query = arguments.get("query")
    if not isinstance(raw_query, str):
        raise ValidationError("Knowledge query must be a string.")
    query = raw_query.strip()
    if not query:
        raise ValidationError("Knowledge query is required.")
    if len(query) > MAX_KNOWLEDGE_QUERY_CHARS:
        raise ValidationError(
            f"Knowledge query must not exceed {MAX_KNOWLEDGE_QUERY_CHARS} characters."
        )

    raw_mode = arguments.get("mode", "auto")
    if not isinstance(raw_mode, str):
        raise ValidationError("Knowledge retrieval mode must be a string.")
    mode = raw_mode.strip().lower()
    if mode not in _LOOKUP_MODES:
        raise ValidationError(
            "Knowledge retrieval mode must be auto, keyword, semantic, or hybrid."
        )
    return query, mode


def _public_results(matches: list[Any]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for match in matches[:_RESULT_LIMIT]:
        excerpt = str(getattr(match, "quote", "")).strip()[:_MAX_EXCERPT_CHARS]
        if not excerpt:
            continue
        result = {
            "source": _public_source(getattr(match, "title", "")),
            "excerpt": excerpt,
        }
        location = _public_location(getattr(match, "locator", None))
        if location is not None:
            result["location"] = location
        results.append(result)
    return results


def _public_source(value: Any) -> str:
    source = str(value).strip()
    looks_like_path = (
        "://" in source
        or "/" in source
        or "\\" in source
        or source.startswith("~")
        or (len(source) >= 2 and source[1] == ":")
    )
    if looks_like_path:
        source = source.split("?", 1)[0].split("#", 1)[0]
        source = source.rstrip("/\\").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if source in {".", "..", "~"}:
        source = ""
    return (source or "Knowledge source")[:_MAX_SOURCE_CHARS]


def _public_location(locator: Any) -> str | None:
    if not isinstance(locator, dict):
        return None
    for key, label in (("page", "page"), ("slide", "slide"), ("passage", "passage")):
        value = locator.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return f"{label} {value}"
    return None
