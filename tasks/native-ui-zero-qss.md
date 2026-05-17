# Native UI Zero QSS

## Objective & Hypothesis

Objective: unify the Qt Widgets visual language by removing stylesheet usage from the active UI code.

Hypothesis: the current visual split comes from local QSS-heavy surfaces mixed with default Qt Widgets surfaces. Replacing QSS with native widget structure, `QFont`, standard icons, and default palette behavior should make the shell feel more coherent without changing product behavior.

## Guardrails Touched

- `src/xenix/ui/`: Qt Widgets presentation only.
- ChatBox-first shell remains the active operator path.
- UI stays service-driven; no storage, ML, or Agent Harness contracts change.
- User-visible text and i18n behavior remain unchanged unless structure requires a label-only adjustment.

## Verification

- Static scan passed: `rg -n "setStyleSheet\\(" src/xenix -S` returned no matches.
- Static UI style scan passed: `rg -n "setStyleSheet\\(|styleSheet|\\.qss|background:|border-radius|font-size|color:" src/xenix/ui -S` returned no matches.
- Compile check passed: `pdm run check`.
- Targeted tests passed:
  - `pdm run pytest tests/test_main.py -q` -> 20 passed.
  - `pdm run pytest tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py -q` -> 10 passed.
  - `pdm run pytest tests/test_scenario_ui.py tests/test_i18n.py -q` -> 27 passed.
- Full-suite attempt: `pdm run pytest -q` timed out after 304 seconds without reporting a failure.
- Split full-suite coverage passed across all test files:
  - storage/services/repository/migration/config/logging/resources group -> 25 passed.
  - ML/scenario-workflow/inference-history group -> 22 passed.
  - JSON schema form/agent settings/agent foundation group -> 8 passed.
- Smoke test passed: `pdm run smoke`.
- Message text transparency follow-up:
  - Runtime Qt inspection confirmed `QTextBrowser.viewport()` was the white background owner because it filled the `Base` palette role.
  - Updated ChatBox message text browser and viewport to transparent native widgets with no stylesheet.
  - Added regression coverage in `tests/test_main.py`.
  - `pdm run pytest tests/test_main.py -q` -> 21 passed.
  - Runtime reinspection confirmed browser/viewport `autoFillBackground=False` and viewport translucent/no-system-background attributes.
- Message panel follow-up:
  - Restored message cards to `QFrame.StyledPanel`.
  - User messages now use a black card palette and white text palette, still without stylesheet.
  - Runtime inspection confirmed user card `StyledPanel`, `Window=#000000`, browser/viewport text `#ffffff`, and assistant cards keep the native default panel palette.
  - `pdm run pytest tests/test_main.py -q` -> 22 passed.
  - `pdm run check` and `pdm run smoke` passed.
