# Development Runbook

## Install

```bash
pdm install
```

Use Python `3.12` to `3.14` for now.

Runtime dependencies now include:

- `pandas`
- `openpyxl`
- `pydantic`
- `joblib`
- `scikit-learn`

## Run

```bash
pdm run dev
```

Expected result: the app opens the native desktop shell on a scenario-first home surface with guided templates, `History`, and `Settings`.

The delivered workflow includes:

- scenario data import by file picker or drag-and-drop
- guided checkbox-group selection of one prediction target and one or more input columns
- application-managed scenario work-item preparation
- fixed template-driven background training with logs and best-model tracking
- manual and batch-file prediction against the best trained model
- prediction history browsing with reopen and export
- technical dataset, training, and inference workspaces still available in code for direct control

## Verify

```bash
pdm run test
pdm run check
pdm run smoke
```

`pdm run smoke` uses the same native entrypoint as the real app, but exits after validating startup, storage bootstrap, logging, and window creation.

## Translations

```bash
pdm run i18n-extract
pdm run i18n-compile
```

- `pdm run i18n-extract` refreshes the Qt Linguist `.ts` catalogs from the current Python widget source.
- `pdm run i18n-compile` compiles `.ts` catalogs into `.qm` files used by `QTranslator` at runtime.

## Package

```bash
pdm run package
```

Expected result:

- Windows `onedir` bundle is created under `dist/xenix/`
- packaged executable path is `dist/xenix/xenix.exe`
- package resources are available under the bundled `xenix/resources/` path
- compiled translations are available under the bundled `xenix/translations/` path

## Packaged Smoke Verification

```bash
pdm run smoke-package
```

## VS Code

- Launch `Xenix Native: Debug App` to start the desktop shell under the debugger.
- Launch `Xenix Native: Debug App (Workspace Home)` to keep runtime data inside `${workspaceFolder}/.runtime`.
- Launch `Xenix Native: Debug Smoke Test` to validate startup without entering the full event loop.
- Run the `PyInstaller: package` task to build the desktop bundle from `xenix.spec`.
- Run the `PyInstaller: packaged smoke test` task to launch the packaged EXE with `--smoke-test` against a temporary runtime home.

## App Directories

- `XENIX_APP_HOME` overrides the base application directory.
- Windows default: `%LOCALAPPDATA%/Xenix`
- macOS default: `~/Library/Application Support/Xenix`
- Linux default: `~/.local/share/Xenix`

Runtime directories created on startup:

- `config/`
- `logs/`
- `cache/`
- `state/`
- `temp/`
- `artifacts/`

Smoke verification should confirm that these directories are created in a fresh runtime home and that:

- `state/xenix.db` is created
- `logs/xenix.log` is created

## Troubleshooting

- If packaging succeeds but the EXE does not start, rerun `pdm run smoke-package` first. It validates the packaged startup path without requiring manual UI interaction.
- If resources fail to load in the packaged app, verify that `xenix.spec` still copies `src/xenix/resources` into `xenix/resources`.
- If language switching fails in a packaged app, verify that `src/xenix/translations/*.qm` were rebuilt and copied into `xenix/translations`.
- If you need an isolated local run, set `XENIX_APP_HOME` to an empty directory or use the VSCode workspace-home launch profile.
