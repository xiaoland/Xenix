# UI Agent DX Phase 0 — Compatibility and Baseline Evidence

## Result

Phase 0 passed its UI admission gates. pytest-qt 4.5.0 is suitable for the locked
Xenix stack by direct execution, and the current Qt widget cases, check topology,
and isolated-home smoke pass. The clean full-test command has one unrelated,
understood generation-order failure and therefore remains a yellow baseline.

Environment:

- Windows, Python 3.14.2
- PySide6/Qt 6.11.1
- pytest 9.1.1
- PDM 2.28.0
- branch `feat/ui-dx`, base `main@bc03951`, SVC cherry-pick `f528d1f`

## Measured commands

| Gate | Result | Wall time | Evidence |
| --- | --- | ---: | --- |
| `pdm install --frozen-lockfile -G :all` | pass, 187 packages | 103s | lock unchanged |
| current direct Qt cases | 4 passed | 41.263s | pytest 35.83s |
| clean `pdm run test` | 147 passed, 2 failed | 155.777s | both missing generated preprocessing skill |
| `pdm run check` | pass | 64.790s | generated/checked 3-skill catalog; strict mypy 17 files |
| failed-file recheck after generation | 3 passed | 7.385s | confirms command-order dependency |
| isolated `pdm run smoke` | pass | 103.060s | unique temp home; OTLP disabled |
| pytest-qt qualification | 2 passed | 2.230s | pytest body 0.12s |

The focused Qt selector was:

```text
pdm run pytest --direct tests/runtime/test_settings_dialog.py \
  tests/knowledge/test_embedding_change_confirmation.py -q
```

The smoke command used a unique directory named
`xenix-ui-dx-phase0-<uuid>` under the system temp root as `XENIX_APP_HOME` and
set `OTEL_SDK_DISABLED=true`. It did not read or write the default Xenix runtime
home. Startup processes events only once before close, so the delayed one-second
update check was not reached.

## pytest-qt qualification

PyPI's current pytest-qt 4.5.0 release requires Python 3.9+ but publishes
classifiers only through Python 3.13. The wheel was downloaded and expanded into
an isolated temporary import directory; neither `pyproject.toml`, `pdm.lock`, nor
the worktree virtual environment was mutated.

The persistent probe is
`tasks/ui-dx/probes/test_pytest_qt_qualification.py`. It verified:

- `qapp` owns the single QApplication;
- `qtbot.addWidget` cleanup and `waitExposed` under `offscreen`;
- `waitSignal` with a zero-delay QTimer;
- `waitUntil` condition processing;
- `qtbot.screenshot`, producing a valid 384-byte PNG for a 320×80 label;
- `qtlog.records` capture of a Qt warning.

Result: 2 passed in 0.12s (2.230s through the repository runner). The initial
wheel-import experiment also exposed a useful tooling fact: plugin entry-point
discovery requires an installed distribution; the final probe exercised the
official plugin from an isolated distribution path without locking it yet.

## Baseline exception

On a clean checkout, `pdm run test` does not run `agent-skills-generate` and the
ignored `src/xenix/services/agent/skills/catalog.json` is absent. Two tests in
`tests/agent/test_agent_data_cleaning_guidance.py` therefore cannot find
`xenix-data-preprocessing`. `pdm run check` generates the three-skill catalog;
the same file then passes 3/3. This predates and is orthogonal to UI-DX work.

For implementation comparisons:

- preserve the clean-order failure as a known baseline until its owning task
  fixes command topology;
- run `pdm run check` before the final full test when validating UI changes;
- never report those two failures as a UI regression without reproducing after
  catalog generation.

## Rehearsal decisions frozen before implementation

1. Scope offscreen setup to `tests/ui/conftest.py`; never set it in the shared
   runner because headed Agent Harness uses the same runner.
2. Run offscreen and native `qwindows` suites in separate processes. QPA cannot
   be switched after QApplication creation.
3. Keep production semantic identity and diagnostics under `src/xenix/ui`, but
   keep registry, gallery, synthetic ports, and CLI under `scripts/ui_lab` so the
   PyInstaller worker-source copy does not ship lab code.
4. Never mirror semantic IDs into `objectName`; existing names influence runtime
   chat layout and may be repeated legitimately.
5. Give static actions unique dotted IDs. Address repeated items by semantic role
   plus authoritative non-sensitive item reference, never content, path, hash,
   runtime UUID, or position.
6. A scenario declares root, cleanup, and readiness. pytest-qt and the lab own
   separate thin drivers, preventing pytest concepts from entering production or
   scenario contracts.
7. Admit zero-service chat scenarios first. Settings and MainWindow scenarios
   wait for narrow ports; initial Knowledge scenarios are deferred because their
   worker lifecycle/cleanup cost fails the 80/20 threshold.
8. Runtime diagnostics default to redacted JSON/logs without pixels. Screenshots
   are permitted only for explicit synthetic-scenario policy; CI accepts only
   that policy.
9. The pytest failure plugin must be subprocess-tested for assertion failure,
   pytest-qt call-report Qt-log failure, and fixture-teardown failure. Direct
   pytest-qt 4.5 source inspection showed that it stops Qt-log capture in the call
   report; teardown failures instead require a pre-cleanup staged snapshot.

No product implementation was made in Phase 0. The design survived rehearsal
with the boundary/order corrections above; no foundational approach was replaced.
