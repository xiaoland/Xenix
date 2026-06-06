# Discussion Log

## 2026-06-05 - Packet Created

User intent:

- Redo `analysis.graph`.
- Purpose remains chart generation.
- Use a DSL idea similar to `data.query`.
- Give the Agent more freedom and reduce cognitive burden.
- User's initial research points to Vega-Lite-style declarative visualization DSL.
- Keep this as a large, discussion-driven poly-file task packet.

Evidence captured:

- Existing `analysis.graph` is operation-enum based and hand-renders SVG.
- Existing `data.query` is a strong local precedent for an expressive DSL with service-owned validation and bounds.
- Vega-Lite official docs support the mark/encoding/transform grammar direction.
- Altair is Python-facing and Vega-Lite-based, but does not remove the render/export decision.
- Plotly JSON is declarative and rich but heavier and more implementation-shaped than a grammar-of-graphics spec.

Current working recommendation:

- Prefer an Xenix-owned constrained Vega-Lite-like graph spec.
- Keep static image artifact output first.
- Defer interactive HTML, browser/WebEngine rendering, full Vega-Lite pass-through, and expression strings.

Open confirmation points:

- Exact DSL name and input key: `spec`, `graph_spec`, or another term.
- Renderer strategy for first slice.

## 2026-06-05 - User Feedback: Engine First

User feedback:

- Prefer an existing complete engine, like DuckDB for SQL, over a Xenix-owned DSL.
- Concern: a custom Xenix DSL adds extra LLM burden.
- The strongest concern with full Vega-Lite pass-through is Python/PySide rendering friendliness.
- Do not mix data transformation into `analysis.graph`; `data.clean` and `data.transform` already own that space.
- The earlier note that "Agent would still likely pass JSON, not Python objects" is not a valid con; Agent should indeed pass JSON-like serializable tool arguments.
- No compatibility is required because the software has not been released.

Packet update:

- Shifted recommendation from Xenix-owned Vega-Lite-like DSL to engine-first Vega-Lite spec under Xenix policy.
- Added `vl-convert-python` / `vl-convert` as a key rendering candidate because it converts Vega-Lite specs to static SVG/PNG from Python.
- Reframed Altair: useful reference/internal helper, but not needed merely to turn Agent JSON into charts if direct Vega-Lite conversion works.
- Removed compatibility as a design driver.
- Added graph/data-transform orthogonality rule.

Current working question:

- How strict should the transform boundary be? Full rejection of Vega-Lite `transform` is cleanest, but common charts need chart-local reductions such as aggregate/bin/timeUnit/sort. The likely boundary is to allow visual reductions and reject broader data preparation/expression transforms.

## 2026-06-05 - Confirmed First Spike

User confirmations:

- Vega-Lite transform features do not need to be specially prohibited for tool orthogonality.
- Provider-facing schema should be `{dataset_id, spec}`.
- First spike is approved.

Local spike:

- Current PDM environment uses Python 3.14 and has no `pip` module.
- Installed `vl-convert-python` 1.9.0 into `%TEMP%/xenix-vl-convert-spike` using system Python, without editing project dependencies.
- Verified `vl_convert.vegalite_to_svg` on a bar chart.
- Verified `vl_convert.vegalite_to_svg` and `vl_convert.vegalite_to_png` on a line chart with top-level Vega-Lite `transform`.
- PNG file rendered visibly when inspected.
- One `tiny_skia::painter` warning appeared during PNG conversion, but output was valid.

Sub-agent documentation research:

- `vl-convert-python` supports `vegalite_to_svg`, `vegalite_to_png`, and `vegalite_to_vega`.
- It is described by official docs as self-contained/dependency-free, not requiring Node, browser, or network for ordinary conversion.
- It is used in the Altair/VegaFusion ecosystem as a static conversion backend.
- PyInstaller packaging needs explicit smoke validation because official PyInstaller-specific proof was not found.

## 2026-06-05 - Sanitizer Policy Question

User question:

- If tool parameters are already `{dataset_id, spec}`, why is sanitizer/policy needed?

Answer recorded:

- `dataset_id` identifies the intended registered dataset, but Vega-Lite `spec` can still contain its own `data`, `datasets`, `url`, or nested data overrides.
- The policy layer is not a custom DSL. It is the equivalent of SQL validation/binding in `data.query`: Xenix binds the registered dataset and prevents hidden data/resource access or unbounded rendering.
- The preferred posture is strict data boundary and loose visualization grammar.

Added:

- `sanitizer-policy.md` with proposed policy levels, pipeline, and row-handling decision.

## 2026-06-05 - Row Policy Confirmed

User agreed with the sanitizer/policy direction.

Confirmed:

- Use the hybrid row strategy.
- Row-level charts may use bounded service-owned sampling/truncation with explicit metadata.
- Aggregate or whole-dataset semantic charts should not silently aggregate truncated data; require pre-aggregation through `data.query` / `data.transform` when the dataset is too large.

Next likely posture:

- Move from `Explore` to `Solidify`.
- Turn the accepted direction into an implementation contract: request/result types, sanitizer behavior, render path, metadata, tests, and packaging smoke.

## 2026-06-05 - Multi-Perspective Review

User asked for a self-directed review using multiple thinking modes and sub-agent support.

Actions:

- Spawned code-mapper sub-agent for a read-only integration-risk review.
- Performed local review of `analysis.graph`, Agent tool schema/handler, ArtifactService, Harness failure propagation, and existing tests.
- Added `solidify-review.md`.

Conclusion:

- Direction remains sound.
- No further high-level user confirmation is needed before implementation planning.
- The dominant risk is synchronized contract migration and packaging proof, not chart grammar capability.

Important evidence:

- Tool failures already become provider-visible failed tool results through `AgentHarnessService`.
- Therefore graph failures should focus on clear `ValidationError` messages that help the Agent retry.
- The artifact path can remain stable: `ArtifactKind.IMAGE`, `image/svg+xml`, and `artifact_id` in payload.

## 2026-06-05 - Implementation Completed

Implemented after user explicitly said start.

Key implementation notes:

- `analysis.graph` now accepts `{dataset_id, spec}`.
- `spec` is Vega-Lite JSON.
- `vl-convert-python` renders static SVG.
- Xenix rejects spec-owned data sources and injects the registered dataset.
- Packaged windowed rendering needed a temporary hidden Windows console around `vl_convert` calls; minimal PyInstaller experiments proved this was necessary.
- Packaged smoke now covers Vega-Lite graph rendering.

Verification summary is in `result.md`.

## 2026-06-06 - Policy Cap And Durable Runtime Note

User requested:

- Record the PyInstaller windowed `vl-convert-python` temporary console workaround in durable docs if missing.
- Treat safe render cap as part of `analysis.graph` sanitizer/policy.
- Raise the safe direct render row cap from 5,000 to 10,000.
- Show current sanitizer/policy.

Updates:

- `docs/40-deployment/development.md` now records the packaged/windowed render failure mode and the temporary hidden console workaround.
- `docs/20-product-tdd/runtime-boundaries.md` now states the active `analysis.graph` render policy, including the 10,000-row direct injection cap.
- `src/xenix/services/analysis_graph.py` now uses `_MAX_RENDER_ROWS = 10_000`.
