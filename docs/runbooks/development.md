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

Expected result: the app opens the native dataset import workspace with project/work-item selection, file-picker and drag-and-drop import, dataset summary, and column selection.

Issue `#72` extends that shell with a dedicated training tab for:

- manual fit with schema-driven parameter editing
- multi-model tuning with schema-driven grid editing
- background task status, logs, and failure summary
- trained-model listing and best-model marker

## Verify

```bash
pdm run test
pdm run check
```

## VS Code

- Launch `Xenix Native: Debug App` to start the desktop shell under the debugger.
- Launch `Xenix Native: Debug App (Workspace Home)` to keep runtime data inside `${workspaceFolder}/.runtime`.
- Run the `PyInstaller: package` task to build the desktop bundle from `xenix.spec`.

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
