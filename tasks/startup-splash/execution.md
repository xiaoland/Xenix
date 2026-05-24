# Startup Splash

## Objective & Hypothesis

Objective: show a branded Xenix startup splash before slow bootstrap work so users get immediate launch feedback.

Hypothesis: creating `QApplication` and a lightweight Qt splash before runtime directory, logging, storage, and service initialization will remove the blank-launch interval without changing storage, service, or main-window contracts.

Follow-up visual direction: revise the splash from a clean modern card into a 2007-era CAD/engineering startup screen. The `Xenix` mark should dominate the upper-right composition, use pseudo-3D perspective, and align with grid/light direction instead of behaving like centered branding.

Follow-up timing direction: in the real GUI startup path, hold the completed splash briefly after bootstrap finishes before showing the main window. The hold is 2200 ms and is injected only through `run()`; direct `build_main_window()` callers, smoke tests, and `show=False` paths default to no hold.

Follow-up simplification direction: remove the logo image and reduce the splash to one dominant mixed-case `Xenix` vector mark, a restrained perspective grid, and the status bay. Keep the palette to three primary hues: deep blue-black, silver blue-gray, and cold blue accent.

Follow-up mark direction: keep the `Xenix` wordmark vector-drawn, but replace rounded `e`/`n` curves with hard-edged strokes and miter joins so the mark reads more like an engineering/software identity than a playful logo.

Follow-up startup-latency diagnosis: the remaining blank-launch interval was not splash rendering. `xenix.app` was eagerly importing the agent, ML registry, all model adapters, and main-window graph before `StartupSplash` could be constructed. The bootstrap shell should stay light enough to create `QApplication` and show the splash first; workbench/service imports can happen after the splash reaches the `STARTING` stage.

Follow-up loading-state diagnosis: moving heavy imports after splash display made the first window appear quickly, but the imports still ran synchronously on the main thread while the translator was not installed yet. The splash could therefore appear in English and the `QTimer`-driven pulse bar could not advance while the `STARTING` stage was blocked. The fix keeps `build_main_window()` synchronous, installs the translator before splash construction, adds a dedicated runtime-loading stage, and loads non-UI runtime modules in a background thread while the main thread pumps Qt events.

## Guardrails Touched

- Incoming request type: `Intent`.
- Active modes: `Explore` for startup chain mapping, then `Execute` for the bounded bootstrap/UI change.
- Startup-latency follow-up incoming request type: `Reality`; active modes: `Diagnose` to isolate the blank interval, then `Execute` for the lazy bootstrap import boundary.
- Loading-state follow-up incoming request type: `Reality`; active modes: `Diagnose` to isolate the frozen splash text/animation, then `Execute` for the translated and animated runtime-loading stage.
- UI surface: `src/xenix/ui/startup_splash.py`.
- Bootstrap surface: `src/xenix/app.py`.
- Runtime/storage services remain unchanged.
- New user-visible text must stay in the Qt translation pipeline.
- Current no-QSS native UI direction remains intact.
- The CAD-style title is drawn as vector geometry so it does not depend on platform font rendering.
- The extra splash hold must happen after `READY` and before `MainWindow.show()`, while smoke tests remain fast.
- The splash no longer loads or draws the packaged logo image.
- The simplified splash avoids extra CAD ornaments and keeps `Xenix` mixed-case.
- The `Xenix` mark should keep straight, hard-edged geometry for `e`, `n`, and `i`.
- The app bootstrap import boundary should remain light: `src/xenix/app.py` may import Qt/application/splash support at module import time, but workbench, agent, storage, and ML services are loaded after the splash is visible.
- External/test compatibility for `xenix.app.MainWindow` is preserved through a lazy module attribute; normal `import xenix.app` must not import `MainWindow`.
- `TranslationManager` must initialize before `StartupSplash` construction so the first visible stage is localized.
- Runtime service imports must not block the main thread while the splash is visible; `build_main_window()` still waits for them and returns only after the main window is fully constructed.

## Verification

- Loading-state follow-up:
  - `pdm run i18n-extract` passed; found one new startup splash source text.
  - `pdm run i18n-compile` passed; `xenix_zh_CN.qm` generated with 192 finished and 0 unfinished translations.
  - `pdm run check` passed.
  - `pdm run pytest tests/test_main.py -q` passed: 34 tests.
  - `pdm run pytest tests/test_i18n.py -q` passed: 5 tests.
  - `pdm run smoke` passed.
  - `pdm run package` passed.
  - `pdm run smoke-package` passed.
  - Direct rebuilt packaged `xenix.exe --smoke-test` passed; second measured process lifetime was `4037 ms` after an initial post-package cold run measured `14153 ms`.
  - Rebuilt packaged exe first visible Qt window was `458 ms`, `545 ms`, and `560 ms` across three runs.
- Startup-latency follow-up:
  - Baseline before the change: packaged exe first visible Qt window was `2262 ms`, `3193 ms`, and `2329 ms` across three runs; source `import xenix.app` was `2.637 s`; source probe reached `splash_show_centered` at `2.810 s`.
  - After lazy bootstrap imports: source `import xenix.app` was `0.213 s`; source probe reached `splash_show_centered` at `0.269 s`; heavy service import work then completed before `PREPARING_APP_DATA` at `2.822 s`.
  - `pdm run check` passed.
  - `pdm run pytest tests/test_main.py -q` passed: 33 tests.
  - `pdm run pytest tests/test_i18n.py::test_startup_splash_renders_nonblank_canvas_offscreen tests/test_i18n.py::test_startup_splash_language_switch_updates_stage_text -q` passed: 2 tests.
  - `pdm run smoke` passed; measured command wall time was `5528.01 ms`.
  - `pdm run package` passed after closing a leftover `dist/xenix/xenix.exe` process that was locking the previous bundle.
  - Rebuilt packaged exe first visible Qt window was `1843 ms`, `586 ms`, and `436 ms` across three runs.
  - `pdm run smoke-package` passed.
  - Direct rebuilt packaged `xenix.exe --smoke-test` passed; second measured process lifetime was `4043 ms` after an initial post-package cold run measured `11041 ms`.
- `pdm run i18n-extract` passed.
- `pdm run i18n-compile` passed; `xenix_zh_CN.qm` generated with 129 finished and 0 unfinished translations.
- `pdm run pytest tests/test_main.py::test_smoke_test_bootstraps_runtime_in_fresh_app_home tests/test_main.py::test_main_window_reports_startup_splash_stages_when_enabled tests/test_i18n.py::test_startup_splash_language_switch_updates_stage_text tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell -q` passed: 4 tests.
- `pdm run pytest tests/test_main.py -q` passed: 26 tests.
- `pdm run pytest tests/test_i18n.py -q` passed: 4 tests.
- `pdm run pytest tests/test_i18n.py::test_startup_splash_renders_nonblank_canvas_offscreen tests/test_i18n.py::test_startup_splash_language_switch_updates_stage_text tests/test_main.py::test_main_window_reports_startup_splash_stages_when_enabled -q` passed: 3 tests.
- `pdm run pytest tests/test_main.py::test_main_window_holds_ready_splash_before_showing_window tests/test_main.py::test_main_window_reports_startup_splash_stages_when_enabled tests/test_main.py::test_smoke_test_bootstraps_runtime_in_fresh_app_home -q` passed: 3 tests.
- Simplified splash follow-up:
  - `pdm run i18n-extract` passed.
  - `pdm run i18n-compile` passed; `xenix_zh_CN.qm` generated with 152 finished and 0 unfinished translations.
  - `pdm run pytest tests/test_i18n.py::test_startup_splash_renders_nonblank_canvas_offscreen tests/test_i18n.py::test_startup_splash_language_switch_updates_stage_text -q` passed: 2 tests.
  - `pdm run pytest tests/test_main.py -q` passed: 29 tests.
  - `pdm run pytest tests/test_i18n.py -q` passed: 4 tests.
  - `pdm run check` passed.
  - `pdm run smoke` passed.
  - `rg -n "setStyleSheet\\(|styleSheet|\\.qss|background:|border-radius|font-size|QPixmap|package_resource_path|Business ML Workbench|logo" src\\xenix\\ui\\startup_splash.py` returned no matches.
- `pdm run check` passed.
- `pdm run smoke` passed.
- `rg -n "setStyleSheet\\(|styleSheet|\\.qss|background:|border-radius|font-size" src\\xenix\\ui src\\xenix\\app.py` returned no matches.
- `pdm run pytest -q` passed: 123 tests. Pytest emitted a Windows temp-directory cleanup `PermissionError` after completion, but the command returned 0.
