# Development Runbook

## Install

```bash
cd native
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

## App Directories

- `XENIX_APP_HOME` overrides the base application directory.
- Windows default: `%LOCALAPPDATA%/Xenix`
- macOS default: `~/Library/Application Support/Xenix`
- Linux default: `~/.local/share/Xenix`

Runtime directories created on startup:

- `config/`
- `logs/`
- `cache/`
