# Execution Task

## Objective & Hypothesis

- Objective: Fix Settings LLM provider switching so moving between configured providers does not copy the previously visible provider form into the newly selected provider.
- Hypothesis: `QComboBox.currentIndexChanged` fires after the combo index changes, while SettingsDialog stores the visible form by reading the combo's current index. Tracking the active provider form index separately prevents writing stale form data into the wrong provider config.

## Guardrails Touched

- Settings UI owns provider form editing state.
- LLM Service remains the owner of provider/model validation, persistence shape, and provider resolution.
- SQLite `xenix.db` is not modified; global provider config remains in `config/agent_settings.json`.

## Verification

- Command: `pdm run pytest tests/test_settings_dialog.py tests/test_agent_settings.py -q`
- Observed: 8 passed.
- Command: `pdm run pytest tests/test_i18n.py tests/test_main.py -q`
- Observed: 44 passed.
- Command: `pdm run pytest tests/test_settings_dialog.py tests/test_agent_settings.py tests/test_i18n.py tests/test_main.py -q`
- Observed: 52 passed after strengthening the regression test to cover editing one provider before switching to another.
- Command: `pdm run check`
- Observed: passed.
