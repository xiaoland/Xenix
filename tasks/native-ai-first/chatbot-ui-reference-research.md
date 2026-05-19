# Chatbot UI Reference Research

## Objective & Hypothesis

Rework the Qt Native Chatbot around current mainstream chatbot interface patterns while keeping Xenix focused on data-analysis work.

The working hypothesis is that the first Xenix Chatbot should follow the structure shared by ChatGPT, Claude, and Cherry Studio:

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
- Cherry Studio exposes a dense desktop Chatbot with attachment, model/tool controls, message display settings, context controls, and token information.

## Xenix UI Direction

- Keep the central pane as Chatbot only.
- Keep Settings as a window-level action in the header.
- Use a centered conversation column.
- Render assistant output as list-style content for readability.
- Render user messages as right-aligned compact bubbles.
- Render tool results as bordered cards and turn boundaries as dividers before user messages.
- Use a bottom composer with a `+` attachment action, file chips, multiline input, and Send/Stop control.
- Keep artifact links inside markdown; richer preview remains a follow-up.

## Qt Widgets Layout Debugging

GammaRay is the preferred interactive debugger for the current Qt Widgets layout work. Its Widget Inspector can browse the runtime `QWidget` and `QLayout` hierarchy, pick widgets from the target window, show a layout diagnostic overlay, inspect/edit geometry-related properties live, and use visibility bisection to find the owner of unexpected space.

Relevant references:

- GammaRay Widget Inspector: https://docs.kdab.com/gammaray-manual/latest/gammaray-widget-inspector.html
- GammaRay Widget Layouting example: https://docs.kdab.com/gammaray-manual/latest/gammaray-widget-layouting-example.html
- GammaRay installation compatibility: https://docs.kdab.com/gammaray-manual/latest/gammaray-install.html
- Qt layout management: https://doc.qt.io/qt-6/layout.html
- Qt `QObject::dumpObjectTree()` / `dumpObjectInfo()`: https://doc.qt.io/qt-6/qobject.html

Local environment check on 2026-05-13:

- PySide6: `6.10.2`
- Qt runtime: `6.10.2`
- Architecture: `64-bit`
- `gammaray` is not currently available on `PATH`.
- `winget search GammaRay` did not find an installable package.
- KDE Craft is not currently available on `PATH`.

GammaRay setup must match the target Qt runtime closely. The probe compatibility is affected by Qt version, Qt configuration, architecture, compiler vendor, and debug/release settings, with Windows compiler/ABI matching being especially important. For this project, the likely path is a GammaRay 3.3.x build compatible with Qt 6.10.x and 64-bit Windows.

Debugging workflow for Chatbot layout issues:

1. Run Xenix with mock thread data so all message variants are visible.
2. Start GammaRay against the running `python.exe` process or launch Xenix through `gammaray`.
3. Use Widget Inspector on `MainWindow -> Chatbot -> chatScrollArea -> chatMessageColumn -> chatMessage*` and `chatComposer -> chatComposerEditor -> attachButton/sendButton`.
4. Verify actual geometry, `sizeHint`, minimum/maximum size, size policy, layout margins, layout spacing, and visibility on each suspect node.
5. Use widget picking and the diagnostic overlay to identify unexpected empty space and misaligned composer controls.
6. Patch the smallest owning widget/layout and rerun the targeted UI tests.

Fallback while GammaRay is unavailable:

- Add stable `objectName` values to intermediate Chatbot containers and rows.
- Add a dev-only layout dump helper guarded by an environment flag, printing widget class, object name, geometry, size hints, size policy, min/max size, layout margins, and spacing.
- Use Qt's built-in `dumpObjectTree()` / `dumpObjectInfo()` as a coarse object hierarchy check.
- Keep screenshot/manual inspection as confirmation after the structural layout data is known.

## Verification

- `python -m compileall src tests`
- `pdm run pytest tests/test_main.py tests/test_i18n.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_foundation.py`
