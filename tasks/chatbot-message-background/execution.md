# Chatbot Message Background

## Objective & Hypothesis

Objective: fix Win11 Chatbot text message rendering where the user message body shows an extra white rectangle and assistant messages inherit a white body background.

Hypothesis: `QTextBrowser` / `QAbstractScrollArea.viewport()` keeps or re-enters native light background roles under the native Windows style even when `autoFillBackground` is disabled. The previous transparent-`Base` fix did not fully bind the user-message visual unit because the user-specific palette only sets foreground/link roles; `AlternateBase`, selection roles, and a black fallback for the child text browser/viewport remain platform-owned.

Current Win11 report: the user-message card container is black, but the text/document area still shows an extra white background, causing white text to blend into it. This suggests the leak is inside the nested text browser or rich-text document paint path, not the outer card.

## Guardrails Touched

- `src/xenix/ui/chatbot.py`: Chatbot message presentation only.
- `CONTRIBUTING.md`, `docs/20-product-tdd/runtime-boundaries.md`, and `docs/30-unit-tdd/chatbot-ui.md`: testing intent and UI component styling contract.
- No stylesheet or durable Agent Harness/storage contract changes.

## Verification

- No new narrow regression test was added for this bug; existing Chatbot UI tests remain the verification surface.
- `git diff -- tests/test_main.py` -> no diff.
- `pdm run pytest tests/test_main.py -q` -> 33 passed.
- `pdm run check` -> passed.

## 2026-06-09 Follow-up Diagnosis

Symptom: User reports the Win11 `UserMessage` text area still has a white background while the user-message container itself is black.

Evidence:

- `render_chat_markdown("User message.")` returns `<p>User message.</p>`; the renderer does not inject a white background.
- `ChatMessageBubble(author="You")` currently yields `card.Window=#ff000000`, `browser.Window=#ff000000`, and `browser.Base=#00000000`, but `browser.AlternateBase=#fff7f7f7`; viewport roles match the browser roles.
- Current regression test only checks the user card black panel and user text/link color. It does not assert the text browser/viewport background roles for user messages.
- Offscreen/default local render probes did not reproduce a large white rectangle, only glyph pixels; the remaining risk is platform-theme-specific fallback behavior on Win11.

Next step:

- After explicit human start, update only `src/xenix/ui/chatbot.py` and the targeted Chatbot UI test in `tests/test_main.py`.
- Bind the complete user-message text browser/viewport palette contract: black foreground-on-background roles for the user message visual unit, including `Base`, `Window`, `AlternateBase`, selection, link, and visited-link roles.
- Keep assistant/tool detail text browsers on the existing transparent native path.

## 2026-06-09 Execution

Change:

- `src/xenix/ui/chatbot.py`: user message text browser and viewport now inherit a complete black visual-unit palette for `Window`, `Base`, `AlternateBase`, foreground/link roles, and selection roles.
- `tests/test_main.py`: `test_thread_detail_view_user_message_uses_native_black_panel` now asserts the same roles on both `QTextBrowser` and `viewport()`, including opaque black background roles and white text/link/selected-text roles.

Verification:

- `pdm run pytest tests/test_main.py::test_thread_detail_view_user_message_uses_native_black_panel -q` -> passed.
- `pdm run pytest tests/test_main.py -q` -> 40 passed.
- `pdm run check` -> passed.
