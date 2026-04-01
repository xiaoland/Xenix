# Xenix Native

Respond and think in English.
Stop and ask the user about trade-offs if a decision would hurt maintainability or readability.

## Primary areas

- `src/xenix` contains the desktop application package, bootstrap code, runtime services, and Qt Widgets UI.
- `tests` contains Python unit tests for the native shell.
- `scripts` contains local developer helpers.
- `ml` keeps the existing Python model scripts that will be integrated into the native flow later.
- `docs` stores canonical durable documentation layers.
- `tasks` stores volatile planning and execution records.

## Quick commands

- `pdm install`
- `pdm run dev`
- `pdm run test`
- `pdm run check`

## Execution protocol (SVC v9.1)

- Select execution mode from request ambiguity:
  - Mode A (exploration): high ambiguity or fuzzy requests. Work only in `tasks/`. Do not edit durable docs or production code.
  - Mode B (solidification): requirements are becoming stable. Classify truths by durable layer, restate scope, and wait for confirmation before durable-doc updates and coding.
  - Mode C (execution): specific and bounded implementation work. Read relevant docs, restate execution scope, then implement tests and code.

### Pre-execution restatement

For reference-sensitive or logic-altering work, restate before editing:

- target path or anchor
- current state and context
- intended operation
- scope included
- scope excluded
- invariants that must hold
- likely affected files
- uncertainty or assumptions

### Documentation layers

- Durable docs:
  - `docs/10-prd/`
  - `docs/15-alignment/`
  - `docs/20-product-tdd/`
  - `docs/30-unit-tdd/`
  - `docs/40-deployment/`
- Volatile planning:
 	- `tasks/active/`
 	- `tasks/archive/`

### L2 hard rule

- Do not create or update durable docs outside canonical layers.
- Do not create new planning records outside `tasks/active/`.

## Native rules

- Use PySide6 with Qt Widgets. Do not introduce QML unless the user asks for that direction explicitly.
- Keep bootstrap code small and explicit: `main.py`, `app.py`, and `ui/`.
- Keep application path conventions stable. `XENIX_APP_HOME` is the local override for runtime directories.
- Prefer simple Python standard library solutions before adding new dependencies.
- Preserve `ml/` as-is unless the task explicitly requires migrating or deleting legacy model scripts.
