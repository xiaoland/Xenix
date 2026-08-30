# UI Agent DX and Maintainability — Implementation Plan

Phase 0 is complete and the user has authorized continued implementation and
task-scoped commits. Each phase remains a reviewable, verified slice.

## Phase 0 — Compatibility and baseline gates

**Status: complete.** Measured commands, compatibility evidence, and the one
unrelated baseline failure are recorded in [phase0.md](phase0.md).

- Install the worktree from the lock file.
- Run the current focused UI cases, `pdm run test`, `pdm run check`, and smoke.
- Qualify the latest admissible `pytest-qt` release with Python 3.14.2, PySide6,
  one `qapp` test, one signal wait, one screenshot, and Qt log capture.
- Record actual feedback timings and baseline artifact sizes.
- If pytest-qt cannot run reliably on Python 3.14.2, stop for a design decision;
  do not implement another hand-rolled event-loop framework.

Verification:

```text
pdm install --frozen-lockfile -G :all
pdm run pytest --direct tests/runtime/test_settings_dialog.py \
  tests/knowledge/test_embedding_change_confirmation.py -q
pdm run test
pdm run check
pdm run smoke
```

## Phase 1 — Shared pytest-qt foundation and semantic IDs

**Status: complete.** pytest-qt 4.5.0 is locked, direct Widget tests live under
the scoped offscreen boundary, manual event polling is removed, and the first
semantic/accessibility contracts pass 18/18 in 4.00s (6.998s runner wall time).
The generated-catalog full suite passes 163/163.

- Add the qualified pytest-qt dependency and lock update.
- Add shared UI pytest configuration/fixtures under `tests/ui/` or root test
  support; keep offscreen QPA setup scoped to `tests/ui/`, and delete duplicated
  `QApplication` and sleep/event-pump helpers as cases migrate.
- Introduce the semantic-ID helper and dotted convention using
  `accessibleIdentifier`.
- Add IDs to the first admitted surfaces only: chat composer/timeline, main
  history shell, and relevant Settings controls.
- Add static uniqueness/presence and repeated-item role/reference contract tests;
  make unexpected Qt warnings fail only with a reviewed scoped baseline.
- Add new typed helper modules to strict mypy.

Verification: migrated existing tests, semantic-ID tests, i18n checks for any
accessible user-facing names, `pdm run check`.

## Phase 2 — Structured UI evidence

**Status: complete.** The typed schema/capture modules, structured
`layout_debug` facade, explicit-root pytest plugin, privacy bounds, and three
subprocess failure probes pass. The scoped UI portfolio is 24/24 in 8.30s.
The generated-catalog full suite passes 169/169.

- Introduce schema-versioned artifact dataclasses/TypedDicts and serializer.
- Refactor `layout_debug.py` to project from JSON authority while preserving the
  environment-triggered log behavior.
- Model both QObject ownership and real layout-item containment.
- Add screenshot, render metadata, bounded Qt log, redaction policy, and optional
  image diff output.
- Add tests for nested layouts, duplicate IDs, redaction, invalid/deleted widget
  handling, deterministic serialization, and bounded output.
- Add a pytest failure hook that captures only registered roots into a known
  `ui-artifacts/` output. Verify ordinary call assertion failure, pytest-qt
  call-report Qt-log failure, and fixture-teardown failure in subprocess probes;
  teardown uses a pre-cleanup staged snapshot.
- Update observability/deployment docs for local use and artifact privacy.

Verification: focused artifact tests plus a deliberately failing probe run whose
artifacts are inspected, then remove/disable the intentional failure.

## Phase 3 — Minimal Qt Widget Lab kernel and zero-service scenarios

**Status: complete.** The dev-only registry exposes three deterministic chat
states through one shared factory contract used by the gallery, capture CLI, and
pytest-qt. Machine discovery does not create a `QApplication`; scenario builds
do not create `XENIX_APP_HOME` or compose runtime services. A representative
900×720 capture emitted a 186,702-byte tree and 24,165-byte screenshot. Focused
UI is 29/29 in 11.25s; the full generated-catalog suite is 174/174 in 136.04s.

- Add dev-only scenario contracts, registry, deterministic context, synthetic
  ports, cleanup handle, and a tiny non-pytest Qt event driver under
  `scripts/ui_lab/`.
- Add list/open/capture CLI entry points and PDM scripts.
- Admit `chat.empty`, `chat.mixed-timeline`, and
  `chat.running-with-attachments`; include repeated items to exercise the
  role/reference identity model.
- Reuse scenario factories in widget-contract tests.
- Provide a compact gallery shell for interactive selection; no hot reload or
  addon system.
- Document the scenario authoring checklist and fastest agent workflow.

Verification:

```text
pdm run ui-lab -- --list --json
pdm run ui-capture -- chat.mixed-timeline --output ui-artifacts/local
pdm run pytest --direct tests/ui -q
```

Acceptance probe: capture a chat state without creating a runtime DB, network
service, OCR service, ML worker pool, or user config.

## Phase 4 — CI evidence and layered visual tests

**Status: implemented locally; first main-targeting PR run remains external
acceptance.** Native CI now captures all three fixed Fusion/en_US/Segoe UI
scenarios, builds a bounded root index, and always uploads only `ui-artifacts/`.
The separately invoked Windows QPA smoke covers expose/activate/focus/dialog and
the custom-painted black user bubble across two resize widths. Visuals remain
capture-only: no expected/diff authority is fabricated before runner stability
is observed. Local UI contracts pass 30/30, native smoke passes 1/1, the full
suite passes 175/175 in 134.59s, and `pdm run check` passes.

- Make Native CI upload the allowlisted `ui-artifacts/` directory with
  `if: always()` alongside JUnit.
- Add environment metadata and a short artifact index suitable for agents.
- Establish a tiny Windows/Fusion visual set with fixed viewport, locale, fonts,
  DPR, and Qt version identity.
- Keep the first visual runs capture-only; generate `expected.png`/`diff.png`
  only after a render-identity-specific baseline is explicitly admitted.
- Add one Windows-native `qwindows` smoke for expose/activate/focus/dialog behavior
  with semantic assertions, not a native pixel baseline.
- Run the native smoke in a distinct pytest process from offscreen contracts and
  include the custom-painted black user bubble resize/repaint tripwire.
- Define the explicit baseline review/update command and promotion criteria.

Verification: local fixed-environment capture, workflow syntax/check, and one CI
run inspected for success and intentional-failure artifact behavior.

## Phase 5 — MainWindow conversation seam

- Characterize stale stream rejection, append acknowledgement, failure recovery,
  stop/pause, attachment state, final snapshot, and shutdown behavior.
- Extract the conversation turn state/controller with injected execution and
  bounded view commands.
- Add pure presentation/model tests for the state transitions and a small widget
  contract using a fake conversation port.
- Keep production harness semantics and translation behavior unchanged.

Verification: pure controller cases, focused main/chat widget contracts, Agent
Harness provider-free checks, `pdm run test`, `pdm run check`.

## Phase 6 — Auxiliary windows and history boundaries

- Move Settings/Knowledge/detail window construction and lifecycle behind narrow
  factories/coordinator composed in `app.py`.
- Extract history panel/controller and remove cross-widget private-state access.
- Reduce `MainWindow` inputs to cohesive feature ports/factories; do not accept a
  giant service bag.
- Split `chatbot.py` and `settings_dialog.py` only where the new boundaries give
  modules independent responsibilities.
- Add extracted contracts/modules to strict mypy.
- Admit `settings.provider-and-ocr` and `main.history-populated` into the shared
  lab registry once their narrow ports make construction honest and cheap.

Verification: main shell fixture constructs with focused fakes; open/raise/close
paths; translated text/language switching; focused/full test and check suites.

## Phase 7 — Agent-safe full-app profiles

- Add typed runtime profile resolution before application import.
- Add `--agent-dev` and `--ephemeral` CLI behavior, unique run id/home, and
  home-scoped mutex.
- Enforce no update auto-check, no remote OTLP, no live LLM/embedding, no OCR
  download, and no remote ML worker admission in agent-safe profiles.
- Connect canonical scripted fixture data through public composition seams.
- Preserve real local directory/bootstrap/migration/recovery topology on fresh
  state.
- Write bounded/redacted evidence outside the raw temporary home and clean the
  home on successful exit.
- Reconcile PDM/CONTRIBUTING/deployment documentation.

Verification must inventory the real default runtime home before and after, use a
network-denial probe, prove fixture visibility, prove mutex isolation, inspect the
failure bundle, and run production smoke for regression.

## Phase 8 — Final integration and measurement

- Run the full acceptance portfolio, check, smoke, translation, and packaging
  gates required by affected surfaces.
- Compare measured reach/arrange/observe timings with Phase 0.
- Audit artifact privacy and baseline stability.
- Update this packet with commands, timings, artifact paths, remaining debt, and
  which capture-only visuals (if any) are safe to promote to blocking.

## Slice ordering rationale

Phases 1–4 create the safety and observation system plus useful zero-service chat
scenarios before structural UI movement. Phases 5–6 then refactor the
highest-degree node with characterization coverage and only then admit honest
Settings/Main scenarios. Phase 7 addresses full-app agent safety without making
it a prerequisite for the faster Widget Lab loop. This ordering maximizes early
feedback-loop ROI and avoids large fake graphs that merely reproduce coupling.
