# Impact Handshake Draft

This is not approved for implementation yet. It is the current high-level confirmation draft after user feedback on engine-first design.

## Address And Object

Likely code/doc targets after explicit implementation start:

- `src/xenix/services/analysis_graph.py`
  - Replace operation-specific graph rendering with a Vega-Lite policy/sanitizer, dataset injector, and static renderer integration.
- `src/xenix/services/agent/tools.py`
  - Change `analysis.graph` provider-facing schema and handler validation.
- `tests/test_analysis_graph.py`
  - Replace operation-enum expectations with Vega-Lite spec policy and rendering contract tests.
- Agent harness tests
  - Update tool schema and contextual exposure expectations if schema shape changes.
- Durable docs
  - Update runtime boundary and Agent Harness contract after implementation is verified.

## State Diff

From:

- `analysis.graph` accepts `{dataset_id, operation, params?}`.
- Chart type is selected from a fixed operation list.
- Service hand-renders SVG for each operation.

To:

- `analysis.graph` accepts `{dataset_id, spec}` where `spec` is Vega-Lite JSON under Xenix graph policy.
- The old operation contract is removed, with no compatibility requirement.
- Service validates/sanitizes the Vega-Lite spec, injects only registered dataset data, enforces bounds, renders a static image artifact, and returns metadata/warnings.

## Blast Radius Forecast

- Agent tool schema and provider-facing prompt behavior.
- Graph service validation and artifact metadata shape.
- Existing tests for graph operation names and metadata.
- Any assistant/system prompt text that explains artifact image links and graph tool semantics.
- Potential packaging smoke if a new renderer dependency is introduced.
- New dependency risk if adopting `vl-convert-python`, Altair, VegaFusion, Plotly, or any renderer support package.

## Invariants Check

Must remain unchanged unless explicitly decided:

- Graphing uses registered datasets, not arbitrary file paths from tool arguments.
- `analysis.graph` returns an image artifact id for user-openable chart output.
- The Chatbot artifact rendering contract remains `artifact://<artifact_id>`.
- `analysis.profile` remains descriptive text/structured evidence, not graph rendering.
- `data.query` / `data.transform` remain the owner for SQL joins and complex data shaping.
- `data.clean` remains the owner for cleaning and normalization.
- `analysis.graph` does not own durable data transformation.
- Agent tool exposure remains contextual: analysis tools appear only after a dataset exists in the thread.
- No external network dependency is required to render a chart.

## Verification Plan

Before implementation:

- Confirm first-release engine path: Vega-Lite spec plus `vl-convert-python`.
- Confirm static SVG as the first output format, with PNG available for smoke/export if useful.
- Confirm sanitizer policy for data source injection, external resource rejection, size bounds, and static-only behavior.

During implementation:

- Unit tests for spec policy validation and rejection paths.
- Unit tests for supported marks/channels/aggregates.
- Artifact registration tests for SVG/image output.
- Tool schema tests for compactness and required keys.
- Regression tests for contextual tool exposure.
- `compileall` and targeted pytest.

If new dependencies are added:

- Update packaging config as needed.
- Run packaged smoke or add a rendering smoke check.

## Confirmation Questions

Confirmed:

- First spike should evaluate `vl-convert-python`.
- Provider-facing schema should be `{dataset_id, spec}`.
- No compatibility with old `{operation, params}` is required.
- Vega-Lite transform features do not need to be specially prohibited for orthogonality.

Still open:

- Exact sanitizer/policy scope for external data, inline data, resource URLs, dimensions, output size, and interaction-only features.
- Whether to add a formal dependency now or keep one more packaging-only spike before implementation.
