# Xenix Native

PySide6 desktop application for the Xenix Native product line.

Repository routing and knowledge ownership start in [AGENTS.md](AGENTS.md). Non-trivial work follows the [working protocol](docs/00-meta/working-protocol.md).

## Quick Start

```bash
pdm install
pdm run dev
```

The authoritative Python and dependency constraints are declared in [pyproject.toml](pyproject.toml).

Contributor, test, translation, and packaging commands are owned by [CONTRIBUTING.md](CONTRIBUTING.md).

## Layout

- `src/xenix` contains the application package, bootstrap code, UI, runtime config, storage services, logging, and exception handling.
- `tests` contains unit tests for config, storage bootstrap, repositories, services, logging, and resource resolution.
- `scripts` contains developer helpers used by `pdm run`.
- `ml` contains legacy model scripts; native ML implementation lives under `src/xenix/services/ml`.
- `docs` stores canonical durable documentation layers.
- `tasks` stores active disposable agent workspaces; retention is owned by [AGENTS.md](AGENTS.md).
- `xenix.spec` is the canonical Windows PyInstaller `onedir` spec.

## Documentation Model

- Working protocol: [docs/00-meta/working-protocol.md](docs/00-meta/working-protocol.md)
- Implementation taste: [docs/00-meta/implementation-taste.md](docs/00-meta/implementation-taste.md)
- PRD: [docs/10-prd/README.md](docs/10-prd/README.md)
- Product TDD: [docs/20-product-tdd/README.md](docs/20-product-tdd/README.md)
- Unit TDD: [docs/30-unit-tdd/README.md](docs/30-unit-tdd/README.md)
- Deployment: [docs/40-deployment/README.md](docs/40-deployment/README.md)
- Contributor workflow: [CONTRIBUTING.md](CONTRIBUTING.md)

For packaged delivery, see [Packaging](docs/40-deployment/packaging.md). For resolved application paths, persisted state, and recovery, see [Runtime State](docs/40-deployment/runtime-state.md).
