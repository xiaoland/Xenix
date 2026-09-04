# UI Guidance

## Scope

Applies to the entire `src/xenix/ui/` subtree. `widgets/AGENTS.md` adds narrower shared-widget rules.

## Tripwires

- Keep UI service-driven: do not parse datasets, invent storage paths, or reconstruct domain state. Cross-unit authority is owned by [Product TDD](../../../docs/20-prd-tdd/README.md).
- Route changed user-visible text through Qt translation, preserve internal identity separately, and handle `QEvent.LanguageChange`. Run extract, complete the affected catalog entries, compile, and verify the changed surface.
- A dialog that starts a `QTimer` owns shutdown in `closeEvent()`; background refresh must not survive window closure.
- Prefer focused composition over cross-dialog inheritance when presentation is shared.

### Startup splash animation

The bootstrap path performs process-global Python and C-extension imports on the application thread because importing them concurrently with PySide has caused native aborts. Keep the splash as a top-level `QQuickView` and keep its continuous motion in Qt Quick `Animator` types so the scene-graph render thread can present frames while the application thread is blocked. Do not replace it with a `QWidget` timer, a regular QML animation, or `QQuickWidget`; those all depend on the application thread. Stage text may continue to update at bootstrap boundaries. The packaged splash intentionally collects only its base QML modules through `scripts/pyinstaller_hooks/hook-PySide6.QtQml.py`; add a module there when the scene begins importing it rather than restoring PyInstaller's full QML-tree collection.

### Windows custom-paint hazard

The black user-message bubble deliberately uses `UserMessageCard` plus `UserMessageBody` custom painting. Do not reintroduce a `QFrame.StyledPanel`, `QTextBrowser`, or `QAbstractScrollArea` background stack: on Windows their independent repaint paths can cover the black card or text during updates. Keep the card/body styles transparent and verify the black user-message bubble after changing this path.
