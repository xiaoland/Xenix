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
- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp`
- `opentelemetry-instrumentation-logging`
- `structlog`

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

LLM provider settings are stored through the Settings dialog in `config/agent_settings.json`. The file stores configured providers, each provider's model list, the global default model, and optional guard/title model selections. Chatbot model switching is per thread and changes only that thread's next turn. `XENIX_ENV=development` exposes development-only mock controls in Settings. AIMock uses the same OpenAI-compatible provider HTTP boundary as the live provider.

ML worker pool settings are stored through Settings in `config/ml_workers.json`. The default configuration uses the local worker. SSH workers require OpenSSH-family `ssh` and `scp` commands, key/agent-based authentication, a POSIX-like remote target, Python 3.12+, and a writable remote root. The SSH setup wizard can write clearly marked `Host xenix.*` blocks to the user's OpenSSH config, create a remote virtual environment, install required ML dependencies, and run upload/download and worker smoke checks.

## Verify

```bash
pdm run test
pdm run check
pdm run smoke
```

`pdm run smoke` uses the same native entrypoint as the real app, but exits after validating startup, storage bootstrap, logging, and window creation.

## Observability

Xenix uses OpenTelemetry for traces, metrics, propagation, SDK/export
configuration, and backend neutrality. Structured local logs use
`structlog + logging` and are written as JSON Lines to `logs/xenix.log`.

Persistent anonymous install identity is stored in `config/telemetry.json`.
The value is randomly generated and is not derived from machine information.

OTLP export is configured with standard OpenTelemetry environment variables.
For a local Collector during development, set for example:

```bash
$env:OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4317"
$env:OTEL_EXPORTER_OTLP_PROTOCOL="grpc"
pdm run dev
```

For HTTP/protobuf collectors:

```bash
$env:OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318"
$env:OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
pdm run dev
```

Remote log export is supported but off by default because application logs may
contain local diagnostic detail. Enable it explicitly with:

```bash
$env:XENIX_OTEL_EXPORT_LOGS="true"
```

Create a local support bundle with:

```bash
pdm run diagnostic-bundle
```

The bundle includes JSON logs, ML task logs, telemetry metadata, and SQLite
schema/table-count summaries. It does not include the raw `state/xenix.db`
database file.

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
- OpenTelemetry OTLP exporter hidden imports are collected by `xenix.spec` so
  packaged builds can use either gRPC or HTTP/protobuf OTLP export when the
  corresponding environment variables are set before launching the executable.

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
- `config/ml_workers.json` can be created by Settings or worker settings service when ML worker configuration is saved

## Troubleshooting

- If packaging succeeds but the EXE does not start, rerun `pdm run smoke-package` first. It validates the packaged startup path without requiring manual UI interaction.
- If resources fail to load in the packaged app, verify that `xenix.spec` still copies `src/xenix/resources` into `xenix/resources`.
- If language switching fails in a packaged app, verify that `src/xenix/translations/*.qm` were rebuilt and copied into `xenix/translations`.
- If DuckDB-backed tools fail only in the packaged app, rerun `pdm run smoke-package` and inspect whether PyInstaller collected DuckDB's package metadata and native library.
- If `analysis.graph` fails only in the PyInstaller windowed package, check the `vl-convert-python` render path. Local minimal packaging tests showed that `vl_convert.vegalite_to_svg` works in a console bundle but can hang or fail with `oneshot canceled` in a windowed bundle that has no Windows console. Xenix allocates a temporary hidden console around the converter call in frozen Windows builds, then releases it after rendering. Keep `smoke-package` covering graph rendering so this workaround does not regress.
- If an SSH worker setup fails, inspect `config/ml_workers.json`, the Xenix-managed `Host xenix.*` block in `~/.ssh/config`, and the remote root permissions. Do not add passwords, passphrases, or private-key material to Xenix config.
- If you need an isolated local run, set `XENIX_APP_HOME` to an empty directory or use the VSCode workspace-home launch profile.
