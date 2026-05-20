# Chatbot I18n Execution

## Objective & Hypothesis

Fix untranslated user-facing Chatbot shell strings in the native Qt UI. Hypothesis: the immediate leak is local to `ThreadDetailView`, `ToolCallItem`, and Chatbot-generated fallback/status text because these widgets do not provide `retranslate_ui()` and are absent from the Qt translation catalogs.

## Guardrails Touched

- UI layer owns visible Chatbot controls, message rendering, attachment intake, and error presentation.
- Service-generated tool summaries remain service-owned; do not change persisted Agent Harness semantics in this slice unless verification proves the UI cannot bound the leak.
- Existing build-commit settings changes in translations and tests are preserved.

## Verification

- Refresh Qt `.ts` catalogs and compile `.qm` files.
- Add focused language-switch assertions for Chatbot controls and UI-generated message text.
- Run targeted i18n/main-window tests.

Results:

- `pdm run i18n-extract`
- `pdm run i18n-compile`
- `pdm run pytest tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell -q` -> passed
- `pdm run pytest tests/test_main.py::test_thread_detail_view_thinking_event_is_bottom_temporary_message tests/test_main.py::test_thread_detail_view_updates_one_assistant_message_by_id -q` -> passed
- `pdm run pytest tests/test_i18n.py -q` -> passed
- `pdm run pytest tests/test_main.py -k "chatbot or thread_detail_view or artifact_link" -q` -> passed
- `pdm run check` -> passed

Note: the targeted `tests/test_main.py` pytest runs exited successfully but emitted a Windows temp-directory cleanup `PermissionError` during pytest atexit cleanup.
