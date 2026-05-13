# ChatBox UI Reference Research

## Objective & Hypothesis

Rework the Qt Native ChatBox around current mainstream chatbot interface patterns while keeping Xenix focused on data-analysis work.

The working hypothesis is that the first Xenix ChatBox should follow the structure shared by ChatGPT, Claude, and Cherry Studio:

- a centered reading column for the conversation
- a persistent bottom composer
- direct file attachment and drag/drop
- explicit tool/result visibility
- quiet window-level controls such as Settings outside the main conversation body

## References

- OpenAI ChatGPT file workflows: https://openai.com/academy/working-with-files/
- OpenAI ChatGPT Projects: https://help.openai.com/en/articles/10169521-using-projects-in-chatgpt
- Anthropic Claude file uploads: https://support.claude.com/en/articles/8241126-upload-files-to-claude
- Anthropic Claude artifacts: https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them
- Cherry Studio conversation interface: https://docs.cherry-ai.com/docs/en-us/cherry-studio/preview/chat

## Claims Applied

- ChatGPT emphasizes file upload from the composer/tool menu and keeping files inside a conversation/project context.
- Claude supports direct drag/drop into the chat and uses artifacts as a separate result surface for generated outputs.
- Cherry Studio exposes a dense desktop chat box with attachment, model/tool controls, message display settings, context controls, and token information.

## Xenix UI Direction

- Keep the central pane as ChatBox only.
- Keep Settings as a window-level action in the header.
- Use a centered conversation column.
- Render assistant output as list-style content for readability.
- Render user messages as right-aligned compact bubbles.
- Render tool results as bordered cards and turn end as a divider.
- Use a bottom composer with a `+` attachment action, file chips, multiline input, and Send/Stop control.
- Keep artifact links inside markdown; richer preview remains a follow-up.

## Verification

- `python -m compileall src tests`
- `pdm run pytest tests/test_main.py tests/test_i18n.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_foundation.py`

