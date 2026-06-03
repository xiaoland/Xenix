# Implementation Plan

## Objective & Hypothesis

- Objective: implement the MVP `analysis.lambda` Agent tool.
- Hypothesis: a local subprocess worker with a narrow JSON request/result protocol is enough for accidental bad-code containment while preserving analyst flexibility.

## Confirmed MVP Defaults

- Tool name: `analysis.lambda`.
- Execution: one-off, no user approval, local subprocess first.
- Function shape: `def analyze(ctx, inputs, params) -> dict`.
- Output: any JSON-serializable `dict`, returned as `result.output`.
- Persistence: generated code and manifest live in tool-call records only.
- Threat model: accidental bad Agent code only, not hostile code.
- Libraries: `pandas`, `numpy`, `matplotlib`/`plt`, `scipy`, `statsmodels`, `sklearn`.

## Default Budgets

- Timeout: 20 seconds.
- Dataset count: 3.
- Input rows per dataset: 100,000.
- Output JSON size: 256 KiB.
- Artifact count: 5.
- Artifact size: 5 MiB each.
- DataFrame artifact rows: 50,000.

## Address And Object

- New service: `src/xenix/services/analysis_lambda.py`
- New worker module: `src/xenix/services/analysis_lambda_worker.py`
- Agent tool registry: `src/xenix/services/agent/tools.py`
- Tests: new `tests/test_analysis_lambda.py`, plus targeted registry/context exposure assertions if needed
- Task docs: `tasks/agent-python-analysis-runtime/`

## State Diff

- From: Agent can only use deterministic `analysis.profile` / `analysis.graph` and other fixed tools.
- To: Agent can execute a one-off typed analysis lambda over registered datasets and create bounded artifacts through `ctx.artifact.create(...)`.

## Blast Radius Forecast

- Agent provider schema grows by one analysis tool.
- Tool availability remains dataset-gated through existing `analysis.*` rule.
- Artifact registration path expands to include lambda-generated files.
- No storage schema migration expected.

## Invariants Check

- No arbitrary local path is exposed in tool args or tool result.
- Worker result contains only JSON and temporary artifact descriptors.
- Parent service registers final artifacts through `ArtifactService`.
- Tool payload stores code and manifest; reusable operation storage is not introduced.
- Existing `analysis.profile` and `analysis.graph` behavior remains unchanged.

## Verification

- Service-level test: lambda returns JSON output.
- Artifact test: lambda creates DataFrame, SVG, bytes, and matplotlib figure artifacts.
- Validation tests: non-dict return, oversized output, unknown dataset, too many datasets, timeout.
- Tool registry test: schema contains `analysis.lambda`; exposed only when dataset context exists through existing `analysis.*` rule.
- Run: targeted pytest for analysis lambda/profile/graph and relevant harness exposure tests.

## Implementation Result

- Added `AnalysisLambdaService` and `analysis_lambda_worker`.
- Added `analysis.lambda` to the Agent tool registry and presentation metadata.
- Added local subprocess execution with timeout, cancellation polling, output-size checks, dataset count limits, row caps, artifact count/size caps, and import allow-listing.
- Added `ctx.artifact.create(...)` support for pandas DataFrame, SVG/string, bytes, and matplotlib Figure content.
- Parent process registers lambda artifacts through `ArtifactService` and rewrites placeholder artifact URIs in `result.output`.
- Added `statsmodels` to runtime dependencies because the confirmed lambda library set includes it.
- Updated durable PRD/runtime/Agent Harness docs.

## Verification Executed

- `pdm run pytest tests/test_analysis_lambda.py -q`
- `pdm run python -m compileall -q src tests scripts`
- `pdm run pytest tests/test_analysis_lambda.py tests/test_analysis_profile.py tests/test_analysis_graph.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py::test_agent_harness_stream_filters_tools_by_thread_files -q`
- `git diff --check`

