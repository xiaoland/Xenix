# Contributing

## Workflow

1. Follow the repository [`AGENTS.md`](AGENTS.md), the [working protocol](docs/00-meta/working-protocol.md) for non-trivial work, and the nearest local `AGENTS.md` for the files being changed.
2. Identify the canonical owner through the [documentation index](docs/README.md) before changing product, architecture, unit, or runtime truth.
3. Load [implementation taste](docs/00-meta/implementation-taste.md) only for non-trivial code changes that shape boundaries, data, authority, naming, abstraction, or complexity.
4. Keep changes explicit and local to the owning surface. Update durable docs when a verified contract, guarantee, operation, or recovery path changes.

## Development Commands

- `pdm install` installs project dependencies.
- `pdm run dev` runs the desktop application.
- `pdm run test` runs the test suite.
- `pdm run check` compiles the source tree to catch syntax errors.
- `pdm run i18n-extract` and `pdm run i18n-compile` update Qt translations.
- `pdm run package` builds the Windows bundle.
- `pdm run smoke-package` verifies the packaged executable.

Use the smallest verification set that proves the affected contract. Run `pdm run test` and `pdm run check` when the change has repository-wide or uncertain impact.

## Change-Specific Review

- UI changes follow the nearest UI guidance. Interaction or rendering-contract changes are reviewed against [Chatbot UI Unit TDD](docs/30-unit-tdd/chatbot-ui.md).
- Cross-service authority or topology changes are reviewed against
  [Product TDD](docs/20-product-tdd/README.md).
- Storage changes are reviewed against [Storage Ownership](docs/20-product-tdd/storage-ownership.md); migrations also follow [Local State Evolution](docs/40-deployment/local-state-evolution.md).
- Runtime or packaging changes follow the [Development Runbook](docs/40-deployment/development.md) and the relevant packaged smoke verification.
- New cross-unit ML states or result semantics update the
  [ML Task Lifecycle](docs/20-product-tdd/ml-task-lifecycle.md); runtime locations
  remain Deployment or source truth.

## Testing Intent

- Avoid adding a narrow regression test for every fixed bug. A past failure is evidence to inspect the durable contract, not by itself a reason to preserve a tiny test forever.
- Prefer high-signal tests that protect stable behavior: golden tests for deterministic payloads, projections, migrations, and artifact shapes; integrated tests for UI/service/storage/ML adapter boundaries; and E2E or smoke tests for critical user workflows.
- Add lower-level unit or boundary tests when they protect a stable contract, isolate high-risk logic, shorten feedback for expensive failures, or cover config resolution, logging, resource loading, ML task orchestration, storage boundaries, migrations, or data-loss risks.
- Do not add tests that only restate facts already guaranteed by source definitions, type contracts, enum membership, schema definitions, data models, or incidental implementation details.
