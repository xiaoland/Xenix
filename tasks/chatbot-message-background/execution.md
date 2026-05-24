# Chatbot Message Background

## Objective & Hypothesis

Objective: fix Win11 Chatbot text message rendering where the user message body shows an extra white rectangle and assistant messages inherit a white body background.

Hypothesis: `QTextBrowser` / `QAbstractScrollArea.viewport()` keeps an opaque `QPalette.Base` role under the native Windows style even when `autoFillBackground` is disabled. Making the message text browser and viewport `Base` role transparent should preserve native widgets while removing the white document fill.

## Guardrails Touched

- `src/xenix/ui/chatbot.py`: Chatbot message presentation only.
- `CONTRIBUTING.md`, `docs/20-product-tdd/runtime-boundaries.md`, and `docs/30-unit-tdd/chatbot-ui.md`: testing intent and UI component styling contract.
- No stylesheet or durable Agent Harness/storage contract changes.

## Verification

- No new narrow regression test was added for this bug; existing Chatbot UI tests remain the verification surface.
- `git diff -- tests/test_main.py` -> no diff.
- `pdm run pytest tests/test_main.py -q` -> 33 passed.
- `pdm run check` -> passed.
