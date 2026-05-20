# UI Layer Guidance

## Scope

This guidance applies to `src/xenix/ui/` except `src/xenix/ui/widgets/`, which may add narrower local rules.

## Rules

- Keep Chatbot as the default operator path. `MainWindow` should host the Chatbot-first shell.
- Treat Message rendering, file drop intake, artifact preview, tool progress, and stop control as first-class UI surfaces.
- UI code must stay service-driven. Do not parse datasets, invent storage paths, or reconstruct hidden container state in the UI layer.
- Every new or changed user-visible UI string must go through the Qt translation pipeline. Use `self.tr(...)` for QObject/widget-owned text such as labels, buttons, placeholders, tooltips, dialog titles, and file-dialog filters; use `QCoreApplication.translate(context, text)` for module-level helpers or renderers that are not QObjects. Any dialog or widget with user-visible text must provide `retranslate_ui()` and respond to `QEvent.LanguageChange`; parent windows should call child `retranslate_ui()` when they own the language-switch refresh path. Do not translate internal state keys, `objectName` values, style/layout sentinel strings, enum values, or persistence payload identities; keep internal identity separate from display text. After touching translatable UI text, run `pdm run i18n-extract`, complete `src/xenix/translations/xenix_zh_CN.ts`, run `pdm run i18n-compile`, and add or update a language-switch test for the affected surface.
- Any dialog that starts a `QTimer` must also own its shutdown in `closeEvent()` so background refresh does not survive window closure.
- Prefer small focused widgets plus shared renderers over cross-dialog inheritance when Chatbot content and technical views overlap.

## Boundaries

- Agent Harness service owns Thread, Turn, Message, tool-call, tool-result, run recording, and LLM tool execution.
- Artifact, data, and ML services own domain behavior and resolved output paths.
- UI opens files or exports only after services resolve the canonical path or dataset id.
