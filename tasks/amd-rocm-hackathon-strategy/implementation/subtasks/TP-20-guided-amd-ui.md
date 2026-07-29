# TP-20 — Guided AMD UI and Settings Conflict Handling

## Outcome

Expose one guided deployment workflow and make UI/background settings changes
honest without moving lifecycle or settings authority into Qt widgets.

## Owned Mutation

- add `src/xenix/ui/amd_setup.py`;
- add `src/xenix/ui/amd_deployment_tasks.py`;
- modify `src/xenix/ui/settings_dialog.py` and
  `src/xenix/ui/main_window.py`;
- update translation catalogs;
- add/extend Settings and AMD setup UI tests.

No deployment state machine, SSH command, manifest logic, or provider factory is
implemented in UI.

## Behavior

- collect Local/Private intent and opaque credential/trust references;
- offer only `This computer` or one pre-enrolled Private SSH target; no model,
  runtime, port, cache, GPU tuning, fallback, or “continue anyway” choice;
- run long operations off the UI thread through service commands;
- render resolve/acquire/verify/install/compile/register phases and typed reasons;
- show installed/operational/degraded/blocked as derived status;
- managed provider rows are read-only except normal independent selection;
- background registration refreshes a clean domain; a dirty domain keeps edits and
  shows a revision conflict requiring reload/reapply;
- LLM, Embedding, and OCR partial outcomes remain separate;
- deployment never auto-selects providers.

Settings save uses per-domain expected revision and no cross-domain transaction.
If one domain commits and another conflicts, the UI reports each outcome and never
rolls the committed domain back.

## Acceptance

- responsive/cancel-safe UI and bounded timers/workers;
- dialog close stops background work/timers safely;
- stale snapshot cannot overwrite an AMD upsert;
- conflict/reload/reapply preserves user intent and secrets;
- strings are translatable and tests cover clean/dirty/partial/error states;
- no live endpoint/token/process details are rendered.
- `main_window.py` consumes only a generic optional action contribution and imports
  no AMD service/UI type;
- removing the two AMD UI files, their namespaced translations, and the bounded
  action contribution leaves SettingsDialog and ordinary LLM/Embedding/Paddle/
  Knowledge UI constructible.

## Verification

- focused Qt/UI tests;
- translation checks;
- `pdm run check` and `pdm run smoke`.
