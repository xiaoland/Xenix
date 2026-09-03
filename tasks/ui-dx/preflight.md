# UI Agent DX and Maintainability — Preflight

## Git and workspace

- Repository has no `master` branch; default/release branch is `main`.
- User explicitly selected `main` because `develop` contains unrelated in-flight
  UI work.
- Worktree was rebuilt at `main@bc03951644d74ff828237fb675974e1e5f659df7`
  on `feat/ui-dx`.
- Approved SVC/docs commit `1a8d784` from develop was cherry-picked as `f528d1f`.
- Two current-workspace changes applied cleanly to the main-based worktree:
  `README.md` terminology and a clarifying comment in
  `src/xenix/services/ml/worker_pool.py`.
- The SVC migration renamed `docs/20-product-tdd` to `docs/20-prd-tdd` and added
  `svc.json` at corpus schema 3/version 14.0.0. Develop-only Job Feed docs were
  still not copied: main has no `JobScheduler`, `JobQueryService`, or Job Center.
  Copying those documents would claim an architecture absent from this baseline.
- The migrated documentation expects `svc lookup`, but no `svc` executable is
  installed on this machine. This is recorded as a tooling/governance gap; no
  unknown global dependency was installed implicitly.

## Quantitative UI inventory on main

- UI Python total: 7,495 lines.
- Top four files: 5,551 lines (74.1%).
  - `src/xenix/ui/chatbot.py`: 2,196
  - `src/xenix/ui/settings_dialog.py`: 1,210
  - `src/xenix/ui/knowledge_workspace.py`: 1,143
  - `src/xenix/ui/main_window.py`: 1,002
- Last-100-commit touch counts:
  - `main_window.py`: 54
  - `chatbot.py`: 28
  - `settings_dialog.py`: 20
  - `knowledge_workspace.py`: 6

This makes `MainWindow` the first refactor target by change-risk centrality, not
merely by line count.

## MainWindow dependency and responsibility evidence

- Constructor: `src/xenix/ui/main_window.py:103-128`.
- Inputs: 22 application values, 13 required and 9 optional.
- Production wiring: `src/xenix/app.py:609-634`.
- Construction creates/connects primary views, loads history/model options, and
  can schedule an update check: `main_window.py:173-223`.
- MainWindow also owns conversation submission/stream gating, attachments,
  service-link background work, thread history actions, title generation, and
  auxiliary window lifecycle.
- Only production and the headed Agent Harness build the real window; there is no
  focused MainWindow fixture/test.

## Test infrastructure evidence

- Direct default Qt widget tests:
  - `tests/runtime/test_settings_dialog.py`: 3 cases
  - `tests/knowledge/test_embedding_change_confirmation.py`: 1 case
- Both files construct their own offscreen `QApplication`.
- Settings tests use manual `processEvents` and `time.sleep` polling.
- `pytest-qt` is absent from the dev dependency group.
- Headed Agent Harness uses real `build_main_window` and `QTest`, but the live
  Agent Harness subtree is excluded from ordinary offline test collection.
- Frozen install and Phase 0 baselines are complete; see `phase0.md`.

## Layout diagnostics evidence

- `src/xenix/ui/layout_debug.py` is 73 lines and gated by
  `XENIX_LAYOUT_DEBUG`.
- It logs class, object name, geometry, size hints, min/max, size policy, and
  visible/hidden state.
- It traverses filtered `QObject.children()` rather than actual layout items.
- It emits no structured file and is called from MainWindow setup only.
- Delayed capture uses nested zero-duration timers without checking whether the
  wrapped C++ object remains valid.

## Startup side-effect evidence

The main-based startup sequence is:

```text
run_dev -> main/single-instance -> app.build_main_window
  -> resolve/create runtime directories
  -> trial state
  -> logging and observability
  -> SQLite bootstrap/migration
  -> headless Agent services
  -> update/OCR/Knowledge service composition
  -> MainWindow
  -> delayed update check
```

- PDM `dev` and `smoke` do not set `XENIX_APP_HOME`.
- `config.py` falls back to the platform user home.
- Startup bootstraps SQLite and composes recovery-capable Knowledge services.
- Observability may create OTLP exporters from configured environment.
- MainWindow schedules update checking when the update controller admits it.
- LLM/Embedding/OCR/ML usually require an explicit action to perform expensive
  work, but their surrounding state and composition still pollute a local UI
  feedback loop.

## CI evidence

- `.github/workflows/native-ci.yml` runs on `windows-2022`.
- It runs `pdm run check` and `pdm run test -vv --junitxml pytest.xml`.
- The only always-uploaded diagnostic is `pytest.xml`, retained for 14 days.
- No known UI artifact output directory or failure hook exists.

## Type-checking probe

The project uses strict mypy over an explicit file allowlist. A read-only probe on
representative UI modules found existing missing parameter annotations in
`startup_splash.py` and `layout_debug.py`. This supports incremental admission of
new/extracted modules instead of a whole-UI switch.

## Resolved and deferred gates

- pytest-qt 4.5.0 passed an isolated Python 3.14.2/PySide6 6.11.1 qualification.
- Frozen install, focused widgets, full test, check, and isolated-home smoke were
  measured. The full test has one understood non-UI generation-order issue.
- Confirm fixed visual environment inputs (font package, Fusion style, locale,
  DPR, viewport) before creating any golden images.
- Confirm artifact redaction with an intentionally sensitive synthetic fixture
  before enabling CI upload.
