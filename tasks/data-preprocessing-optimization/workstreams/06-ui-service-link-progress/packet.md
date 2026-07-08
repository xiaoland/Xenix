# UI Service Link Progress

## Objective & Hypothesis

Service-owned link activation can be slow because dataset activation may export a workbook. UI should remain interactive while the service boundary does that work.

## Status

verified

## Durable Owners / Blast Radius

- `MainWindow`
- `ThreadDetailView` service link signal path
- Qt thread/signal behavior
- i18n catalogs

## State Diff

From: service-owned link activation ran synchronously on the Qt UI thread and used a modal progress surface.

To: `MainWindow` starts background activation, shows non-modal indeterminate progress, closes progress on success/failure, and updates progress strings on language switch.

## Invariants

- UI chooses execution mode only; service boundaries still resolve/export/open.
- Progress must not block main-window interaction.
- Worker failures return to the UI thread and render an error.
- Visible progress text must participate in i18n retranslation.

## Decisions Consumed

- `ArtifactService` owns OS file open.
- `LinkRouter` remains activation authority.
- Progress is non-modal.

## Open Questions

None blocking.

## Verification Plan

- `_open_service_link()` returns promptly when activation blocks.
- Progress dialog is `Qt.NonModal`.
- Success and failure close the progress dialog.
- Language switching updates visible progress title/label.

## Verification Run Log

- Covered by `pdm run python -m pytest -q`: 304 passed, 3 warnings.

## Next Action

If real exports are long enough to need percentage progress, design a service-side progress contract instead of adding UI polling heuristics.
