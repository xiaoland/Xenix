# Dataset age audit

## Objective

Record how session-produced datasets were derived and show that evidence in the
Chatbot tool-call UI so a user can audit provenance and generation depth.

## Guardrails

- Dataset storage is authoritative for derivation records and input edges.
- LLM Conversation remains authoritative for ToolCall and ToolResult lifecycle.
- Harness/UI resolve derivations by stable ToolCall references; they do not parse
  ToolResult payloads into a second truth.
- Agent-authored explanations remain optional, bounded annotations and are shown
  as unverified claims.
- Existing single-parent `derived_from_dataset_id` consumers remain compatible.
- Avoid validation, indirection, and compatibility logic without a concrete
  invalid state or existing consumer to protect.

## Verification

- Fresh schema and v25 upgrade both produce ORM-readable derivation tables.
- Single- and multi-input transforms record operation, ordered inputs, ToolCall,
  parameters, and optional explanation.
- Multi-input derived datasets are never classified as original imports.
- Chatbot projection shows persisted audit evidence without parsing ToolResult.
- Focused tests, full relevant tests, and `pdm run check` pass on Python 3.14.2.
- `pdm run smoke` reaches the existing packaged knowledge smoke, then the
  `lancedb` native extension raises `SIGBUS` while loading in this headless VPS;
  the failure is outside the Dataset age execution path.

## Current Truth

- Branch `feat/dataset-age-audit` starts at `develop@6a8d896`.
- Schema v26 persists one authoritative derivation record per generated Dataset
  plus ordered input edges, including multi-input transforms.
- `DatasetRow.derived_from_dataset_id` remains a best-effort compatibility
  projection for existing single-parent consumers.
- Dataset tools attach the staged ToolCall id; the Harness resolves persisted
  audit evidence directly and the GUI shows generation, inputs, parameters, and
  an explicitly unverified optional Agent explanation.
- The maintainability review removed redundant thread persistence and a generic
  enrichment abstraction, relies on typed input validation, and avoids a ToolCall
  foreign key because the staged message is committed after tool execution.
- On Python 3.14.2, 37 relevant tests pass and `pdm run check` passes (Ruff, Mypy,
  generated artifacts, knowledge lock validation, and compileall).

## Next Step

Publish the reviewed implementation from `feat/dataset-age-audit` for review.
