# Implementation Plan

## Objective & Hypothesis

- Objective: replace `analysis.graph` operation dispatch with `{dataset_id, spec}` Vega-Lite rendering through `vl-convert-python`.
- Hypothesis: keeping Xenix policy focused on registered dataset injection, bounded rendering, actionable failures, and artifact registration will preserve the current product purpose while giving the Agent a complete visualization grammar.

## Guardrails Touched

- Service boundary: `AnalysisGraphService` owns graph rendering.
- Agent Harness boundary: `AgentToolRegistry` owns provider-facing tool schema and tool execution.
- Artifact boundary: graph output remains `ArtifactKind.IMAGE` and `image/svg+xml`.
- Data boundary: graphing reads only registered datasets resolved from `dataset_id`.
- Packaging boundary: `vl-convert-python` must import and render inside the project environment.

## Work Slices

1. Add `vl-convert-python` dependency.
2. Rewrite graph service request/result around `spec`.
3. Add policy validation:
   - `spec` object only.
   - reject `data`, `datasets`, and data/resource URLs.
   - bound spec size, dimensions, render output size, and rows.
   - validate common field references.
   - hybrid row handling for aggregate/whole-dataset specs.
4. Update Agent tool schema/handler and artifact metadata.
5. Replace graph tests with Vega-Lite spec, failure, artifact, and schema tests.
6. Update durable docs after verified behavior.
7. Run target tests and render/import smoke.

## Verification

- `pdm run python -c "import vl_convert; ..."`
- `pdm run pytest tests/test_analysis_graph.py -q`
- Agent schema/exposure target tests.
- `pdm run python -m compileall -q src/xenix/services/analysis_graph.py src/xenix/services/agent/tools.py`
- `git diff --check`

## Outcome

- Implemented. See `result.md`.
