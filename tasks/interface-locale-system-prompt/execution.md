# Execution Task

## Objective & Hypothesis

- Objective: Inject the current Xenix UI locale into new Agent thread system prompts and strengthen non-technical business-language guidance.
- Hypothesis: Passing the UI locale at thread creation keeps model language behavior aligned with the application interface without rewriting old persisted threads.

## Pre-Execution Restatement

- Target: Agent thread system prompt creation and MainWindow-to-Harness thread creation inputs.
- Current state and context: The default prompt says "Communicate in the user's language" and is persisted per thread when a thread is created.
- Operation: Replace user-language inference with explicit interface-locale wording, add locale input to thread creation paths, and pass `TranslationManager.current_locale()` from UI.
- Scope included: New thread creation, implicit first-turn thread creation, focused tests.
- Scope excluded: Rewriting existing persisted thread prompts, changing supported locale codes, changing translation files.
- Invariants: System messages remain hidden; artifact link rules remain unchanged; legacy custom `system_prompt` input remains authoritative.
- Likely affected files: `src/xenix/services/storage/models.py`, `src/xenix/services/agent/conversation_store.py`, `src/xenix/services/agent/harness_service.py`, `src/xenix/ui/main_window.py`, related tests.
- Uncertainty: Existing dirty worktree has unrelated changes; edits must avoid reverting them.

## Guardrails Touched

- Agent Harness owns Thread and system prompt semantics.
- Chatbot UI owns current interface locale and user input collection.

## Plan

1. Add a default prompt builder that accepts an interface locale.
2. Thread locale through ConversationStore, AgentHarnessService, and MainWindow.
3. Add focused tests and run the relevant subset.

## Verification

- Command: `pdm run pytest tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py::test_agent_harness_projects_thread_system_prompt_as_first_provider_message tests/test_main.py::test_main_window_submit_chat_message_injects_interface_locale`
- Expected: ConversationStore formats `zh_CN` into the default prompt, Harness projects that prompt as the first provider message, and MainWindow passes the current UI locale into submit inputs.
- Observed: 13 passed.

## Promotion Notes

- Durable truth candidates: New Agent threads format the default system prompt with the current application interface locale; old persisted prompts are not rewritten.
- Keep in task only: The focused verification command and dirty-worktree note.
