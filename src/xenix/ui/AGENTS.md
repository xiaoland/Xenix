# UI Guidance

## Scope

Applies to the entire `src/xenix/ui/` subtree. `widgets/AGENTS.md` adds narrower shared-widget rules.

## Tripwires

- Keep UI service-driven: do not parse datasets, invent storage paths, or reconstruct domain state. Cross-unit authority is owned by [Product TDD](../../../docs/20-product-tdd/README.md).
- Route changed user-visible text through Qt translation, preserve internal identity separately, and handle `QEvent.LanguageChange`. Run extract, complete the affected catalog entries, compile, and verify the changed surface.
- A dialog that starts a `QTimer` owns shutdown in `closeEvent()`; background refresh must not survive window closure.
- Prefer focused composition over cross-dialog inheritance when presentation is shared.

### Windows custom-paint hazard

The black user-message bubble deliberately uses `UserMessageCard` plus `UserMessageBody` custom painting. Do not reintroduce a `QFrame.StyledPanel`, `QTextBrowser`, or `QAbstractScrollArea` background stack: on Windows their independent repaint paths can cover the black card or text during updates. Keep the card/body styles transparent and verify `test_thread_detail_view_user_message_uses_native_black_panel` in `tests/test_main.py` after changing this path.
