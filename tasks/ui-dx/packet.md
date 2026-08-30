# UI Agent DX and Maintainability — Task Packet

## Objective and hypothesis

Shorten the UI feedback loop for agents and humans without creating a second
application architecture. The primary path should render deterministic widget
states without booting storage, network adapters, update checks, OCR, ML, or the
user's configuration. The full application path should remain available through
an explicit isolated/offline runtime profile.

Hypothesis: the highest-return slice is one reusable scenario contract feeding a
small Qt Widget Lab, widget-contract tests, screenshots, and structured failure
artifacts. In parallel, lowering `MainWindow`'s dependency degree at real feature
boundaries will reduce fixture cost and change blast radius more effectively than
line-count-driven file splitting.

## Status and mutation boundary

- Baseline: `main@bc03951644d74ff828237fb675974e1e5f659df7`, plus the
  approved SVC v14 consumer-baseline cherry-pick `f528d1f`.
- Branch: `feat/ui-dx`.
- Worktree: `F:\CODING\Project\Xenix_native-ui-dx`.
- State: Phases 0–1 complete; Phase 2 structured evidence is next.
- Authority: the user has authorized continuation and task-scoped commits without
  further per-phase approval.

## Guardrails

- Production startup defaults, user runtime home, migration behavior, packaging,
  translation, and recovery semantics remain unchanged unless a planned slice
  explicitly proves the change.
- Agent/test modes must never read, migrate, or write the real user runtime home.
- Offline modes must disable remote update, telemetry export, LLM, embedding,
  OCR download, and remote ML worker edges through composition capabilities, not
  ambient convention alone.
- CI artifacts never include the raw SQLite database, provider settings,
  credentials, arbitrary user content, or an entire runtime home.
- `MainWindow` will not receive a single giant dependency bag that merely hides
  the existing coupling. Dependencies are reduced at conversation, navigation,
  and auxiliary-window boundaries.
- File splitting follows cohesive behavior, lifecycle, and change locality. No
  arbitrary maximum-line rule is introduced.
- Bitmap comparisons are a small, environment-pinned layer, not the default UI
  assertion mechanism.
- Existing translated UI behavior and `LanguageChange` handling remain covered.

## Current truth

- `src/xenix/ui` contains 7,495 Python lines. `chatbot.py`,
  `settings_dialog.py`, `knowledge_workspace.py`, and `main_window.py` contain
  5,551 lines (74.1%).
- In the last 100 commits, `main_window.py` changed 54 times, versus 28 for
  `chatbot.py` and 20 for `settings_dialog.py`; it is both a size and churn
  hotspot.
- `MainWindow.__init__` accepts 22 application inputs (13 required and 9
  optional) and construction immediately queries models/history, creates
  controllers, connects workflows, and may schedule an update check.
- There is no focused `MainWindow` or `ThreadDetailView` test. The default test
  portfolio has four direct Qt widget cases across two files.
- Those tests duplicate `QApplication`, `processEvents`, and sleep-based waiting;
  `pytest-qt` is not installed.
- `layout_debug.py` emits a log-only QObject ownership traversal. It does not
  model real `QLayout.itemAt()` containment, persist JSON, capture screenshots,
  or record render environment metadata.
- CI uploads only `pytest.xml`; no UI tree, screenshot, diff, geometry, Qt log,
  or environment manifest is preserved.
- `pdm run dev` and `pdm run smoke` do not select an isolated runtime home.
  Full startup creates directories, bootstraps/migrates SQLite, initializes
  observability, composes services, recovers Knowledge tasks, and can schedule
  an update check.
- Phase 0 qualified pytest-qt 4.5.0 on the locked Python/PySide/pytest stack.
  The clean first `pdm run test` baseline is 147 passed / 2 failed because the
  ignored Agent skill catalog has not yet been generated; after `pdm run check`
  generates it, the failing file passes. This is an unrelated command-order
  dependency, not a UI regression.
- The migrated SVC docs route workflow/taste lookup through `svc`, but that CLI
  is unavailable on this machine. Repository evidence and authoritative public
  sources remain usable; no unknown global tool was installed implicitly.
- Phase 1 locked pytest-qt 4.5.0, moved all direct Widget tests under the scoped
  `tests/ui` QPA boundary, removed manual event pumping/sleeps, introduced typed
  semantic identity, and admitted the first Main/chat/Settings static controls.
  Focused UI is 18 passed in 4.00s (6.998s through the repository runner); the
  generated-catalog full suite is 163 passed.

Detailed evidence is in [preflight.md](preflight.md); source research is in
[research.md](research.md).

## 80/20 deliverables

1. **Shared Qt test foundation**
   - Qualify `pytest-qt` against Python 3.14.2 before locking it.
   - Replace duplicated application/event-loop helpers with `qapp`, `qtbot`,
     `addWidget`, `waitSignal`, `waitUntil`, and Qt log capture.

2. **Qt Widget Lab**
   - A searchable/listable scenario registry with deterministic state inputs,
     synthetic fixtures, explicit viewport/locale/style, and cleanup.
   - The first zero-service slice covers chat timeline/composer states. Settings
     and main shell/history join only after narrow construction ports exist;
     Knowledge is deferred until its worker cleanup can be deterministic.
   - The same scenario factory is callable interactively, from tests, and from a
     headless capture command.

3. **Stable UI semantic identity**
   - Use `QWidget.accessibleIdentifier` as the non-localized automation ID.
   - Preserve `objectName` for Qt styling/legacy lookup; do not silently change
     style selectors.
   - Enforce uniqueness and presence for static actionable widgets. Repeated
     collection controls use a semantic role plus a stable, non-sensitive item
     reference; neither content/path nor layout position is identity.

4. **Structured UI evidence**
   - Upgrade `layout_debug.py` into a schema-versioned snapshot producer:
     ownership tree, layout tree, semantic state, geometry, render metadata,
     screenshot, and optional expected/actual/diff set.
   - Runtime captures redact user values and paths; CI capture is limited to
     synthetic scenarios.
   - A pytest failure hook writes to a known `ui-artifacts/` directory which CI
     uploads with `if: always()`.

5. **Layered UI verification**
   - Pure presentation/model tests: no `QApplication`.
   - Widget contracts: offscreen, semantic/property/signal assertions.
   - Scenario visuals: a few pinned Windows/Fusion baselines with metadata and
     tolerance; capture-only until stability is demonstrated.
   - Windows-native visual smoke: `qwindows`, exposed/active/focus/dialog checks,
     semantic assertions, no pixel-perfect cross-run gate.

6. **Lower-coupled UI composition**
   - Extract a conversation turn state/controller seam from `MainWindow`.
   - Extract auxiliary-window creation/lifecycle behind narrow factories or a
     coordinator.
   - Extract the history sidebar as a cohesive view/controller when its contract
     is covered.
   - Split large files only as these boundaries become real.

7. **Agent-safe full-app profile**
   - Introduce a typed runtime profile propagated from launcher to composition.
   - `--agent-dev`: deterministic fixtures, explicit remote-capability denial,
     no automatic update or remote telemetry.
   - `--ephemeral`: unique runtime home and home-scoped mutex; run real local
     bootstrap/recovery topology against fresh state, never the user home.
   - Preserve only bounded, redacted failure evidence outside the temporary home.

8. **Incremental typing**
   - Add new scenario, artifact, semantic-ID, port, and pure controller modules
     to the existing strict mypy allowlist first.
   - Expand into extracted UI modules as their interfaces stabilize; do not
     enable strict checking for the entire legacy UI tree in one step.

## Acceptance criteria

- An agent can list scenarios as JSON, open one scenario, and capture its evidence
  without constructing storage, update, provider, OCR, ML, or user-config services.
- A representative chat/settings change has a sub-10-second focused feedback
  command on an already-installed environment.
- Scenario factories are reused by widget tests and capture commands; no parallel
  fixture language exists.
- Static actionable controls in admitted scenarios have unique stable semantic
  IDs. Repeated items are addressable by role plus authoritative item reference;
  neither contract depends on translated text, widget class, content/path, or
  layout position.
- A deliberately failing widget test yields a screenshot, JSON trees, geometry,
  Qt/PySide/style/DPI/locale metadata, and bounded Qt logs in CI.
- `MainWindow` focused tests can construct the shell without manually providing
  every concrete application service; the production composition root still
  wires real services explicitly.
- `--agent-dev --ephemeral` proves that the default user home is unchanged and
  that remote edges are denied while the main window can still be inspected.
- Existing production startup, smoke, translation, and packaged behavior remain
  green.
- No screenshot baseline is shared across OS/style/font/DPI identities.

## Non-goals

- Reimplementing Storybook's web UI, hot-module reload, addon ecosystem, or remote
  publishing.
- Full pixel coverage of every widget state.
- A whole-repository MVC/MVVM rewrite.
- Moving domain logic into UI fixtures or creating a second service stack.
- Making Agent Harness live-provider benchmarks part of ordinary UI tests.
- Backporting develop-only Job Center/Job Scheduler work into this main-based task.

## Decisions

- D1: base this task on `main`, per explicit user direction, even though the
  repository normally integrates feature work through `develop`.
- D2: scenarios are reusable executable state specifications, not screenshots or
  bespoke demo scripts.
- D3: semantic identity is `accessibleIdentifier`; `objectName` remains a
  presentation/legacy concern.
- D4: structured/semantic assertions are the default; bitmap comparison is narrow.
- D5: reduce `MainWindow` degree through feature ports/coordinators, not a service
  locator or dependency-parameter object alone.
- D6: fresh-home isolation preserves production-local bootstrap/recovery behavior;
  only remote capabilities and fixtures vary by profile.
- D7: mypy remains the required checker; no second mandatory Pyright gate.
- D8: pytest-qt 4.5.0 is admitted by the Python 3.14.2 compatibility spike even
  though its published classifiers currently stop at Python 3.13.
- D9: offscreen widget contracts and native `qwindows` smoke run in separate
  pytest processes because QPA selection is fixed by the first QApplication.
- D10: production semantic/snapshot code lives under `src/xenix/ui`; dev-only
  scenario registry, synthetic ports, gallery, and CLI live under
  `scripts/ui_lab` so `xenix.spec` does not copy them into worker source.
- D11: scenario specifications declare root, cleanup, and readiness only. pytest
  and the interactive lab provide separate thin event drivers.
- D12: runtime layout diagnostics default to redacted JSON without screenshots;
  screenshots require an explicit synthetic-scenario capture policy.

## Plan and verification

See [phase0.md](phase0.md) for measured gates, [plan.md](plan.md) for
implementation slices, and [design.md](design.md) for topology, sequences,
contracts, and testing policy.
