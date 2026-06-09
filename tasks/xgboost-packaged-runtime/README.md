# XGBoost Packaged Runtime Diagnosis

## Objective & Hypothesis

Diagnose why a distributed `dist/xenix/xenix.exe` fails when using XGBoost with a missing-library error.

Initial hypothesis: the PyInstaller bundle starts successfully but does not collect XGBoost's native runtime library or import-time metadata needed by `xgboost` when model execution imports `XGBRegressor` / `XGBClassifier`.

## Guardrails Touched

- Reality route: evidence before code/config mutation.
- Packaging owner: `xenix.spec`, `scripts/package_app.py`, `scripts/verify_packaged_smoke.py`, `docs/40-deployment/development.md`.
- ML owner: `src/xenix/services/ml/models/`.

## Verification

- Inspect current PyInstaller spec and packaged smoke coverage.
- Reproduce or approximate packaged import failure with `dist/xenix/xenix.exe`.
- Validate that a fix collects XGBoost runtime assets and that packaged smoke covers XGBoost import/model creation.

## Current Understanding

- User observed failure only after distributing packaged `xenix.exe`.
- Current durable packaging docs mention DuckDB native-library troubleshooting, but not XGBoost.
- XGBoost imports are lazy inside ML model services, so normal startup smoke may pass even if XGBoost packaging is incomplete.
- Local `pdm run smoke-package` passes against `dist/xenix/xenix.exe`.
- Current bundle has LightGBM runtime data (`lightgbm/bin/lib_lightgbm.dll`) but no collected `xgboost` directory or `xgboost/lib/xgboost.dll` file under `dist/xenix/_internal`.
- PyInstaller analysis includes XGBoost Python modules in `PYZ-00.toc`, but `COLLECT-00.toc` does not include XGBoost's native DLL.
- Installed `pyinstaller-hooks-contrib` has `hook-lightgbm.py`, but no equivalent XGBoost hook. Local `collect_dynamic_libs("xgboost")` resolves `.venv/Lib/site-packages/xgboost/lib/xgboost.dll`.
- Durable lesson promoted to `docs/40-deployment/development.md`: packaged verification must exercise ML/data-science runtime paths that load native libraries, compiled extensions, metadata, or data files.

## Implemented Change

- `xenix.spec` explicitly collects XGBoost dynamic libraries and small package data (`VERSION`, `py.typed`).
- `src/xenix/app.py` smoke checks now exercise `XGBoostRegressionService` with a tiny in-memory fit/predict, which triggers XGBoost runtime loading inside the packaged app.
- `scripts/verify_packaged_smoke.py` default timeout increased from 30 seconds to 90 seconds because packaged smoke now loads native ML runtime code.

## Verification Results

- `pdm run smoke` passed.
- `pdm run python -m compileall src scripts` passed.
- `pdm run package` passed.
- `dist/xenix/_internal/xgboost/lib/xgboost.dll` exists after packaging.
- `build/xenix/COLLECT-00.toc` includes `xgboost/lib/xgboost.dll`.
- `pdm run smoke-package` passed against `dist/xenix/xenix.exe`.
- `pdm run pytest tests/test_main.py::test_smoke_test_bootstraps_runtime_in_fresh_app_home tests/test_build_info.py` passed.

## Next Step

Distribute the rebuilt `dist/xenix/` onedir bundle or regenerate the distribution ZIP so users receive the collected XGBoost DLL.
