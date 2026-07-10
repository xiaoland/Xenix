# Xenix Native

PySide6 desktop application for the Xenix Native product line.

Repository routing and knowledge ownership start in [AGENTS.md](AGENTS.md).

## Quick Start

```bash
pdm install
pdm run dev
```

The authoritative Python and dependency constraints are declared in [pyproject.toml](pyproject.toml).

## Commands

- `pdm run dev` starts the desktop shell.
- `pdm run smoke` initializes the app with a fresh startup path and exits after bootstrap validation.
- `pdm run package` builds the Windows `onedir` PyInstaller bundle from `xenix.spec`.
- `pdm run smoke-package` launches the packaged executable with `--smoke-test` and verifies runtime artifacts in a temporary app home.
- `pdm run test` runs the Python tests.
- `pdm run check` compiles the source tree to catch syntax errors.

## Layout

- `src/xenix` contains the application package, bootstrap code, UI, runtime config, storage services, logging, and exception handling.
- `tests` contains unit tests for config, storage bootstrap, repositories, services, logging, and resource resolution.
- `scripts` contains developer helpers used by `pdm run`.
- `ml` contains legacy model scripts; native ML implementation lives under `src/xenix/services/ml`.
- `docs` stores canonical durable documentation layers.
- `tasks` stores disposable agent workspaces whose latest recursive modification is within the previous seven days.
- `xenix.spec` is the canonical Windows PyInstaller `onedir` spec.

## Documentation Model

- Implementation taste: [docs/00-meta/implementation-taste.md](docs/00-meta/implementation-taste.md)
- PRD: [docs/10-prd/README.md](docs/10-prd/README.md)
- Product TDD: [docs/20-product-tdd/README.md](docs/20-product-tdd/README.md)
- Unit TDD: [docs/30-unit-tdd/README.md](docs/30-unit-tdd/README.md)
- Deployment: [docs/40-deployment/README.md](docs/40-deployment/README.md)
- Contributor workflow: [CONTRIBUTING.md](CONTRIBUTING.md)

For development, packaging, and verification, see the [Development Runbook](docs/40-deployment/development.md). For resolved application paths, persisted state, and recovery, see the [Runtime State Runbook](docs/40-deployment/runtime-state.md).
