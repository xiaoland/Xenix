# Xenix Native

PySide6 desktop application for the Xenix Native product line.

Repository routing and knowledge ownership start in [AGENTS.md](AGENTS.md). Framework guidance (working methods, task packets, verification, and taste) is browsed with `svc lookup`.

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
- `docs` stores durable project knowledge.
- `tasks` stores active task packets; retention is owned by [AGENTS.md](AGENTS.md).
- `xenix.spec` is the canonical Windows PyInstaller `onedir` spec.

## Documentation Model

- PRD: [docs/10-prd/README.md](docs/10-prd/README.md)
- Product TDD: [docs/20-prd-tdd/README.md](docs/20-prd-tdd/README.md)
- Unit TDD: [docs/30-unit-tdd/README.md](docs/30-unit-tdd/README.md)
- Deployment: [docs/40-deployment/README.md](docs/40-deployment/README.md)
- Contributor workflow: [CONTRIBUTING.md](CONTRIBUTING.md)
- SVC corpus baseline: [svc.json](svc.json)

For packaged delivery, see [Packaging](docs/40-deployment/packaging.md). For resolved application paths, persisted state, and recovery, see [Runtime State](docs/40-deployment/runtime-state.md).
