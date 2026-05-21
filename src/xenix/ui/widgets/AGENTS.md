# Shared Widget Guidance

## Scope

This guidance applies to `src/xenix/ui/widgets/`.

## Rules

- Shared widgets must stay policy-light. Avoid baking old predefined-workflow assumptions into widgets that can serve Chatbot renderers or technical views.
- When a specific view needs stricter behavior, prefer an explicit constructor flag or narrow adapter over a forked widget copy.
- Widgets may manage local selection or presentation state, but they must not call services or own filesystem business logic.
- User-visible strings must participate in `retranslate_ui()` and respond to `QEvent.LanguageChange`.
- Preserve deterministic value ordering when widgets return selected columns or rows; downstream services and tests rely on stable ordering.
- If a widget begins carrying view-specific workflow logic, move that logic back into the parent dialog or a service instead of growing the widget contract.
