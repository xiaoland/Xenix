# Contributing

## Workflow

1. Start from the issue scope and confirm whether the change is bootstrap, UI, service, persistence, or ML work.
2. Read the relevant contract and ADR documents before changing code:
   - `docs/contracts/`
   - `docs/adr/`
   - `docs/runbooks/`
   - `docs/migrations/`
3. Keep the native shell code-first and Qt Widgets based. Do not introduce QML unless the issue explicitly asks for it.
4. Prefer small, explicit changes in `src/xenix/main.py`, `src/xenix/app.py`, and `src/xenix/ui/`.
5. Update docs when the change affects architecture boundaries, guarantees, operations, or local-state evolution.

## Development Checklist

- Install dependencies with `pdm install`.
- Run the app with `pdm run dev` when the change affects the desktop flow.
- Run `pdm run test`.
- Run `pdm run check`.
- If runtime paths or packaging behavior changed, review `docs/runbooks/development.md`.

## Review Checklist

- UI code does not call ML scripts directly.
- UI code talks to services through stable request/result objects or methods documented in `docs/contracts/runtime-boundaries.md`.
- SQLite is only used for metadata and task bookkeeping; datasets, models, exports, and logs remain on the filesystem unless an ADR says otherwise.
- Single-user local mode assumptions still hold. Do not reintroduce multi-user, remote deployment, or web-only concepts without an ADR.
- New task states, result formats, or storage locations are documented before merge.

## Testing Intent

- Add or update unit tests when changing config resolution, logging, resource loading, task orchestration, or storage boundaries.
- Add contract tests for any boundary that crosses UI, services, ML adapters, SQLite, or the filesystem.
- Prefer executable checks over prose when a guarantee can be enforced in tests or CI.
