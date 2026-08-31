# Phase 6 — Frozen implementation boundaries

## Decisions before implementation

Independent read-only maps confirmed that history owns list/actions/title jobs,
whereas Settings/Knowledge/detail construction is only forwarded by MainWindow.
These are separate lifecycles, not a reason to introduce an application-service bag.

- An auxiliary-window coordinator receives feature-specific factories, owns lazy
  Settings/Knowledge windows, transient details and update presentation. Production
  factories are composed in `app.py`. MainWindow only requests opening and shutdown
  and observes settings-saved to refresh model choices.
- `HistoryPanel` owns list rendering, selection, rename/delete/title presentation.
  A typed history port returns immutable summaries; the production adapter delegates
  to the existing harness. Opening/new-thread requests go to the shell: conversation
  snapshot authority and generation invalidation remain at the Phase 5 seam.
- History title execution is injected. One active generation is sufficient; close,
  deletion and missing list membership invalidate delayed completions. A running
  state query guards deletion, without reaching into conversation widgets.
- Preserve existing stylesheet object names and translation context for moved text.
  Add translated untitled fallback and canonical repeated-item semantic references.
- MainWindow retains only actual conversation/link/model/locale dependencies and
  the two feature seams. Benchmark DB access must use its own runtime paths, and
  Knowledge lookup must use the actual window type, not obsolete shell fields.
- Settings provider/OCR presentation extraction follows the first integrated slice;
  no lab scenario may fake the full Settings service graph. Chat internals are not
  split merely to hit a line-count threshold.

### Settings presentation interfaces

The first Settings extraction is deliberately two independent production widgets,
because the provider/global-model cards belong to the AI tab while the OCR card
belongs to the Knowledge Base tab.  They must not be wrapped in a synthetic
combined settings pane or reparented just to serve the lab.

```text
ProviderSettingsEditor(settings: LLMSettings, parent: QWidget | None = None)
  load_settings(settings: LLMSettings) -> None
  current_settings() -> LLMSettings
  retranslate_ui() -> None

OcrSettingsCard(deployment: PaddleOcrDeploymentPort | None,
                parent: QWidget | None = None)
  activate() -> None
  deactivate() -> None
  shutdown() -> None
  retranslate_ui() -> None
```

`PaddleOcrDeploymentPort` is the only OCR dependency: `status_snapshot()`,
`verify_active()`, and `install(progress)`.  The real deployment service is
structurally compatible.  OCR status/install jobs remain owned by
`OcrSettingsCard`; the dialog merely forwards its show/hide/shutdown lifecycle.
Provider editing owns only an in-memory `LLMSettings` draft.  Persistence remains
the dialog's save orchestration.  Moved strings use the explicit
`QCoreApplication.translate("SettingsDialog", literal)` form so both the
translation context and lupdate discovery remain stable.

## Sequence and acceptance

1. Implement/test auxiliary coordinator and history independently; root integrates
   shell and production composition after the interfaces are fixed.
2. Verify focused conversation regressions, history action/late completion tests,
   auxiliary lazy creation/update wiring/shutdown/language propagation, strict ports.
3. Admit a synthetic production HistoryPanel scene, with explicit synthetic fixture
   authority (not a misleading screenshot of a fake full MainWindow).
4. Extract honest provider/OCR presentation and register its scenario; then run full
   tests, translations, type checks, native and isolated production smoke.

CI acceptance is separate from local verification. Native CI triggers on PRs to
main; no direct push to main is technically required. The repository currently
permits only develop-to-main PRs, so the requested clean baseline needs an explicit
task exception before opening a feature-to-main draft PR. No unrelated develop or
dirty-worktree changes may enter this branch.

## Results

The shell now has eight constructor inputs (down from 23 after Phase 5) and
591 lines (down from 951). SettingsDialog has 778
lines (down from 1,246); the old provider/OCR fields, handlers, and hidden widget
graphs are removed, not retained as compatibility aliases. `SettingsTab` is a
lightweight import independent of the full dialog. Forty boundary modules are
now checked strictly.

Both conditional scenarios are admitted using the actual production components.
History is explicitly panel-only; Provider/OCR are composed side by side, without
moving their production AI/Knowledge tab placement. Main shell contracts arrange
only the services they use. Headed benchmark service inspection now enters at an
application-owned `on_services_ready` callback; its handles are never passed into
MainWindow. Existing conversation event observers remain unchanged.

### Rehearsal findings

- A scenario handle scheduling deletion while pytest-qt also owns the widget
  left a live Python wrapper for an already deleted HistoryPanel. The test adapter
  now gives deletion solely to qtbot and attaches cleanup before close.
- Offscreen Windows initially reported an empty system font database. Loading
  the icon font then made requested Segoe UI resolve to `codicon`: history appeared
  uppercase and Settings became square glyphs. Existing capture-only images must
  not be promoted. The lab now registers already-installed Segoe UI faces locally
  in the process, rejects mismatched/missing text glyphs, and records resolved font
  metadata. A corrected 1050x760 Settings capture is 36,349 bytes with resolved
  Segoe UI Regular and exact match. No system font or user configuration changed.
- Translation extraction retained every moved context and found only one new
  string, the previously hard-coded untitled history fallback. Both catalogs now
  contain 383 finished entries. Provider LanguageChange preserves unsaved fields
  and selected models while updating translated option labels.

The font policy follows Qt's distinction between a requested
[QFont and actual QFontInfo](https://doc.qt.io/qt-6/qfontinfo.html), and its
[process-local font registration](https://doc.qt.io/qt-6/qfontdatabase.html#addApplicationFont).

### Verification

- `pdm run check`: passed (40 strict modules).
- Native Windows smoke: 1 passed in 2.83s.
- Agent benchmark offline: 33 passed in 33.67s; headed discovery: 13 cases.
- Scoped UI contracts: 55 passed in 22.34s after the font fix, including three
  subprocess failure-publication probes. UI plus pure models passed 63/63 before
  enabling the same font setup for every scoped UI contract.
- Full portfolio: final run 208 passed in 150.71s after the added provider
  LanguageChange case and scoped failure-font setup (488 existing joblib/NumPy
  deprecation warnings). Initial integrated run: 207 passed in 149.99s.
- Isolated production smoke: passed with unique
  `xenix-ui-dx-phase6-bd1de6203b004bd6bf4f4aaba0438db7` home and OTEL disabled;
  the exact synthetic directory was removed after completion. No user home used.
- Five final captures plus index: passed; artifacts are under
  `ui-artifacts/phase6-final/`, all resolve to Segoe UI Regular, exact match.
- Independent integration review: no functional blockers; its remaining private
  history-refresh call was replaced with the public shell `refresh_history` seam.
- Actual GitHub artifact inspection: pending the task-specific PR-route exception;
  no main/develop mutation or remote publication has occurred.

### Remaining task boundaries

Phase 7's agent-safe whole-app profiles and Phase 8's packaging/final measurement
remain separate. The history title delivery gate does not cancel provider I/O
already in flight; it only prevents late presentation changes. No new service
cancellation semantics, chatbot file split, or pixel baseline is claimed here.
The artifact privacy audit should explicitly decide whether safe repeated-item
references may appear in synthetic tree JSON (currently available on widgets,
but omitted by the generic redacted tree serializer).
