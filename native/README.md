# Xenix Native

Desktop workspace for the planned PySide6-based Xenix application.

This directory is intentionally isolated from the current web monorepo so the desktop bootstrap can land without destabilizing `packages/frontend` or `packages/backend`. When the long-lived `native` branch is cut, this subtree can be promoted to the branch root with minimal reshaping.

## Quick Start

```bash
cd native
pdm install
pdm run dev
```

Use Python `3.12` to `3.14`. The initial toolchain is intentionally pinned below `3.15` because current `PySide6` and `PyInstaller` releases do not resolve across a `>=3.15` target range.

## Commands

- `pdm run dev` starts the desktop shell.
- `pdm run test` runs the Python tests.
- `pdm run check` compiles the source tree to catch syntax errors.

## Directory Map

- `src/xenix` contains the application package, bootstrap code, UI, runtime config, logging, and exception handling.
- `tests` contains the first Python unit tests for config, logging, and resource resolution.
- `scripts` contains developer entry helpers used by `pdm run`.
- `ml` is reserved for future local training and inference modules.
- `docs` stores native-only runbooks and design notes.
- `xenix.spec` is the initial PyInstaller spec for desktop packaging work.

## Runtime Conventions

- App state defaults to `%LOCALAPPDATA%/Xenix` on Windows.
- Override the base directory with `XENIX_APP_HOME` during development or testing.
- Logs are written to `logs/xenix.log` under the resolved app home.

See [development runbook](docs/runbooks/development.md) for local workflow details and [repository governance](../docs/native-branch-governance.md) for the planned `master -> web` cutover.
