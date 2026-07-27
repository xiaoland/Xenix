# Revenue by Region Graph Benchmark Case

Case ID: `analysis.revenue_by_region_chart`

## Purpose

This is the smallest second case that has a different product-output type from
the April cleaning case. It measures whether a real AgentHarness × model cell
can produce a useful final visualization through the same public AgentHarness
boundary. Tool discovery, Tool feedback/recovery, rendering, and Artifact
registration are mechanisms observed separately, not the task outcome.

## Input and User Intent

- A committed, hash-pinned four-row CSV with `region`, `amount`, `score`, and
  `date` columns.
- One isolated Thread and explicit configured model key.
- One user turn in ordinary Chinese: “请用图表呈现各地区收入对比，选择最合适的
  图表形式并简述发现。”

The fixture contains one row per region, so chart correctness does not require
an upstream aggregation transform. The case does not provide a Vega-Lite spec
or prescribe Tool calls to the model.

## Terminal Product Locator

The case scans canonical messages newest-first for a successful ToolResult
whose direct value contains a non-empty `artifact_id`. It resolves that stable
reference through public `ArtifactService.resolve_uri()` and accepts only an
existing, ready IMAGE artifact with MIME type `image/svg+xml` whose absolute
path is under the cell's isolated runtime. The reference and resolved details
remain in process only.

## Candidate Balanced Semantic Contract (Pending Implementation)

The original structural check set is superseded. SVG validity, Artifact
registration, graph metadata, source preservation, and temporary-runtime
confinement do not prove that the Agent completed the chart task; they belong
to Tool/integration tests or benchmark-run integrity checks.

The case must instead inspect only the final SVG Artifact against an
independent fixture oracle. It deliberately specifies a business question but
leaves chart type, title, axes, sorting, colors, labels, and Tool plan to the
model.

The case uses a rubric-based, pointwise LLM-as-a-Judge as its primary semantic
evaluator. It builds an independent, privacy-reviewed judge packet from only:

1. the ordinary-language user intent;
2. compact fixture facts: `North`, `South`, `West`, and `East` are the valid
   regions, and their revenue relation is `West > East > South > North`; and
3. a bounded final-SVG semantic extract (visible text plus accessibility labels
   where present).

The judge returns structured `pass` / `partial` / `fail` / `inconclusive` and
scores: (a) whether the visual answers the regional-revenue comparison, (b)
whether it is grounded in those facts without evident fabrication, and (c)
whether its semantic labels/content are intelligible to a non-technical user.
It may accept a bar, point,
slice, or another suitable visual. It must not demand literal `region`/
`amount` field keys, a title, an axis orientation, raw-cell equality, SVG DOM
order, or pixel coordinates.

The SVG's final accessibility projection is the preferred read-only evidence
surface, not expected truth. Artifact paths/IDs, Tool arguments/results,
`analysis_graph` metadata, Assistant prose, and internal Vega-Lite
specifications are all out of scope. If evidence is too weak for a responsible
verdict, the judge returns `inconclusive`; a renderer/Tool failure must not be
misreported as a poor Agent result.

Judge identity, rubric version, availability, usage, retries, and elapsed time
are evaluation metadata. The judge runs independently after the subject turn,
with no Tools, and its cost/latency never contribute to the AgentHarness cell's
token or time measurements.

The current judge transport is text-only, so this case deliberately does not
claim to score colors, geometry, or other pixel-level aesthetics. That requires
a future vision-capable Artifact-evidence extension.

## Prerequisites and Integrity, Not Case Outcome

- Canonical completion and resolving an Artifact are assessment prerequisites:
  their absence makes the semantic checks fail with a bounded reason, not a
  separate task-quality assertion.
- Fixture/settings fingerprints, source preservation, report privacy, and
  temporary-home confinement are benchmark-run integrity checks. A breach
  invalidates the measurement and must not be folded into model/case quality.
- XML parseability, non-empty paths, renderer validity, and Artifact
  registration remain `analysis.graph` service/Tool integration coverage.

The outcome reads final product state only. It does not match Assistant prose,
require `analysis.graph` by name, inspect Tool arguments/order, or serialize an
artifact id/path/SVG into the benchmark result.

## Performance Interpretation

Common metrics remain the measurements: tokens, latency, sampling rounds,
messages, Tool calls/results, and retries. `derived_dataset_count` may be zero
and `terminal_shape` is `null`; neither is a defect for a chart-output case.
