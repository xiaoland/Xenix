# Implementation Plan

## Scope

Implement a single Agent-facing graph DSL: Xenix Vega profile. This replaces the current Vega-Lite-facing `analysis.graph` contract instead of adding a second format switch.

## Steps

1. Update dependency and lockfile.
   - Change `vl-convert-python` dependency to the accepted 2.0 RC line.
   - Refresh `pdm.lock`.
   - Verify the project no longer relies on `vl_convert.vegalite_to_svg`.

2. Convert `analysis.graph` contract from Vega-Lite to Xenix Vega profile.
   - Keep provider-facing arguments as `{dataset_id, spec}`.
   - Change schema and description to say Vega, not Vega-Lite.
   - Document concise profile rules in the tool description: Xenix injects the dataset; user-authored `data` or `datasets` are ignored and replaced; `url` resources are rejected; use fields from the registered dataset; use `data.transform` for data preparation.

3. Split service preparation into Vega-specific policy steps.
   - Validate `spec` object and JSON size.
   - Drop user-authored `data` and `datasets` declarations before policy checks.
   - Reject any remaining `url` anywhere in user spec.
   - Validate dimensions using the existing bounds.
   - Validate Vega visual shape through `marks`.
   - Preserve best-effort field scanning for obvious `field`, `groupby`, `fields`, and simple `datum.*` references.

4. Add Xenix-owned Vega data injection and reference patching.
   - Deep-copy user spec.
   - Set default `width`, `height`, and `title`.
   - Inject private top-level data source `__xenix_dataset` with bounded `values`.
   - Patch every ordinary mark to read from `__xenix_dataset` when `from` is absent.
   - Overwrite simple `mark.from.data` to `__xenix_dataset`.
   - Reject complex `from.facet` or non-simple mark data references in the first slice.
   - Patch simple scale domains shaped as `{"field": "..."}` into `{"data": "__xenix_dataset", "field": "..."}`.
   - Overwrite simple scale domains with a `data` key to the private source.
   - Reject complex multi-source domains in the first slice.

5. Preserve graph/data boundary.
   - Continue row cap and truncation behavior for row-level drawing.
   - Replace Vega-Lite aggregate whole-dataset checks with Vega-profile checks that reject user-authored data-level transforms by construction.
   - Keep mark-level `transform` allowed without transform-type special casing.

6. Switch rendering and metadata.
   - Render with `vl_convert.vega_to_svg`.
   - Change output filename suffix from `vegalite` to `vega`.
   - Change metadata `spec_format` to `vega`.
   - Update error messages to say Vega/Xenix Vega profile.
   - Keep artifact kind and MIME type as `IMAGE` / `image/svg+xml`.

7. Update tests.
   - Convert existing Vega-Lite tests into Vega-profile tests.
   - Add a simple Vega bar chart render test.
   - Add a schema test proving no `spec_format`, no operation params, and still `{dataset_id, spec}`.
   - Add tests proving user `data` and `datasets` are ignored and replaced.
   - Add rejection tests for `url`, complex mark dataflow, and complex scale domains.
   - Add a wordcloud render test that checks actual text positioning and non-zero font size.
   - Keep artifact registration coverage.

8. Update smoke and docs.
   - Update app smoke graph spec to Vega.
   - Add smoke coverage for Vega wordcloud.
   - Update PRD, Product TDD, Unit TDD, and deployment docs from Vega-Lite to Xenix Vega profile.

9. Verify.
   - `pdm run pytest tests/test_analysis_graph.py -q`
   - `pdm run pytest tests/test_analysis_graph.py tests/test_agent_harness_first_slice.py::test_agent_harness_model_metadata_exposes_catalog_without_train_enums -q`
   - `pdm run python -m compileall -q src/xenix/services/analysis_graph.py src/xenix/services/agent/tools.py src/xenix/app.py`
   - If dependency or packaging behavior changed, run the packaging smoke path already used by the project.
