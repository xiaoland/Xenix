# Result

## Implemented

- Replaced the Agent-facing `analysis.graph` contract with a single Xenix Vega profile.
- Kept provider-facing arguments as `{dataset_id, spec}`.
- Removed Vega-Lite renderer usage from source, tests, and durable docs.
- Upgraded `vl-convert-python` to `2.0.0rc1` and kept lockfile churn scoped to that package.
- Added service-owned Vega data injection through a private data source.
- Ignored and replaced user-authored Vega `data` and `datasets` declarations.
- Rejected external `url`, non-mark-level transforms, complex mark dataflow, and complex scale domains.
- Kept mark-level transforms allowed without transform-type special casing.
- Switched rendering to `vl_convert.vega_to_svg`.
- Added Vega wordcloud verification that proves non-zero positioned text instead of only checking for an SVG string.
- Added service-side wordcloud SVG validation so a syntactically valid but semantically blank wordcloud fails with a repair hint.
- Kept the Agent-facing wordcloud prompt concise and moved detailed wordcloud authoring guidance into wordcloud-specific failure messages.
- Added pre-render wordcloud shape validation for grouped `encode.enter` / `encode.update`, `transform.text`, `transform.fontSize`, and bounded `fontSizeRange`.
- Adjusted wordcloud placement validation to avoid failing tiny wordclouds when only a small absolute number of terms cannot be placed.
- Updated app smoke to cover both ordinary Vega rendering and wordcloud rendering.
- Expanded the provider-facing `spec` schema with first-level Vega property descriptions and required non-empty `marks`.

## Verification

- `pdm run pytest tests/test_analysis_graph.py tests/test_agent_harness_first_slice.py::test_agent_harness_model_metadata_exposes_catalog_without_train_enums -q`
- `pdm run python -m compileall -q src/xenix/services/analysis_graph.py src/xenix/services/agent/tools.py src/xenix/app.py`
- `pdm run smoke`
- `pdm run pytest tests/test_analysis_graph.py -q`
- `pdm run pytest tests/test_agent_harness_first_slice.py::test_agent_harness_model_metadata_exposes_catalog_without_train_enums -q`
- `pdm run python -m compileall -q src/xenix/services/analysis_graph.py src/xenix/services/agent/tools.py tests/test_analysis_graph.py`
- `rg -n "Vega-Lite|vegalite|vega-lite|vegalite_to_svg|Vega Lite" src tests docs pyproject.toml --glob '!tasks/**' --glob '!dist/**' --glob '!build/**'`

## Notes

- The private injected data source name is intentionally not exposed in the tool schema.
- `analysis.graph` remains a static SVG artifact producer; interactive Vega behavior is not promoted to a user-facing artifact contract.
- Full packaged smoke was not run in this implementation pass.
