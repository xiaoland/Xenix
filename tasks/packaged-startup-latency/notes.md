# Packaged Startup Latency Diagnosis

## Objective & Hypothesis

- Objective: explain why the packaged Windows build appears to start from `scripts/run_dev.py` and why first startup spends unusually long before and during splash.
- Initial hypothesis: packaged entrypoint is currently the development wrapper, and startup blocks on heavy runtime imports after splash creation; pre-splash delay may come from PyInstaller bootloader/module bootstrap before `QApplication` and `StartupSplash` exist.

## Guardrails Touched

- Reality / Diagnose: gather evidence before code or durable-doc mutation.
- Durable owners likely involved if a fix is approved later: `xenix.spec`, `scripts/run_dev.py`, `src/xenix/app.py`, packaging docs/tests.

## Verification

- Static trace: packaging spec entrypoint, bootstrap call graph, splash stage transitions, import locations.
- Runtime trace if needed: launch packaged exe with isolated `XENIX_APP_HOME`, compare time-to-process, time-to-splash, and app logs.

## Current Understanding

- `xenix.spec` uses `scripts/run_dev.py` as the PyInstaller Analysis script.
- `run_dev.py` inserts `<project>/src` into `sys.path`, dispatches `--analysis-lambda-worker`, then imports `xenix.main`.
- `src/xenix/main.py` imports `xenix.app` at module import time. `xenix.app` imports PySide6, observability, logging, resources, and splash classes before `build_main_window()` can create `QApplication` or show splash.
- `build_main_window()` shows splash, then enters `StartupStage.LOADING_RUNTIME` while `_load_runtime_imports_with_events()` imports the service runtime in one background thread.
- `_load_runtime_imports()` first imports `xenix.services.agent`; `agent.__init__` imports `agent.tools`; `agent.tools` imports analysis/data/ML services and `ml.registry`; `ml.registry` imports all model modules at top level, which pulls in pandas/scikit-learn/scipy/numpy-oriented dependencies.
- Source import timing on this machine:
  - `import xenix.main`: ~5.18s before any splash can exist.
  - `import xenix.services.agent`: ~22.20s on the first observed run, matching the user's long "Loading runtime components..." stage.
  - A hot-cache `-X importtime` subprocess later reduced `xenix.services.agent` to ~3.83s, indicating cold-cache/DLL/security-scanner effects amplify the same import chain.
- Current `dist/xenix` is an onedir bundle with about 1,909 files and 466 MB. Largest payloads include `vl_convert`, DuckDB, PySide6 Qt DLLs, scipy/numpy, grpc, LightGBM, and other native binaries.
- Packaged `--smoke-test` with isolated `XENIX_APP_HOME` completed successfully in ~6.27s on a warm run; this is not representative of a cold interactive splash run, but proves the packaged executable itself works and startup logs only appear after much of bootstrap has already completed.
- External research:
  - PyInstaller official docs: onedir apps still start through the PyInstaller bootloader, which prepares a temporary Python environment and starts the interpreter; onefile adds extraction overhead, but Xenix is already onedir.
  - PyInstaller docs expose `--debug imports`, `--debug bootloader`, and `--debug noarchive`; these are directly useful for building a diagnostic package that separates bootloader time from Python import time.
  - PyInstaller docs also note UPX is Windows-only in current usage and can be disabled with `--noupx`; Qt plugins are known UPX-sensitive even though PyInstaller tries to exclude many automatically.
  - PyInstaller's own splash feature is meant to show before bootloader/extraction work, but it is Tcl/Tk-based and has warnings for onedir apps. Xenix's Qt splash cannot appear until Python and PySide6 imports have completed.
  - Qt for Python docs and community posts focus mostly on PySide6/PyInstaller plugin deployment. They support checking platform/plugins/translations, but do not explain the observed 20s runtime-import delay by themselves.
  - Community reports repeatedly identify first-run OS security scanning, large Qt/numpy/scipy-style bundles, and network/shared-drive/WSL filesystems as causes of 10s+ packaged startup delays.

## Collected Evidence

Artifacts:

- `tasks/packaged-startup-latency/startup_probe.py`: repeatable probe for bundle inventory, source import timing, packaged smoke timing, copied-dist first-run timing, and startup timing line parsing.
- `tasks/packaged-startup-latency/artifacts/20260609-052548/report.md`: baseline before adding startup timing instrumentation.
- `tasks/packaged-startup-latency/artifacts/20260609-053000-copydist-abs/report.md`: copied-dist first-run probe with absolute runtime paths.
- `tasks/packaged-startup-latency/artifacts/20260609-053000-copied-warm/report.md`: same copied dist after first run, proving warm path recovery.
- `tasks/packaged-startup-latency/artifacts/source_timing_latest.txt`: source smoke with `XENIX_STARTUP_TIMING=1`.
- `tasks/packaged-startup-latency/artifacts/20260609-053500-instrumented-package/report.md`: rebuilt packaged bundle with startup timing instrumentation.

Findings:

- Warm packaged smoke before instrumentation: 5.6-6.2s total; first application log at 3.1-3.4s.
- Copying the same `dist/xenix` tree to a fresh path caused the next first run to take 18.8s; first application log appeared at 15.5s.
- Running the copied tree again recovered to 5.8-5.9s, with first log at 3.1-3.4s. This strongly supports Windows first-scan/cold-path overhead as the explanation for the user's 10s+ pre-splash gap after receiving a packaged build.
- Source smoke with `XENIX_STARTUP_TIMING=1`: `run_dev.import_xenix_main` ~0.69s, `runtime_import.module module=xenix.services.agent` ~3.62s, `storage.bootstrap` ~0.32s, total `build_main_window` ~4.37s.
- Rebuilt packaged bundle with timing instrumentation:
  - First run after rebuilding `dist/xenix`: total process ~18.9s; first log at 16.0s; `runtime_import.module module=xenix.services.agent` ~12.53s.
  - Second run from the same path: total process ~5.6s; first log at 3.17s; `runtime_import.module module=xenix.services.agent` ~2.30s.
  - Copied rebuilt bundle first run: total process ~20.0s; first log at 17.2s; `runtime_import.module module=xenix.services.agent` ~13.25s.
- Source isolated subimport probe at `tasks/packaged-startup-latency/artifacts/source_agent_subimports_latest.txt` showed that importing `xenix.services.agent.conversation_store`, `chatbot_events`, `providers`, `settings`, `harness_service`, or `tools` all costs ~3.45-4.52s because Python executes `xenix.services.agent.__init__` first. The agent package's eager re-export surface prevents cheap submodule imports.
- Source isolated imports for direct service/model modules: `analysis_graph` ~1.54s, `analysis_profile` ~1.53s, `data_transform` ~1.58s, `dataset_service` ~1.26s, `ml.registry` ~5.40s, `ml.models.classification` ~3.60s, `ml.models.regression` ~2.98s. These results reinforce that ML registry/model import is the heaviest code-owned import family.
- Qt plugin debugging did not produce plugin-search evidence in the current windowed package; source Qt probe showed PySide6 import ~0.145s and `QApplication` creation ~0.124s. Qt plugin loading is not the primary suspect for the observed long delay.
- Current bundle size is ~445MB and ~1,910 files. Largest payloads include `vl_convert` 79MB, DuckDB 35.5MB, PySide6 OpenGL/Qt DLLs, numpy/scipy OpenBLAS DLLs, grpc, and many `.pyd` files. This bundle shape is consistent with Windows first-run scanning overhead.
- Current rebuilt packaged smoke exits 1 after startup due to a separate XGBoost packaged-runtime failure: `xgboost/lib/xgboost.dll` is absent from `dist/xenix/_internal/` even though local `.venv` has the 143.6MB DLL. This failure occurs after `Xenix native shell started`, so startup timing remains valid. If XGBoost is correctly bundled, package size and first-scan cost will increase further.

## Current Diagnosis

- The packaged app appears to start from `run_dev.py` because `xenix.spec` deliberately uses `scripts/run_dev.py` as the PyInstaller entry script. This is confusing naming and should be separated, but it is not the dominant startup cost by itself.
- The dominant startup cost is `xenix.services.agent` import during the `Loading runtime components...` phase. That import drags in `agent.tools`, analysis/data services, `ml.registry`, and all model modules, which in turn pull pandas/scikit-learn/scipy/numpy-oriented imports.
- The agent package's `__init__.py` eager re-export makes even apparently narrow imports pay the broad Agent/Tools/ML import cost.
- On a warmed path, the same runtime import costs about 2.3-3.6s. On a fresh rebuilt/copied package path, it costs 12.5-13.3s. The delta is consistent with OS/security scanning of a large native-extension bundle during import/DLL load.
- Xenix's Qt splash is application-level. It cannot appear until PyInstaller bootloader, Python startup, `run_dev -> xenix.main`, `xenix.app` imports, and `QApplication` creation have already happened. It also does not currently appear during smoke because smoke disables splash.

## Next Step

- For startup UX: keep `XENIX_STARTUP_TIMING` as a guarded diagnostic path for now and consider a bootloader-level splash only if the remaining pre-Qt gap still matters in real interactive builds.
- For packaging size/cold-start: keep reducing first-use ML/scientific payloads where product scope allows. The current package is about 582MB because XGBoost, vl-convert, DuckDB, PySide6, numpy/scipy, and grpc are bundled.

## 2026-06-09 Implemented Startup Fix

Changed code:

- Added `scripts/run_packaged.py` and changed `xenix.spec` to use it as the PyInstaller entrypoint. `scripts/run_dev.py` remains the source/dev entrypoint that injects `src` into `sys.path`.
- Added guarded startup timing (`XENIX_STARTUP_TIMING=1`) around packaged/dev entrypoints and app startup phases.
- Replaced eager Agent package re-exports with lazy `__getattr__`.
- Split tool presentation metadata out of `agent.tools` so chatbot event projection does not import the full tool/ML stack.
- Added `LazyAgentToolRegistry`, `LazyMLService`, and `LazyServiceProxy`.
- Deferred startup imports/construction for `DatasetService`, `DataCleaningService`, `DataQueryTransformService`, `MLService`, and `MLTaskService`.
- Moved `MLTaskService` imports of `ml.registry` and `ml.operations` to first-use paths.
- Converted UI-only `MLService` imports in `main_window.py` and `tool_call_detail_view.py` to `TYPE_CHECKING`.
- Added explicit PyInstaller hidden imports for dynamically imported Xenix service modules; the first rebuild failed without this, proving that the lazy imports must be paired with spec-level module collection.

Verification:

- `pdm run check`: passed.
- `pdm run pytest tests\test_main.py -k "startup or smoke"`: 4 passed.
- `pdm run pytest tests\test_services.py tests\test_ml_execution.py`: 14 passed.
- `pdm run pytest tests\test_agent_harness_first_slice.py tests\test_agent_harness_streaming.py`: 35 passed.
- Source/offscreen smoke after lazy-service pass:
  - `run_dev.import_xenix_main`: ~634ms.
  - `runtime_import.total`: ~786ms.
  - `build_main_window.total`: ~1.23s.
  - Before this pass, runtime import was ~3.7s with eager Agent/ML imports.
- Startup interaction probe:
  - Built a hidden main window, confirmed `_tool_registry` is `LazyAgentToolRegistry`, and `list_specs()` resolves 14 tools successfully.
- Packaged rebuild: passed.
- Direct packaged smoke with timing: passed.
- Packaged probe `tasks/packaged-startup-latency/artifacts/20260609-105057/report.md`:
  - Bundle: 1,922 files, 581.64MB.
  - Warm packaged smoke run 1: exit 0, process ~5.93s, first log ~1.37s, shell started ~1.73s, `runtime_import.total` ~496ms, `build_main_window.total` ~1.17s.
  - Warm packaged smoke run 2: exit 0, process ~6.41s, first log ~1.57s, shell started ~1.95s, `runtime_import.total` ~628ms, `build_main_window.total` ~1.36s.
  - Copied-dist first run: exit 0, process ~19.19s, first log ~5.13s, shell started ~5.69s, `runtime_import.total` ~1.17s, `build_main_window.total` ~3.33s.
  - The copied first-run total remains high because smoke checks load DuckDB, vl-convert, XGBoost, and other large native payloads after the shell has started.
- Large copied dist directories generated by the probe were removed after report collection.

Updated diagnosis:

- The packaged app no longer starts from `run_dev.py`; timing now reports `run_packaged.*`.
- The original `Loading runtime components...` bottleneck was code-owned eager import of Agent tools and ML/catalog/data modules. That startup phase is now sub-second on warm packaged runs and about 1.17s on a copied-dist first run.
- A residual first-run gap remains before and around Qt/app startup on a fresh path. This is consistent with Windows first-scan/cold-path behavior against a 582MB, 1,922-file bundle.
- Xenix's Qt splash still cannot appear before PyInstaller bootloader, Python startup, PySide6 import, and `QApplication` creation. If product UX requires immediate launch feedback before those steps, the relevant mechanism is PyInstaller's bootloader splash, not the current Qt splash.

External references used:

- PyInstaller runtime docs: bundled apps set `sys.frozen` and `sys._MEIPASS`; onedir `_MEIPASS` points inside the bundle. This supports treating packaged runtime as a different entry/runtime environment.
- PyInstaller usage docs: bootloader splash can appear before Python application startup, unlike Xenix's Qt splash.
- PyInstaller "When Things Go Wrong": dynamic/hidden imports need explicit collection or hooks; this matched the failed rebuild missing `xenix.services.agent.harness_service`.
- Qt for Python PyInstaller deployment docs: PySide6 deployment depends on correct Qt plugin/library collection and PyInstaller integration.
- Qt for Python `pyside6-deploy` docs: Nuitka-based deployment is the official alternative and has explicit controls to exclude heavy Qt modules/plugins.
- Stack Overflow slow PyInstaller startup discussion: Windows I/O and antivirus scanning of DLL-heavy bundles are common causes; recommended mitigations include early splash and import rework.
- Qt Forum PySide6 slow-start thread: cold vs warm PySide6 startup differences are observed in the field, aligning with Xenix's copied-dist vs warm-path delta.
