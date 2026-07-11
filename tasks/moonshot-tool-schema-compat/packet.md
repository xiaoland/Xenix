# Moonshot Tool Schema Compatibility

## Objective & Hypothesis

Provider-facing tool schemas should avoid advanced JSON Schema combinators because OpenAI-compatible providers do not share one stable schema subset. The Moonshot 400 on thread `0664a9dff45a4412a56fc9d5d752daa8` is consistent with `data.query` exposing top-level `anyOf`.

## Guardrails Touched

- LLM Service/provider adapter boundary
- Agent Harness provider-facing tool schema contract
- `data.query` and `analysis.graph` tool schema descriptions

## Verification

- Update schema tests to reject `anyOf` / `oneOf` on provider-facing tool schemas.
- Run focused agent/tool schema tests.
- `pdm run pytest tests/test_agent_harness_first_slice.py::test_agent_harness_model_metadata_exposes_contract_without_train_enums tests/test_analysis_graph.py::test_analysis_graph_tool_schema_is_dataset_scoped` passed.
- `pdm run pytest tests/test_agent_harness_first_slice.py tests/test_analysis_graph.py` passed: 38 tests.

## Current Understanding

Runtime validation remains in Xenix services and tool handlers. Provider-facing JSON Schema should guide model argument shape using simple object/property/required declarations plus descriptions for either/or constraints and deterministic priority.
`data.query` no longer exposes `anyOf`; its description states that at least one input source is required and that `bindings` wins when both input forms are present. `analysis.graph` no longer exposes `oneOf`; its description states that exactly one graph mode must be passed.

## Next Step

No implementation step remains for this slice.
