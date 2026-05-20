# Development Runbook

## Install

```bash
pdm install
```

Use Python `3.12` to `3.14` for now.

Runtime dependencies now include:

- `pandas`
- `openpyxl`
- `duckdb`
- `pydantic`
- `joblib`
- `scikit-learn`

## Run

```bash
pdm run dev
```

Expected result: the app opens the native desktop shell on the Chatbot-first surface.

The delivered workflow includes:

- conversation plus file drag-and-drop
- Agent Harness tool calls for data inspection, integration, cleaning, read-only querying, transformation, role binding, training, hyperparameter training, and model apply
- markdown summaries with `artifact://...` links
- Chatbot previews for generated datasets, reports, metrics, models, images, and apply result files
- local persistence for conversations, messages, tool calls, tool results, artifacts, ML task metadata, and logs

LLM provider settings are stored through the Settings dialog in `config/agent_settings.json`. `XENIX_ENV=development` exposes development-only mock controls in Settings. AIMock uses the same OpenAI-compatible provider HTTP boundary as the live provider.

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
- In Codex App, use the `Compile .qm` project action to run the same compile step from the action bar.

## Package

```bash
pdm run package
```

Expected result:

- Windows `onedir` bundle is created under `dist/xenix/`
- packaged executable path is `dist/xenix/xenix.exe`
- package resources are available under the bundled `xenix/resources/` path
- compiled translations are available under the bundled `xenix/translations/` path
- build commit is embedded into the bundle and shown in Settings; `XENIX_BUILD_COMMIT` can override git discovery for non-checkout build environments
- DuckDB Python runtime imports successfully and can run an in-memory query inside the packaged app

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
- If DuckDB-backed tools fail only in the packaged app, rerun `pdm run smoke-package` and inspect whether PyInstaller collected DuckDB's package metadata and native library.
- If you need an isolated local run, set `XENIX_APP_HOME` to an empty directory or use the VSCode workspace-home launch profile.
