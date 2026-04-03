# Xenix Native

Respond and think in English.
Keep this file as a lightweight dispatcher, not a constitutional rulebook.

## Dispatch

- Mode A, exploration: vague request, unknown causality, or unstable requirements. Load `docs/00-meta/mode-a-explore.md` and work only in `tasks/`.
- Mode B, solidification: requirements are stabilizing but not yet confirmed. Load `docs/00-meta/mode-b-solidify.md`, restate scope, and wait for confirmation before durable-doc updates or code.
- Mode C, execution: bounded implementation work with known causality. Load `docs/00-meta/mode-c-execute.md`, check local `AGENTS.md` files near the target, then restate and edit tests or code.
- Mode D, diagnosis: crashes, anomalies, or data corruption. Load `docs/00-meta/mode-d-diagnose.md`, stay read-only, gather telemetry, and write diagnostics in `tasks/` before fixing anything.

## Pacing Layers

- `docs/30-unit-tdd/` holds slow-moving logical structure.
- `src/**/AGENTS.md` holds fast-moving local hazards close to the code they protect.
- `docs/15-alignment/` is optional and only for repeated coordination drift.

## Guardrails

- Do not create or update durable docs outside the canonical layers.
- Do not create new planning records outside `tasks/active/`.
- Preserve `ml/` as-is unless the task explicitly requires migrating or deleting legacy model scripts.

## Quick commands

- `pdm install`
- `pdm run dev`
- `pdm run test`
- `pdm run check`
