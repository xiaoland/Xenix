# Result

## Objective & Hypothesis

- Objective: replace `analysis.graph` operation dispatch with `{dataset_id, spec}` Vega-Lite rendering through `vl-convert-python`.
- Hypothesis: a real visualization engine plus Xenix-owned data binding, validation, failure feedback, and artifact registration gives the Agent more expressive charting while preserving service boundaries.

## Implemented

- Added `vl-convert-python` as a runtime dependency.
- Replaced hand-rendered chart operations in `AnalysisGraphService` with Vega-Lite static SVG rendering.
- Changed `analysis.graph` provider-facing schema to `{dataset_id, spec}`.
- Removed compatibility with old `{operation, params}`.
- Added graph policy:
  - reject spec-owned `data`, `datasets`, and `url`.
  - inject registered dataset records as Vega-Lite `data.values`.
  - validate common field references and report available columns.
  - cap spec size, chart dimensions, render rows, and SVG output size.
  - reject too-large aggregate/whole-dataset charts and ask Agent to pre-aggregate through `data.query` / `data.transform`.
  - allow row-level truncation with explicit metadata warnings.
- Kept graph output as `ArtifactKind.IMAGE` / `image/svg+xml`.
- Added `--smoke-test` coverage for Vega-Lite SVG rendering.
- Added a Windows frozen/windowed runtime workaround for `vl-convert-python`: packaged windowed executables need a temporary hidden console while calling the native converter. A minimal PyInstaller spike proved console builds worked, windowed builds hung without `AllocConsole`, and windowed builds succeeded with `AllocConsole` + hidden console.
- Updated product/runtime/Agent Harness docs.
- Updated tests for service behavior, failure feedback, artifact registration, and tool schema.

## Verification

Executed:

- `pdm add vl-convert-python`
- `pdm run python -c "import vl_convert as vlc; ... vegalite_to_svg ..."`
- `pdm run pytest tests/test_analysis_graph.py -q`
- `pdm run pytest tests/test_analysis_graph.py tests/test_agent_harness_first_slice.py::test_agent_harness_model_metadata_exposes_catalog_without_train_enums -q`
- `pdm run smoke`
- `pdm run pytest tests/test_analysis_graph.py tests/test_analysis_profile.py tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py::test_agent_harness_stream_filters_tools_by_thread_files tests/test_data_transform.py -q`
- `pdm run python -m compileall -q src tests scripts`
- `pdm run package`
- `pdm run smoke-package`
- `git diff --check`

Final verification status:

- 42 relevant tests passed.
- Development smoke passed.
- PyInstaller package build passed.
- Packaged smoke passed and now includes Vega-Lite graph rendering.
- `git diff --check` passed.

## Notes

- Existing unrelated workspace changes remain untouched:
  - `.gitignore`
  - `.vscode/tasks.json`
  - `tasks/issue-97/data-pre-process.py`
  - `tasks/public-beta-runtime-telemetry/`
- `pdm.lock` was normalized back to LF after PDM wrote CRLF, because `git diff --check` treated CRLF as trailing whitespace.
