# DSL Options

## Evaluation Criteria

- Agent usability: compact enough to write correctly from natural-language chart intent, and preferably already familiar to LLMs.
- Expressiveness: supports common business/data-mining visuals beyond the current enum.
- Validation: service can reject unsafe, oversized, unsupported, or semantically invalid specs before rendering.
- Data boundary: only registered datasets or service-produced query results are visible.
- Rendering fit: works in a PySide6 desktop app and PyInstaller package without online dependencies.
- Artifact fit: produces durable image artifacts compatible with current `artifact://...` previews.
- Maintenance: prefer a real engine over a Xenix-owned visualization grammar.

## Option A - Vega-Lite Spec With Service Sanitizer And Static Converter

Shape:

```json
{
  "dataset_id": "ds_...",
  "spec": {
    "mark": "bar",
    "encoding": {
      "x": {"field": "region", "type": "nominal", "sort": "-y"},
      "y": {"aggregate": "sum", "field": "revenue", "type": "quantitative"},
      "color": {"field": "channel", "type": "nominal"}
    },
    "title": "Revenue by region and channel"
  }
}
```

Pros:

- Uses an existing declarative visualization grammar instead of inventing one.
- Matches a proven grammar-of-graphics mental model: mark + encoding, with optional chart-local transforms.
- Fits Agent generation better than many operation-specific parameter objects and should be familiar to LLMs.
- `vl-convert-python` appears to provide a Python-callable static conversion path from Vega-Lite specs to SVG/PNG, reducing the PySide/WebEngine concern.
- Xenix can still own dataset binding, sanitizer policy, row/category/output bounds, artifact registration, and offline packaging checks.

Cons:

- Full Vega-Lite includes data URLs, inline data, expression strings, selections, parameters, lookups, calculation, and broad transforms that may conflict with Xenix boundaries.
- A sanitizer is still required; raw pass-through without policy would be too broad.
- Transform policy needs careful design so `analysis.graph` remains orthogonal to `data.clean`, `data.query`, and `data.transform`.

Working judgement:

- Best current hypothesis after user feedback.
- This should be described as "Vega-Lite spec accepted under Xenix graph policy", not as a new Xenix DSL.
- Local spike shows `vl-convert-python` can convert Vega-Lite specs to SVG and PNG on Windows/Python 3.14 without adding project dependencies yet.
- The key remaining implementation question is whether it packages cleanly and renders reliably in Xenix's desktop distribution.

## Option B - Raw Full Vega-Lite Pass-Through

Pros:

- Most expressive relative to schema size.
- Upstream JSON schema and examples already exist.
- Strong ecosystem and model familiarity.

Cons:

- Full pass-through can expose URLs, inline data, transforms, interactions, signals, or unsupported features that must be audited.
- Rendering has a plausible Python route through `vl-convert-python`, but packaging and image fidelity must still be proven.
- Raw pass-through makes it harder to preserve registered-dataset-only data access and graph/data-transform orthogonality.

Working judgement:

- Do not expose raw pass-through as the Agent contract.
- Expose Vega-Lite through a Xenix policy layer that replaces `data` with service-bound datasets and rejects unsafe or out-of-scope properties.

## Option C - Altair-As-Compiler

Pros:

- Python-native authoring library built on Vega-Lite grammar.
- Can save charts to HTML and, with the appropriate backend, SVG/PNG.
- Could be useful internally for validation, examples, or smoke tests.

Cons:

- This is not a con about JSON. Agent tool calls should indeed pass serializable JSON, not Python objects.
- Altair's main ergonomic value is Python object authoring; the Agent-facing contract should still be Vega-Lite JSON.
- If `vl-convert-python` can render Vega-Lite specs directly, Altair may be unnecessary in the runtime path.
- Adding Altair only for validation needs a clear payoff.

Working judgement:

- Useful as a reference and possible internal validation aid, but not the core Agent-facing DSL.

## Option D - Plotly JSON Figure Schema

Pros:

- Declarative JSON figure schema exists.
- Plotly has strong interactive chart support and image export APIs.
- Good for business dashboards and rich hover/legend interactions.

Cons:

- Figure JSON is more implementation-shaped than grammar-of-graphics-shaped.
- Static image export commonly brings Kaleido/Chrome considerations.
- Self-contained offline HTML can include large JavaScript payloads.
- The schema can be verbose and harder for an Agent to author minimally.

Working judgement:

- Better for future interactive dashboard artifacts than for replacing `analysis.graph` as a small chart DSL.

## Option E - Keep Operation Catalog, Add Metadata Tool

Pros:

- Minimal implementation risk.
- Easy to validate and test.
- Keeps static SVG path.

Cons:

- Does not solve the user's core goal: more Agent freedom and lower cognitive load.
- Catalog growth remains the main maintenance cost.

Working judgement:

- Not the destination.
- User confirmed no compatibility is required before release, so this should not shape the redesign unless it helps implementation staging internally.

## Option F - `analysis.lambda` Generates Charts

Pros:

- Maximum flexibility for bespoke analysis visuals.
- Already has an execution model for generated analysis code and artifacts.

Cons:

- Higher cognitive and safety burden than a chart DSL.
- Chart intent gets buried in generated Python.
- Not ideal for routine visualizations that should be inspectable as declarative spec.

Working judgement:

- Keep as escape hatch for genuinely custom analysis, not replacement for routine graphing.

## Current Recommendation

Use an engine-first design:

1. Agent-facing `analysis.graph` accepts Vega-Lite-style JSON spec, ideally close enough to official Vega-Lite that examples and model priors transfer directly.
2. Xenix service applies a graph policy layer: inject registered dataset data, reject external data and unsafe/out-of-scope spec features, enforce bounds, then render with a real converter.
3. First renderer candidate: `vl-convert-python` to static SVG, with PNG as a possible fallback/export target.

Initial policy hypothesis:

- Accept ordinary single-view Vega-Lite charts first: mark, encoding, title, width/height, config.
- Do not specially prohibit Vega-Lite transform features merely to enforce tool orthogonality. The Agent can use `data.query` / `data.transform` when durable data shaping is needed and use Vega-Lite transform when it is natural for charting.
- Still reject external data URLs, remote resources, and arbitrary inline model-supplied data because data access belongs to registered datasets.
- Static image slice may ignore or reject interaction-only features if they have no static rendering value or create validation complexity.
- Keep joins, durable derived columns, cleaning, and business metric construction in `data.query`, `data.transform`, `data.clean`, or `analysis.lambda`.

Strong exclusions for first release:

- external URLs
- inline arbitrary data
- remote resources
- unbounded interactive selections
- multi-dataset joins inside graph DSL
- compatibility with old `{operation, params}` provider-facing contract

Data joins and complex shaping should remain owned by `data.query` / `data.transform`, then graph the resulting registered dataset.

## External References Checked

- Vega-Lite official docs describe it as a high-level JSON grammar for interactive graphics with data, transform, mark, encoding, composition, parameter, and config sections: https://vega.github.io/vega-lite/docs/
- Vega-Altair official docs describe it as a Python declarative visualization library built on Vega-Lite: https://altair-viz.github.io/index.html
- `vl-convert` provides Rust, CLI, and Python utilities for converting Vega-Lite specs into static SVG/PNG or Vega specs: https://github.com/vega/vl-convert
- VegaFusion provides Python/Rust/JavaScript tooling for analyzing, accelerating, and scaling Vega visualizations, including Python-side transform execution: https://vegafusion.io/
- Plotly docs expose JSON figure construction, HTML output, and static image export APIs: https://plotly.github.io/plotly.py-docs/generated/plotly.io.html
- Plotly JSON chart schema is a declarative format for creating, saving, and sharing interactive scientific charts: https://plotly.github.io/json-chart-schema/
