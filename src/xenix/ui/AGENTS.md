# UI Guidance

Applies to `src/xenix/ui/`; `widgets/AGENTS.md` adds shared-widget guidance.

- Obtain domain state through services; UI owns presentation and user intent.
- Translate changed user-visible text, preserve internal identities, and handle `QEvent.LanguageChange`. Run translation extraction and compilation after completing the affected catalogs.
- Stop UI-owned timers and quiesce background work when their window closes.
- Startup animation and Windows message painting have native Qt constraints. Before changing either, read [desktop rendering seams](../../../docs/30-unit-tdd/application-composition.md#desktop-rendering-seams).
- Feature composition and exception presentation belong to [Application Composition](../../../docs/30-unit-tdd/application-composition.md). Shared widgets stay policy-light; prefer composition over cross-dialog inheritance.
