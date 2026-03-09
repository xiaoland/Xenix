# Development Runbook

## Install

```bash
pdm install
```

Use Python `3.12` to `3.14` for now.

## Run

```bash
pdm run dev
```

Expected result: a minimal `Xenix Native` window opens and shows the resolved app directories plus the current log file location.

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
