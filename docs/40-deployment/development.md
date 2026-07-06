# Development Runbook

## Install

```bash
pdm install
```

Use Python `3.12` to `3.14` for now.

Runtime dependencies now include:

- `pandas`
- `openpyxl`
- `polars` with `rtcompat` runtime support for older or constrained CPUs
- `fastexcel`
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
Xenix enables export per signal:

- traces are enabled by `OTEL_EXPORTER_OTLP_ENDPOINT` or
  `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, unless
  `XENIX_OTEL_EXPORT_TRACES=false`.
- metrics are enabled by `OTEL_EXPORTER_OTLP_ENDPOINT` or
  `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`, unless
  `XENIX_OTEL_EXPORT_METRICS=false`.
- logs are exported only when `XENIX_OTEL_EXPORT_LOGS=true` and either
  `OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` is set.

Endpoint, protocol, and headers can all be configured per signal with standard
OTel variables:

| Signal | Endpoint | Protocol | Headers |
| --- | --- | --- | --- |
| traces | `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` | `OTEL_EXPORTER_OTLP_TRACES_HEADERS` |
| metrics | `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` | `OTEL_EXPORTER_OTLP_METRICS_PROTOCOL` | `OTEL_EXPORTER_OTLP_METRICS_HEADERS` |
| logs | `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` | `OTEL_EXPORTER_OTLP_LOGS_PROTOCOL` | `OTEL_EXPORTER_OTLP_LOGS_HEADERS` |

When a signal-specific value is absent, the OTel exporter falls back to the
global `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_PROTOCOL`, and
`OTEL_EXPORTER_OTLP_HEADERS` variables. Prefer signal-specific headers when
different backends require different API keys. Do not add Xenix-specific API key
environment variables for telemetry backends.

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

For Arize Phoenix as a direct traces-only backend, set the trace endpoint only:

```bash
$env:OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://127.0.0.1:6006/v1/traces"
$env:OTEL_EXPORTER_OTLP_TRACES_PROTOCOL="http/protobuf"
# Only when Phoenix auth is enabled:
# $env:OTEL_EXPORTER_OTLP_TRACES_HEADERS="Authorization=Bearer <phoenix-api-key>"
pdm run dev
```

or, if using Phoenix's gRPC trace collector:

```bash
$env:OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://127.0.0.1:4317"
$env:OTEL_EXPORTER_OTLP_TRACES_PROTOCOL="grpc"
# Only when Phoenix auth is enabled:
# $env:OTEL_EXPORTER_OTLP_TRACES_HEADERS="Authorization=Bearer <phoenix-api-key>"
pdm run dev
```

Phoenix is an AI trace backend, not a full replacement for a logs/metrics
collector. Prefer routing through an OpenTelemetry Collector when traces,
metrics, and logs need different destinations.

Interactive startup does not force-flush OTLP exporters after the MainWindow is
shown. Startup spans are handed to the OpenTelemetry batch processors so a slow
or unreachable telemetry backend cannot block Qt input. Smoke and diagnostic
process-exit paths may still flush synchronously to make validation output
deterministic.

When sending different signals to different backends directly, keep all three
transport settings signal-specific:

```bash
$env:OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://127.0.0.1:6006/v1/traces"
$env:OTEL_EXPORTER_OTLP_TRACES_PROTOCOL="http/protobuf"
$env:OTEL_EXPORTER_OTLP_TRACES_HEADERS="Authorization=Bearer <phoenix-api-key>"

$env:OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="http://metrics.example.internal:4317"
$env:OTEL_EXPORTER_OTLP_METRICS_PROTOCOL="grpc"
$env:OTEL_EXPORTER_OTLP_METRICS_HEADERS="api-key=<metrics-key>"

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
- test-build startup locking is embedded from `XENIX_TRIAL_LOCK_DAYS`; unset, blank, or `0` disables it, while a positive integer locks startup after that many elapsed first-run days. Use a stable `XENIX_TRIAL_LOCK_STATE_SECRET` across rebuilds in the same test wave.
- DuckDB Python runtime imports successfully and can run an in-memory query inside the packaged app
- Native ML and data-science runtimes used by first-party workflows are present under `dist/xenix/_internal/` and are exercised by packaged verification, not only by startup import discovery.
- Polars packages both the compatible runtime and the default runtime. Keep `polars[calamine,rtcompat]` in project dependencies and keep `_polars_runtime_compat` explicitly collected in `xenix.spec`; Polars loads the compatible runtime first when it is available, which avoids startup failure on older CPUs that cannot satisfy the default runtime's AVX-oriented feature set.
- OpenTelemetry OTLP exporter hidden imports are collected by `xenix.spec` so
  packaged builds can use either gRPC or HTTP/protobuf OTLP export when the
  corresponding environment variables are set before launching the executable.

## Packaged Smoke Verification

```bash
pdm run smoke-package
```

Packaged smoke checks must cover runtime paths that load package-local native
libraries, compiled extensions, metadata, or data files. Startup-only smoke can
miss delayed ML imports: PyInstaller may include a package's Python modules in
`PYZ` while failing to collect the native files that the package loads later in
`COLLECT`. XGBoost, LightGBM, DuckDB, scikit-learn, SciPy, NumPy, pandas, Polars, and Fastexcel
are examples of dependency families that need this treatment when first-party
workflows depend on them.

Current smoke coverage intentionally exercises the strict Polars CSV and XLSX
read paths before higher-level dataset inspection or profiling code runs. This
keeps packaged builds from silently shipping with a missing, incompatible, or
mismatched `polars-runtime-*` binary while other features still appear healthy.

When adding or upgrading an ML/data-science dependency, add or keep a packaged
verification path that performs the smallest meaningful runtime exercise:
import the public API used by Xenix, construct the estimator or client, and for
model libraries prefer a tiny in-memory fit or prediction when it is cheap. If
that is too expensive for the default smoke, add a targeted packaged check and
document when release builds must run it.

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
- If an ML/data-science dependency fails only in the packaged app, inspect `build/xenix/COLLECT-00.toc` and `dist/xenix/_internal/` for package-local native files. Compare them with `PyInstaller.utils.hooks.collect_dynamic_libs("<package>")` and package metadata/data requirements. Do not assume that a successful Python-module import during analysis means the package's DLLs, `.pyd` files, BLAS/OpenMP runtimes, or package data were collected.
- If the packaged app fails at startup with `unknown feature flag: 'sse3'`, verify that `_polars_runtime_compat` is present under `dist/xenix/_internal/` and that the release environment was synced after the `polars[calamine,rtcompat]` dependency change. Do not use `POLARS_SKIP_CPU_CHECK` as the packaged fix; it can defer the failure into an illegal CPU instruction crash.
- If dataset inspection or `data.peek` reports `tabular_runtime_unavailable`, verify that `polars` and `polars-runtime-*` resolve to the same version in the active environment. Close running Xenix/Python processes that may keep old binaries loaded, then run `pdm sync -d --clean` and retry.
- If `analysis.graph` fails only in the PyInstaller windowed package, separate the renderer path first: Vega-Lite charts still go through `vl-convert-python`, while `wordcloud_spec` goes through `wordcloud` plus a real font file. Local minimal packaging tests showed that `vl_convert` SVG conversion can work in a console bundle but hang or fail with `oneshot canceled` in a windowed bundle that has no Windows console. Xenix allocates a temporary hidden console around the Vega-Lite converter call in frozen Windows builds, then releases it after rendering. Keep `smoke-package` covering both Vega-Lite rendering and dedicated word-cloud rendering so this boundary does not regress.
- If an SSH worker setup fails, inspect `config/ml_workers.json`, the Xenix-managed `Host xenix.*` block in `~/.ssh/config`, and the remote root permissions. Do not add passwords, passphrases, or private-key material to Xenix config.
- If you need an isolated local run, set `XENIX_APP_HOME` to an empty directory or use the VSCode workspace-home launch profile.
