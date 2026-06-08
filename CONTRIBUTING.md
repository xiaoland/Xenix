# Contributing

## Workflow

1. Start from the issue scope and confirm whether the change is bootstrap, UI, service, persistence, or ML work.
2. For ambiguous, non-trivial, diagnosis-first, or reference-sensitive work, start in an agent-owned task packet under `tasks/` and keep the compact current state, evidence, and verification there until requirements become stable.
3. Read the relevant durable docs before changing code:
   - `docs/10-prd/`
   - `docs/20-product-tdd/`
   - `docs/40-deployment/`
   - `docs/20-product-tdd/adr/`
4. Use the pre-execution restatement format in `AGENTS.md` for reference-sensitive or logic-altering changes.
5. For non-trivial code design or implementation changes, load `docs/00-meta/implementation-taste.md` and keep authority, data shape, naming, and complexity tradeoffs explicit.
6. Keep the native shell code-first and Qt Widgets based. Do not introduce QML unless the issue explicitly asks for it.
7. Prefer small, explicit changes in `src/xenix/main.py`, `src/xenix/app.py`, and `src/xenix/ui/`.
8. Update docs when the change affects architecture boundaries, guarantees, operations, or local-state evolution.

## Development Checklist

- Install dependencies with `pdm install`.
- Run the app with `pdm run dev` when the change affects the desktop flow.
- Run `pdm run test`.
- Run `pdm run check`.
- For ordinary source or durable-doc searches, exclude task workspaces, generated output, dependencies, virtual environments, and caches unless the task explicitly targets them.
- If runtime paths or packaging behavior changed, review `docs/40-deployment/development.md`.

## Review Checklist

- UI code does not call ML scripts directly.
- UI code talks to services through stable request/result objects or methods documented in `docs/20-product-tdd/runtime-boundaries.md`.
- SQLite is only used for metadata and ML task bookkeeping; datasets, models, exports, and logs remain on the filesystem unless an ADR says otherwise.
- Single-user local mode assumptions still hold. Do not reintroduce multi-user, remote deployment, or web-only concepts without an ADR.
- New ML task states, result formats, or storage locations are documented before merge.

## Testing Intent

- Avoid adding a narrow regression test for every fixed bug. A past failure is evidence to inspect the durable contract, not by itself a reason to preserve a tiny test forever.
- Prefer high-signal tests that protect stable behavior: golden tests for deterministic payloads, projections, migrations, and artifact shapes; integrated tests for UI/service/storage/ML adapter boundaries; and E2E or smoke tests for critical user workflows.
- Add lower-level unit or boundary tests only when they protect a stable contract, isolate high-risk logic, shorten feedback for expensive failures, or cover config resolution, logging, resource loading, ML task orchestration, storage boundaries, migrations, or data-loss risks.
- Do not add tests that only restate facts already guaranteed by source definitions, type contracts, enum membership, schema definitions, data models, or incidental implementation details.
