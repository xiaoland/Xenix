# Solidify Review

## User-Level Direction

Confirmed product direction:

- `analysis.graph` remains a chart-generation tool.
- The Agent should receive a real visualization grammar, not a Xenix-owned chart DSL.
- Provider-facing schema is `{dataset_id, spec}`.
- The spec is Vega-Lite JSON.
- Xenix uses `vl-convert-python` as the first static rendering candidate.
- No compatibility is required for the old `{operation, params}` contract.
- Vega-Lite transform features do not need special prohibition for tool orthogonality.
- Output shape is not important beyond giving the Agent an `artifact_id` for the graph artifact.
- Tool failures must give the Agent enough information to adjust and retry.

## Demand Review

From a product-demand perspective, the direction is coherent:

- Non-technical business users ask for charts at the intent level; the Agent should translate intent into a visual grammar.
- Vega-Lite is familiar enough to LLMs and broad enough for routine data-mining visuals.
- Keeping `analysis.graph` as artifact-producing chart generation preserves the current user-visible purpose.
- Data shaping remains orthogonal:
  - `data.clean`: cleaning/normalization.
  - `data.query`: read-only analysis/result shaping.
  - `data.transform`: materialized derived datasets.
  - `analysis.graph`: visualization over a registered dataset or derived dataset.
- `analysis.lambda` remains an escape hatch for custom analytical procedures, not routine charts.

The main product invariant:

- A successful graph call must return a user-openable image artifact id.

The main failure invariant:

- A failed graph call must explain what the Agent should change: column name, spec shape, data source, size, render limitation, or required pre-aggregation.

## Technical Reality Review

Existing code supports the high-level move:

- `ArtifactService` already registers `ArtifactKind.IMAGE` artifacts and resolves `artifact://...`.
- Chatbot already supports inline image artifacts through markdown image syntax in assistant messages.
- Tool failure propagation already makes validation errors visible to the provider:
  - `AgentHarnessService` catches tool exceptions.
  - It writes result payload `{"error": "..."}`
  - Provider-facing tool result includes the failed status and `error_summary`.
- Current graph tests are already centered on service output and artifact registration; they can be replaced with Vega-Lite spec tests.

The major technical risk is synchronization:

- Agent tool schema in `src/xenix/services/agent/tools.py`
- Graph service contract in `src/xenix/services/analysis_graph.py`
- Durable docs in `docs/20-product-tdd/runtime-boundaries.md` and `docs/30-unit-tdd/agent-harness.md`
- Test expectations in `tests/test_analysis_graph.py`, `tests/test_agent_harness_first_slice.py`, and streaming exposure tests
- Packaging smoke for `vl-convert-python`

## Sub-Agent Review Summary

The code-mapper review reached the same main conclusion:

- The largest risk is not whether the Agent can describe charts.
- The largest risk is protocol boundary and persisted contract synchronization.

Highlighted integration risks:

- Tool protocol change from `operation/params` to `spec`.
- Artifact contract must keep `image/svg+xml`, `ArtifactKind.IMAGE`, and metadata stable enough for UI preview/open.
- `vl-convert-python` adds native/platform wheel packaging risk.
- Free-form Vega-Lite specs need robust failure semantics.
- Tests must be updated across graph service, Agent schema exposure, artifact registration, and UI artifact preview.

## Thinking Passes

### First Principles

The tool has three essential transformations:

1. User visual intent becomes Vega-Lite spec.
2. Registered dataset becomes renderer-visible data.
3. Renderer output becomes service-managed artifact.

Only the second and third are Xenix's hard responsibility. The first is Agent responsibility bounded by tool failure feedback.

### Boundary Reasoning

The important boundary is not "which Vega-Lite transform is allowed".

The important boundary is:

- the renderer only receives data from `dataset_id`
- output remains bounded
- failures are actionable
- chart artifacts stay service-owned

### Sequence Reasoning

Implementation should not start by deleting all hand-rendered SVG code blindly.

The safe sequence:

1. Add dependency and prove import/convert in tests.
2. Replace `GraphDatasetInput` shape.
3. Add policy/sanitizer and field validation.
4. Render SVG through `vl-convert-python`.
5. Register artifact exactly as before.
6. Update Agent tool schema and tests.
7. Update durable docs after tests pass.
8. Run packaging smoke.

### Failure-Mode Reasoning

Failures should be grouped by Agent action:

- `spec_missing`: provide a Vega-Lite object in `spec`.
- `spec_data_forbidden`: remove `data`/`datasets`; Xenix injects the registered dataset.
- `unknown_field`: use exact columns from `data.peek` or `data.query`.
- `dataset_too_large_for_aggregate`: pre-aggregate with `data.query`/`data.transform`.
- `render_failed`: simplify spec or remove unsupported interactive/static features.
- `output_too_large`: reduce marks, dimensions, rows, or pre-aggregate.

The exact payload shape is less important than concrete messages. Still, structured error details would help future UI/tool diagnostics.

### Inductive Reasoning From Existing Tools

`data.query` succeeded because it did not expose raw DuckDB freedom directly:

- registered bindings only
- read-only shape
- single statement
- no direct file scans
- bounded results

`analysis.graph` should copy that pattern:

- registered dataset only
- Vega-Lite grammar
- no spec-owned external data
- bounded render
- artifact id output

## Current Implementation Contract Draft

Input:

```json
{
  "dataset_id": "string",
  "spec": {}
}
```

Success:

- Register an `ArtifactKind.IMAGE`.
- Prefer SVG first.
- MIME type: `image/svg+xml`.
- Payload includes at least:
  - `dataset_id`
  - `artifact_id`
  - graph metadata

Failure:

- Raise `ValidationError` with a message specific enough for retry.
- Prefer messages that include:
  - failing path, such as `spec.encoding.x.field`
  - offending value
  - available columns when field-related
  - recommended next tool if pre-aggregation is needed

## Must-Prove Before Implementation Is Considered Complete

- `vl-convert-python` imports and converts in the PDM environment after dependency addition.
- Graph service renders a valid SVG artifact from a Vega-Lite spec.
- Spec with explicit `data`, `datasets`, or URL data source fails before rendering.
- Wrong field names fail with actionable errors.
- Large aggregate charts do not silently compute on truncated data.
- Provider-facing schema is `{dataset_id, spec}`.
- Tool failure reaches the Agent as provider-visible error payload.
- Image artifact can be resolved and previewed.
- PyInstaller/package smoke can import `vl_convert` and render one minimal chart.

## No Further User Confirmation Needed

No further high-level product confirmation is needed before drafting an implementation plan.

The remaining decisions are engineering details:

- exact row caps and output caps
- exact metadata keys
- exact helper class/function names
- whether to keep a temporary internal helper for old operation tests while migrating
- whether packaging smoke is part of the same implementation slice or the immediate follow-up slice
