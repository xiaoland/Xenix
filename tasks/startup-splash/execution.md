# Startup Splash

## Objective & Hypothesis

Objective: show a branded Xenix startup splash before slow bootstrap work so users get immediate launch feedback.

Hypothesis: creating `QApplication` and a lightweight Qt splash before runtime directory, logging, storage, and service initialization will remove the blank-launch interval without changing storage, service, or main-window contracts.

Follow-up visual direction: revise the splash from a clean modern card into a 2007-era CAD/engineering startup screen. The `Xenix` mark should dominate the upper-right composition, use pseudo-3D perspective, and align with grid/light direction instead of behaving like centered branding.

Follow-up timing direction: in the real GUI startup path, hold the completed splash briefly after bootstrap finishes before showing the main window. The hold is 2200 ms and is injected only through `run()`; direct `build_main_window()` callers, smoke tests, and `show=False` paths default to no hold.

## Guardrails Touched

- Incoming request type: `Intent`.
- Active modes: `Explore` for startup chain mapping, then `Execute` for the bounded bootstrap/UI change.
- UI surface: `src/xenix/ui/startup_splash.py`.
- Bootstrap surface: `src/xenix/app.py`.
- Runtime/storage services remain unchanged.
- New user-visible text must stay in the Qt translation pipeline.
- Current no-QSS native UI direction remains intact.
- The CAD-style title is drawn as vector geometry so it does not depend on platform font rendering.
- The extra splash hold must happen after `READY` and before `MainWindow.show()`, while smoke tests remain fast.

## Verification

- `pdm run i18n-extract` passed.
- `pdm run i18n-compile` passed; `xenix_zh_CN.qm` generated with 129 finished and 0 unfinished translations.
- `pdm run pytest tests/test_main.py::test_smoke_test_bootstraps_runtime_in_fresh_app_home tests/test_main.py::test_main_window_reports_startup_splash_stages_when_enabled tests/test_i18n.py::test_startup_splash_language_switch_updates_stage_text tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell -q` passed: 4 tests.
- `pdm run pytest tests/test_main.py -q` passed: 26 tests.
- `pdm run pytest tests/test_i18n.py -q` passed: 4 tests.
- `pdm run pytest tests/test_i18n.py::test_startup_splash_renders_nonblank_canvas_offscreen tests/test_i18n.py::test_startup_splash_language_switch_updates_stage_text tests/test_main.py::test_main_window_reports_startup_splash_stages_when_enabled -q` passed: 3 tests.
- `pdm run pytest tests/test_main.py::test_main_window_holds_ready_splash_before_showing_window tests/test_main.py::test_main_window_reports_startup_splash_stages_when_enabled tests/test_main.py::test_smoke_test_bootstraps_runtime_in_fresh_app_home -q` passed: 3 tests.
- `pdm run check` passed.
- `pdm run smoke` passed.
- `rg -n "setStyleSheet\\(|styleSheet|\\.qss|background:|border-radius|font-size" src\\xenix\\ui src\\xenix\\app.py` returned no matches.
- `pdm run pytest -q` passed: 113 tests. Pytest emitted a Windows temp-directory cleanup `PermissionError` after completion, but the command returned 0.
