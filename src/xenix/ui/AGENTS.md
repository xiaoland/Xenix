# UI Layer Guidance

## Scope

This guidance applies to `src/xenix/ui/` except `src/xenix/ui/widgets/`, which may add narrower local rules.

## Rules

- Keep ChatBox as the default operator path. `MainWindow` should host the ChatBox-first shell.
- Treat Message rendering, file drop intake, artifact preview, tool progress, and stop control as first-class UI surfaces.
- UI code must stay service-driven. Do not parse datasets, invent storage paths, or reconstruct hidden container state in the UI layer.
- Any dialog or widget with user-visible text should provide `retranslate_ui()` and respond to `QEvent.LanguageChange`.
- Any dialog that starts a `QTimer` must also own its shutdown in `closeEvent()` so background refresh does not survive window closure.
- Prefer small focused widgets plus shared renderers over cross-dialog inheritance when ChatBox content and technical views overlap.

## Boundaries

- Agent Harness service owns Thread, Turn, Message, tool-call, tool-result, run recording, and LLM tool execution.
- Artifact, data, and ML services own domain behavior and resolved output paths.
- UI opens files or exports only after services resolve the canonical path or dataset id.
