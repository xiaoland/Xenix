# Contributing

## Workflow

1. Start from the issue scope and confirm whether the change is bootstrap, UI, service, persistence, or ML work.
2. For ambiguous or reference-sensitive work, start in a named task packet under `tasks/` and keep exploration there until requirements become stable.
3. Read the relevant durable docs before changing code:
   - `docs/10-prd/`
   - `docs/20-product-tdd/`
   - `docs/40-deployment/`
   - `docs/20-product-tdd/adr/`
4. Use the pre-execution restatement format in `AGENTS.md` for reference-sensitive or logic-altering changes.
5. Keep the native shell code-first and Qt Widgets based. Do not introduce QML unless the issue explicitly asks for it.
6. Prefer small, explicit changes in `src/xenix/main.py`, `src/xenix/app.py`, and `src/xenix/ui/`.
7. Update docs when the change affects architecture boundaries, guarantees, operations, or local-state evolution.

## Development Checklist

- Install dependencies with `pdm install`.
- Run the app with `pdm run dev` when the change affects the desktop flow.
- Run `pdm run test`.
- Run `pdm run check`.
- If runtime paths or packaging behavior changed, review `docs/40-deployment/development.md`.

## Review Checklist

- UI code does not call ML scripts directly.
- UI code talks to services through stable request/result objects or methods documented in `docs/20-product-tdd/runtime-boundaries.md`.
- SQLite is only used for metadata and ML task bookkeeping; datasets, models, exports, and logs remain on the filesystem unless an ADR says otherwise.
- Single-user local mode assumptions still hold. Do not reintroduce multi-user, remote deployment, or web-only concepts without an ADR.
- New ML task states, result formats, or storage locations are documented before merge.

## Testing Intent

- Add or update unit tests when changing config resolution, logging, resource loading, ML task orchestration, or storage boundaries.
- Add contract tests for any boundary that crosses UI, services, ML adapters, SQLite, or the filesystem.
- Prefer executable checks over prose when a guarantee can be enforced in tests or CI.
