# TP-20 — Guided AMD UI and Settings Conflict Handling

**Delivery note:** the original surface was incomplete. The corrective packet
and acceptance delta are owned by
[TP-20A](TP-20A-guided-amd-ui-repair.md); that file supersedes Local/Private
chooser and pre-enrollment wording below for the current Windows product.

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

- collect one Private SSH enrollment plus deployment intent; Install performs
  both actions and there is no separate Save or ML Worker route;
- offer only the current Windows-to-Linux-Radeon Private SSH placement; no Local
  Linux desktop claim, model, runtime, cache, GPU tuning, fallback, or
  “continue anyway” choice;
- run long operations off the UI thread through service commands;
- validate pure field syntax before scheduling; check local file availability in
  the worker; return either failure to the exact field with a localized
  explanation and stable redacted support code;
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
- an active operation cannot be silently hidden; app shutdown suppresses late
  delivery while leaving durable forward work truthful;
- stale snapshot cannot overwrite an AMD upsert;
- conflict/reload/reapply preserves user intent and secrets;
- strings are translatable and tests cover validation, retry checkpoint,
  operational/incompatible/degraded, SSH error, and redaction states;
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
