# Startup OTLP UI Freeze Profile

## Objective & Hypothesis

- Objective: diagnose the reproducible UI freeze after MainWindow appears and before the app becomes responsive.
- Hypothesis: startup finishes the `app.startup` span and synchronously flushes OpenTelemetry exporters on the Qt main thread; a slow or unreachable OTLP HTTP backend blocks the event loop until the exporter timeout.

## Guardrails Touched

- Reality / Diagnose route.
- Runtime owner: `src/xenix/app.py` owns application startup sequencing.
- Observability owner: `src/xenix/observability.py` owns OpenTelemetry provider/exporter setup, flush, and shutdown helpers.
- UI invariant: network telemetry export must not block the Qt event loop after the shell is visible.

## Current Understanding

- User-reported symptom: after entering MainWindow, UI is unresponsive until an OTLP exporter timeout log appears.
- User console evidence showed:
  - `Xenix native shell started` at `2026-06-19T14:07:20.938137Z`.
  - `Failed to export span batch ... Read timed out. (read timeout=9.999...)` at `2026-06-19T14:07:52.261947Z`.
- Code path:
  - `build_main_window()` logs `Xenix native shell started`.
  - It records `xenix.app.startup.count`.
  - It exits the startup span.
  - It immediately calls `flush_observability()` before returning to `app.exec()`.
  - `flush_observability()` calls `_tracer_provider.force_flush()` and `_meter_provider.force_flush()` synchronously.
- With OTLP HTTP/protobuf traces enabled, `force_flush()` can perform a blocking exporter call on the caller thread.
- Because this happens after `window.show()` but before the event loop is entered, the visible MainWindow cannot process input or repaints while the exporter waits for network timeout.

## Evidence Log

- Baseline smoke with OTLP disabled:
  - Command shape: `XENIX_STARTUP_TIMING=1`, fresh `XENIX_APP_HOME`, no `OTEL_EXPORTER_OTLP*` or `XENIX_OTEL*` env, `pdm run smoke`.
  - Result: exit 0, elapsed 6.750s.
  - `Xenix native shell started` at app-import +1693ms.
  - `build_main_window.total` at app-import +1693ms.
  - No post-shell-start flush gap.
- Reproduction smoke with local non-responsive OTLP HTTP endpoint:
  - A local socket server accepted connections and held them open without response.
  - Env:
    - `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:<port>/v1/traces`
    - `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf`
    - `XENIX_STARTUP_TIMING=1`
    - fresh `XENIX_APP_HOME`
  - Result: exit 0, elapsed 27.295s.
  - The fake endpoint accepted 2 connections.
  - `Xenix native shell started` at app-import +2039ms.
  - Exporter logged `Read timed out. (read timeout=9.999...)` about 10s later.
  - `build_main_window.total` appeared only after that timeout, at app-import +12068ms.
  - Smoke later triggered another synchronous flush and another 10s exporter timeout.

## Diagnosis

- Root cause: startup calls synchronous OpenTelemetry flush on the GUI startup path.
- Trigger: an enabled OTLP exporter whose backend is slow, unreachable, or timing out.
- User-visible failure mode: MainWindow is visible but Qt event processing has not resumed, so the UI appears frozen until the exporter call returns or times out.
- This is not a storage bootstrap, MainWindow construction, or dataset-loading freeze.

## Candidate Fix Direction

- Remove synchronous `flush_observability()` from the interactive startup success path.
- Let `BatchSpanProcessor` export startup spans asynchronously according to its own schedule.
- Keep explicit synchronous flush for non-interactive smoke/diagnostic process-exit paths if deterministic telemetry delivery matters there.
- For failures or process shutdown, flush from a bounded background path or use a short timeout, but do not block Qt input after the window is visible.
- Add a regression test that replaces the tracer provider with a blocking fake and proves `build_main_window(show=True)` does not synchronously wait after shell start.

## Implemented Change

- `build_main_window()` now accepts `flush_startup_observability=False`.
- Interactive startup keeps the default and does not call `flush_observability()` after `Xenix native shell started`.
- `run(smoke_test=True)` passes `flush_startup_observability=True`, preserving deterministic smoke-test telemetry delivery.
- Startup failure handling still flushes synchronously, matching the existing failure-path behavior.
- Runtime documentation now states that interactive startup must not block Qt input on OTLP export.
- Regression coverage:
  - interactive startup fails the test if it tries to synchronously flush observability;
  - explicit startup flush opt-in remains available and calls the flush hook once.

## Verification

- Targeted tests:
  - `pdm run pytest tests/test_main.py::test_interactive_startup_does_not_synchronously_flush_observability tests/test_main.py::test_startup_observability_flush_remains_explicitly_available tests/test_main.py::test_smoke_test_bootstraps_runtime_in_fresh_app_home tests/test_observability.py -q`
  - Result: 10 passed.
- Compile check:
  - `pdm run check`
  - Result: passed.
- Related tests:
  - `pdm run pytest tests/test_main.py tests/test_observability.py -q`
  - Result: 54 passed.
- Diff hygiene:
  - `git diff --check`
  - Result: clean.
- Reproduction rerun with a local non-responsive OTLP HTTP endpoint:
  - `build_main_window(show=True, show_splash=False)` returned in 2.300s.
  - `Xenix native shell started` and `build_main_window.total` appeared back-to-back at app-import +2299ms/+2300ms.
  - The exporter timeout still appeared about 10s later during background/process-exit telemetry handling, but no longer delayed `build_main_window()` returning to the interactive caller.

## Next Step

- Ready for review or commit with the dataset preflight work.
