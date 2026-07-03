# Settings Tabs UX

## Objective & Hypothesis

Reorganize the Settings dialog as top tabs so growing configuration surfaces stay scannable. The LLM model selectors for default, turn guard, and thread title are global settings and should be visually separated from per-provider configuration. Runtime diagnostics should move out of Settings into an independent About window, opened from the lower-left corner of Settings.

## Guardrails Touched

- UI layer: `src/xenix/ui/settings_dialog.py`
- UI layer: likely a new About dialog class or a focused private dialog in the settings module.
- Translation pipeline: any new visible labels need Qt translation entries.
- Settings authority: `LLMSettings` already owns global model keys; provider config remains per-provider.

## Verification

- Focused SettingsDialog tests should prove provider switching and global model selector behavior still persist correctly.
- i18n tests should cover new/renamed visible strings.
- A Qt offscreen smoke or screenshot is useful after implementation to catch layout regressions.
- 2026-07-03: `pdm run pytest tests/test_settings_dialog.py tests/test_i18n.py` passed.

## Current Understanding

- Current dialog is one scroll stack: LLM providers, optional AIMock, ML workers, runtime.
- `Default model`, `Turn guard model`, and `Thread title model` are rendered in the same `QFormLayout` card as provider fields, creating a false provider-local visual boundary.
- Product docs already describe Settings as containing multi-provider config, global default model, and development mock configuration.
- Runtime content is diagnostic/about information: app home, state directory, artifacts directory, database path, current log file, build commit, and open log directory action.
- Implemented shape: Settings has top tabs for AI and ML Workers; About opens from the lower-left Settings action and owns runtime diagnostics.

## Unknowns

- Exact desired tab names are not specified.
- Whether AIMock should stay inside an AI/LLM tab or become a developer tab is a product choice; current behavior only shows it in development.
- Exact About window title and entry label need final naming; current user wording says `关于`.

## Candidate Path

- Convert the central settings body into a `QTabWidget` with top tabs.
- Use an AI tab containing two visually separate groups: global model choices and provider configurations; keep AIMock as a separate development-only group in that tab.
- Use an ML Workers tab for worker pool summary and SSH worker setup.
- Remove runtime diagnostics from the tab set and expose them through an About window opened by a lower-left Settings action.

## Next Step

Review visually in a real Qt session if desired; focused offscreen behavior and translation tests pass.
