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
# QTextDocument / Win11 UserMessage Follow-up Research

## 2026-06-11 Diagnosis Notes

User re-tested on Windows 11 after commit `5677f09 Fix Chatbot user message background`; issue persists. This means the previous palette-only fix is insufficient.

Local evidence from current code:

- `render_chat_markdown("plain user text")` and `ChatMessageBubble(author="You")` do not produce explicit `background` or `bgcolor` in `QTextDocument.toHtml()`.
- `QTextDocument.rootFrame().frameFormat().background()`, first block background, and first block char background are all `NoBrush`.
- Current user message `QTextBrowser` and `viewport()` palettes are black for `Window`, `Base`, and `AlternateBase`, and white for text roles.
- Therefore the remaining white rectangle is not authored HTML or a missing palette role visible through introspection.

External research findings:

- Qt docs say `QPalette::Base` is used mostly as the background color for text entry widgets, but also warn that native styles such as Windows Vista/macOS may ignore palette roles for parts of drawing.
- `QWidget` docs also state that assigning palette roles is not guaranteed to change appearance under native styles, and recommends style sheets when palette does not achieve the intended result.
- Qt source shows `QTextEdit::paintEvent()` paints on the `QAbstractScrollArea` viewport, then delegates to `QWidgetTextControl::drawContents()` and finally to `QTextDocument` layout drawing. `QWidgetTextControl::getPaintContext()` uses the control palette as the paint context palette, but if a stylesheet style is present it explicitly asks `QStyleSheetStyle::styleSheetPalette()` to modify the paint context.
- QtCentre thread `QTextDocument background colour` reports the same shape: changing the edit palette changed only the area without text, while the background of the text/document area did not change; the practical solution reported was setting the `QPlainTextEdit` stylesheet background.
- Qt Forum thread `QTextEdit transparency in QGraphicsView` reports QTextEdit/QPlainTextEdit background staying white under Windows until frame/native painting was removed, while QLabel/QLineEdit did not show the issue.
- PyQt mailing-list report from 2007 similarly says QTextEdit objects did not follow the same palette setup that worked for QLineEdit.

Current root-cause claim:

The failed fix targeted the wrong authority. On Windows 11, `QTextBrowser`/`QTextEdit` is not reliably governed by `QPalette` for the rich-text document paint area. The text document is painted through `QWidgetTextControl`/`QTextDocumentLayout` inside a `QAbstractScrollArea` viewport, and the Windows native style can keep/restore a light text-editor background even when `browser.palette()` and `viewport().palette()` report black roles. In Qt's own paint path, stylesheet-derived palette is treated as a distinct input to the text paint context, which explains why forum fixes use `QTextEdit { background-color: ... }` rather than palette-only mutation.

Next discriminating implementation experiment, after explicit start:

- Apply a narrowly scoped stylesheet to the user-message `QTextBrowser` only, e.g. object-name-scoped `QTextBrowser#chatMessageBody { background-color: #000000; color: #ffffff; border: none; }`, plus selection colors.
- If the white rectangle remains, set the document body/root background explicitly by wrapping user-message HTML with a `body bgcolor="#000000"` or using `document().setDefaultStyleSheet("body { background-color: #000000; color: #ffffff; }")` before `setHtml()`, then reload the HTML.
- Verification should include a Windows-visible pixel probe or screenshot test, not only palette role assertions, because the palette can report black while native drawing remains white.

## 2026-06-11 Execution

Change:

- `src/xenix/ui/chatbot.py`: user messages now keep the black palette fallback but no longer rely on it as the primary authority. The user-message `QTextBrowser` exits the translucent path, receives an object-scoped stylesheet for black background, white text, and selection colors, and its `QTextDocument` receives a default stylesheet for body/block/table/link text.
- `tests/test_main.py`: user-message coverage now checks the widget stylesheet and `QTextDocument.defaultStyleSheet()` contract. Assistant message coverage now asserts that ordinary assistant text remains on the transparent native path with no stylesheet.

Verification:

- `pdm run pytest tests/test_main.py::test_thread_detail_view_message_text_uses_transparent_native_background tests/test_main.py::test_thread_detail_view_user_message_uses_native_black_panel -q` -> 2 passed.
- `pdm run pytest tests/test_main.py -q` -> 41 passed.
- `pdm run check` -> passed.

Open verification gap:

- Per user instruction, no Windows screenshot/pixel check was added in this slice.

## 2026-06-12 Screenshot Diagnosis

User supplied a Win11 screenshot after `7f1c5a8`. Observed state:

- Text glyphs and line rectangles are now on black.
- The user-message bubble interior around the text remains white.

Diagnosis:

- The previous `QTextDocument.defaultStyleSheet()` fix reached the document/block paint path, which explains why the text lines are black.
- The remaining white area is outside the document text/block rectangles. Candidate owners are the `QAbstractScrollArea.viewport()` background and the outer `QFrame` card background.
- Current code still leaves the outer user card as `QFrame.StyledPanel` with no stylesheet. It relies on `QPalette.Window` plus `autoFillBackground`, which is the same native-style-sensitive mechanism that already failed for QTextBrowser.
- Current `QTextBrowser#chatMessageBody` stylesheet also targets the scroll area widget, not the separate viewport child (`qt_scrollarea_viewport`) directly. Qt scroll-area discussions note that the main area is a separate viewport widget; styling only the scroll area can affect borders/edges without covering the main part.

Root-cause refinement:

The problem has two layers. `QTextDocument` background is now controlled, but the full user-message visual unit is still split between native-painted `QFrame.StyledPanel`, `QAbstractScrollArea`, the viewport child, and the rich-text document. Win11 still paints at least one non-document layer white.

Next likely fix after explicit start:

- Style the whole user-message visual unit, not only the text document:
  - `QFrame#chatMessageUser { background-color: #000000; border: 1px solid #000000; }`
  - `QTextBrowser#chatMessageBody, QTextBrowser#chatMessageBody QWidget#qt_scrollarea_viewport { background-color: #000000; color: #ffffff; border: none; }`
- Consider removing `QFrame.StyledPanel` for user messages or replacing it with stylesheet-owned border/background, because native `StyledPanel` can repaint the panel interior.

## 2026-06-12 Design Constraint

User preference: use a long-lived stable fix instead of accumulating multi-layer fallbacks.

Design implication:

- The durable fix should reduce native-style ownership rather than add more palette/stylesheet guards.
- The problematic topology is `QFrame.StyledPanel -> QTextBrowser/QAbstractScrollArea -> viewport -> QTextDocument`; each layer can paint a background independently.
- A stable UserMessage surface should have one rendering owner for the bubble background and text content. Candidate shape: a custom QWidget-backed rich-text bubble/body that paints the user-message panel itself and renders the `QTextDocument` directly, avoiding `QFrame.StyledPanel` and `QTextBrowser`/`QAbstractScrollArea` for user-message text.
- Assistant/tool messages can keep the existing transparent native path unless a separate symptom appears, because the current Win11 defect is specific to the black UserMessage visual unit.

## 2026-06-12 Execution

Change:

- `src/xenix/ui/chatbot.py`: User messages now render through `UserMessageCard` and `UserMessageBody`. `UserMessageCard` is a custom `QWidget` that paints the black bubble background itself. `UserMessageBody` renders a `QTextDocument` directly and handles anchor activation without `QTextBrowser` or `QAbstractScrollArea`.
- `tests/test_main.py`: user-message coverage now asserts the stable topology: no `QTextBrowser`, no native `QFrame.StyledPanel`, and no stylesheet-owned background fallback. Assistant message coverage still protects the existing transparent native path.
- `docs/30-unit-tdd/chatbot-ui.md`: recorded the durable invariant that user text message bubbles own their black background as a custom-painted visual unit.

Verification:

- `pdm run pytest tests/test_main.py::test_thread_detail_view_message_text_uses_transparent_native_background tests/test_main.py::test_thread_detail_view_user_message_uses_native_black_panel -q` -> 2 passed.
- `pdm run pytest tests/test_main.py -q` -> 41 passed.
- `pdm run check` -> passed.
- Local Qt render probe on Windows style showed `UserMessageCard` contains no `QTextBrowser`; sampled inner padding, text area, and bottom padding pixels were all `#ff000000`.

## 2026-06-12 Width Contract Adjustment

User clarified the UserMessage width contract: user messages should be at least 60% of the parent EventList column width and at most 80%.

Change:

- `docs/30-unit-tdd/chatbot-ui.md`: updated the Event Rendering contract from a 60% cap to a 60%-80% width band.
- `src/xenix/ui/chatbot.py`: UserMessage cards now set `minimumWidth=max(280, width*0.6)` and `maximumWidth=max(320, width*0.8)`.
- `tests/test_main.py`: width coverage now asserts both minimum and maximum constraints, plus actual width at least the minimum.
