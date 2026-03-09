# Xenix Native

Respond and think in English.
Stop and ask the user about trade-offs if a decision would hurt maintainability or readability.

## Primary areas

- `src/xenix` contains the desktop application package, bootstrap code, runtime services, and Qt Widgets UI.
- `tests` contains Python unit tests for the native shell.
- `scripts` contains local developer helpers.
- `ml` keeps the existing Python model scripts that will be integrated into the native flow later.
- `docs` stores native runbooks and branch-governance notes.

## Quick commands

- `pdm install`
- `pdm run dev`
- `pdm run test`
- `pdm run check`

## Native rules

- Use PySide6 with Qt Widgets. Do not introduce QML unless the user asks for that direction explicitly.
- Keep bootstrap code small and explicit: `main.py`, `app.py`, and `ui/`.
- Keep application path conventions stable. `XENIX_APP_HOME` is the local override for runtime directories.
- Prefer simple Python standard library solutions before adding new dependencies.
- Preserve `ml/` as-is unless the task explicitly requires migrating or deleting legacy model scripts.
