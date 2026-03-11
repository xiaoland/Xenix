# Xenix Native

PySide6 desktop bootstrap for the `native` branch of Xenix.

This branch is intentionally focused on the Native desktop application line. The web monorepo remains on `web` (previous `master`, read [docs/runbooks/branch-governance.md](docs/runbooks/branch-governance.md) for more information)

## Quick Start

```bash
pdm install
pdm run dev
```

Use Python `3.12` to `3.14`. The initial toolchain is pinned below `3.15` because the current `PySide6` and `PyInstaller` releases do not resolve against a `>=3.15` target range.

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
- `ml` keeps the existing Python model scripts that will be integrated into the native workflow later.
- `docs` stores contracts, ADRs, runbooks, and migration guidance for the native app.
- `xenix.spec` is the canonical Windows PyInstaller `onedir` spec.

## Documentation Model

- Contracts: [docs/contracts/README.md](docs/contracts/README.md)
- ADRs: [docs/adr/README.md](docs/adr/README.md)
- Runbooks: [docs/runbooks/README.md](docs/runbooks/README.md)
- Migrations: [docs/migrations/README.md](docs/migrations/README.md)
- Contributor workflow: [CONTRIBUTING.md](CONTRIBUTING.md)

## Runtime Conventions

- App state defaults to `%LOCALAPPDATA%/Xenix` on Windows.
- Override the base directory with `XENIX_APP_HOME` during development or testing.
- Logs are written to `logs/xenix.log` under the resolved app home.
- SQLite metadata is stored in `state/xenix.db`.
- Temporary dataset copies live under `temp/datasets/`.
- App-managed artifacts and ML task working directories live under `artifacts/`.

## Packaging

- The packaged executable is built at `dist/xenix/xenix.exe`.
- Startup smoke validation is available in both source and packaged forms through the shared `--smoke-test` CLI.
- VSCode launch/task entries are provided for debugger startup, smoke startup, packaging, and packaged smoke verification.

See [docs/runbooks/development.md](docs/runbooks/development.md) for local workflow details.
