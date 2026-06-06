# Runtime Telemetry Implementation Slices

## Purpose

Break the agreed observability strategy into implementation slices without
starting implementation.

These slices follow the current decisions:

- OTel owns traces, metrics, propagation, SDK/export configuration, semantic
  conventions, and backend neutrality.
- `structlog + logging` owns the structured logging/event developer interface.
- JSON logs, diagnostic bundles, and OTLP are sinks/exports.
- Existing domain models and lifecycle transitions are the primary observability
  source.
- No telemetry-specific persistence entity is introduced in v1.
- UI interaction telemetry is out of scope.

## Slice 0: Dependency And Bootstrap Baseline

### Objective

Introduce mature observability libraries and central runtime bootstrap without
instrumenting business workflows yet.

### Likely Scope

- Add OTel API/SDK packages required for traces, metrics, propagation, and
  logging correlation.
- Add `structlog` or confirm stdlib-only structured logging is sufficient.
- Add a tiny bootstrap integration near existing logging/runtime setup.
- Add persistent anonymous install id generation/storage if product/privacy
  handshake confirms it.
- Add app/build/package resource attributes.
- Preserve no-op behavior when telemetry is disabled.

### Existing Models Reused

- `AppPaths`
- runtime config files under `config/`
- existing logging setup entrypoint

### Explicit Non-Scope

- No domain spans.
- No remote backend decision hard-coded.
- No telemetry table.
- No UI settings panel unless later required.

### Verification

- Existing startup/smoke tests still pass with telemetry disabled.
- Tests prove bootstrap is idempotent enough for test/runtime usage.
- Tests prove install id is random-generated and persisted without machine
  fingerprinting.
- Logging still writes locally.

## Slice 1: Structured Local Logs As First Export

### Objective

Make local logs parseable and trace-correlatable while keeping them as an export
path, not the source of truth.

### Likely Scope

- Migrate `logs/xenix.log` to JSON Lines.
- Configure `structlog + logging` or stdlib JSON logging.
- Add OTel logging correlation for trace id/span id/service context.
- Preserve existing log rotation behavior.
- Ensure logs tolerate telemetry disabled/no active span.

### Existing Models Reused

- Existing logger names and logging call sites.
- Existing runtime `logs/` directory.

### Explicit Non-Scope

- No broad rewrite of every logging call.
- No log-based workflow state model.
- No raw user data/path/prompt/model response in structured fields.

### Verification

- Existing logging tests updated for JSON Lines.
- Test JSON log parseability.
- Test correlation fields are present when inside an active span and harmless
  when absent.

## Slice 2: Startup, Storage, And Runtime Resource Instrumentation

### Objective

Cover the earliest public-beta failure points: startup, runtime paths, settings,
storage bootstrap, and schema migration.

### Likely Scope

- Instrument startup/bootstrap span boundaries.
- Instrument storage bootstrap/migration boundary.
- Emit aggregate startup/storage success/failure metrics.
- Record structured logs for startup/storage lifecycle transitions.

### Existing Models Reused

- `AppPaths`
- storage bootstrap service
- SQLite `user_version`
- existing migration flow

### Explicit Non-Scope

- No new startup state table.
- No raw absolute paths in exported attributes.
- No SQL row payload logging.

### Verification

- Startup/smoke tests pass.
- Storage bootstrap tests pass.
- Tests cover successful and failed bootstrap instrumentation through in-memory
  or fake OTel exporters where practical.

## Slice 3: Agent Harness Boundary Instrumentation

### Objective

Make Agent/LLM public-beta failures diagnosable through existing Agent Harness
records and lifecycle transitions.

### Likely Scope

- Instrument Agent turn lifecycle.
- Instrument provider request lifecycle and duration.
- Instrument tool call lifecycle and duration.
- Instrument step-budget and cancellation boundaries.
- Correlate logs with active turn/provider/tool spans.

### Existing Models Reused

- `AgentTurnRow`
- `AgentRunRow`
- `AgentProviderRequestRow`
- `AgentToolCallRow`
- `AgentTurnCompletionGuardRow`
- existing Agent status enums and lifecycle methods

### Explicit Non-Scope

- No prompt, message content, raw model output, tool args, or tool result body in
  telemetry attributes/log fields.
- No new Agent telemetry rows.
- No UI interaction events.

### Verification

- Agent Harness targeted tests pass.
- Tests prove provider/tool failure paths emit expected status without sensitive
  payloads.
- Tests cover cancellation/step-budget correlation where feasible.

## Slice 4: ML Task, Worker, And Artifact Instrumentation

### Objective

Make model execution and artifact finalization failures diagnosable across local
and SSH worker paths.

### Likely Scope

- Instrument ML task enqueue/start/complete/fail/cancel/finalize boundaries.
- Instrument worker dispatch and remote staging boundaries.
- Propagate OTel context through local subprocess/worker boundaries using
  standard carriers where practical.
- Instrument artifact registration/finalization.
- Correlate ML task logs with parent spans where feasible.

### Existing Models Reused

- `MLTaskRow`
- `MLTaskStatus`
- `MLTaskType`
- `MLTaskArtifactRow`
- `ArtifactRow`
- existing worker pool/runner flow
- existing task `request.json`, `result.json`, `logs.jsonl`

### Explicit Non-Scope

- No telemetry table.
- No raw dataset paths, column names, cell values, SSH host/user/path, key path,
  command line with secrets, model artifact path, or raw traceback in exported
  attributes.
- No automatic retry/failover semantics change.

### Verification

- ML task tests pass.
- Worker tests pass.
- Tests prove local and SSH dispatch failures are observable without exposing
  connection details.
- Tests prove artifact finalization failure is observable.

## Slice 5: Selected Data And Analysis Operation Instrumentation

### Objective

Cover P1 data/analysis operation failures only where they directly support beta
diagnosis.

### Likely Scope

- Instrument durable service boundaries for dataset registration, query,
  transform, profile, graph, and clean operations if they are already part of the
  accepted beta path.
- Use broad buckets for workload shape only if allowed.

### Existing Models Reused

- dataset registration rows
- artifact metadata
- existing service request/result objects
- existing validation errors

### Explicit Non-Scope

- No dataset values.
- No column names by default.
- No SQL text.
- No graph spec body or generated image content.
- No product analytics of UI behavior.

### Verification

- Data/analysis targeted tests pass.
- Sensitive-field tests cover SQL text, paths, column names, and payload values.

## Slice 6: Transport Configuration And Diagnostic Bundle

### Objective

Make telemetry useful outside the running process through replaceable exports.

### Likely Scope

- Configure OTLP export through standard OTel environment/config path.
- Keep backend/vendor-specific configuration out of domain code.
- Add or refine local diagnostic bundle generation if needed for public beta
  support.
- Include JSON logs, relevant SQLite metadata summaries, build/install metadata,
  and task logs according to privacy rules.

### Existing Models Reused

- runtime logs
- task logs
- existing SQLite rows
- app config/build metadata

### Explicit Non-Scope

- No vendor SDK.
- No backend-specific dashboard assumptions in app code.
- No uploading without explicit product/consent decision.

### Verification

- Local bundle can be generated and inspected.
- OTLP export can be validated against a local Collector or in-memory/fake
  exporter.
- Telemetry endpoint failures do not block app workflows.

## Slice 7: Documentation, Review, And Regression Guards

### Objective

Promote stable decisions into durable docs and prevent telemetry regressions.

### Likely Scope

- Update runtime/deployment docs with observability configuration and local log
  format.
- Update product TDD or unit TDD only for stable boundary claims.
- Add tests or lint-like checks for forbidden telemetry fields where practical.
- Document support workflow for reading logs/traces/bundles.

### Existing Models Reused

- docs route ownership
- tests around storage, logging, startup, Agent, ML workers

### Explicit Non-Scope

- No broad docs rewrite.
- No product analytics policy expansion beyond current scope.

### Verification

- Full targeted test set passes.
- `pdm run check` passes.
- Packaged smoke considered if dependency/package changes affect PyInstaller.

## Suggested Execution Order

1. Slice 0: Dependency and bootstrap baseline.
2. Slice 1: Structured local logs.
3. Slice 2: Startup/storage/resource.
4. Slice 3: Agent/provider/tool.
5. Slice 4: ML/worker/artifact.
6. Slice 5: selected data/analysis P1.
7. Slice 6: transport/bundle.
8. Slice 7: docs and guards.

## Handshake Before Implementation

Before code implementation starts, restate:

- Which slices are in the first implementation batch.
- Which existing models and lifecycle transitions are touched.
- Whether persistent anonymous install id is approved.
- Whether `structlog` is selected or stdlib JSON logging is enough.
- Whether OTLP remote export is included in the first batch or deferred.
- Which verification commands bound side effects.

Status on 2026-06-06:

- First implementation batch includes all slices.
- Persistent anonymous install id is approved.
- `structlog` is selected.
- OTLP remote export is included in the first batch.

## Implementation Result

Implemented on 2026-06-06.

### Delivered

- Added OpenTelemetry API/SDK/exporter/logging-instrumentation and `structlog`
  dependencies.
- Added `src/xenix/observability.py` for install id, OTel bootstrap, resource
  attributes, OTLP exporter selection, log correlation, and tiny helper
  functions.
- Migrated local `logs/xenix.log` to JSON Lines through `structlog + logging`.
- Added persistent anonymous install id in `config/telemetry.json`.
- Added startup/storage instrumentation.
- Added Agent Harness turn/provider/tool instrumentation based on existing
  Agent lifecycle models.
- Added ML task/worker/artifact instrumentation based on existing task,
  worker, and artifact lifecycle models.
- Added selected data/analysis service boundary instrumentation.
- Added `scripts/create_diagnostic_bundle.py` and `pdm run diagnostic-bundle`.
- Added PyInstaller hidden imports for OTLP gRPC and HTTP/protobuf exporters.
- Updated runtime/development docs for JSON logs, OTLP env configuration, and
  diagnostic bundles.

### Preserved

- No telemetry-specific SQLite table.
- No UI interaction telemetry.
- No prompt/message/tool body/model response/dataset values/SQL text/chart spec
  in telemetry attributes.
- Trace context is propagated to background ML task dispatch in memory, not by
  adding trace fields to persisted task request payloads.

### Verification

- Command: `pdm run pytest tests/test_logging.py tests/test_observability.py tests/test_main.py::test_smoke_test_bootstraps_runtime_in_fresh_app_home -q`
  - Observed: `5 passed`.
- Command: `pdm run pytest tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py -q`
  - Observed: `29 passed`.
- Command: `pdm run pytest tests/test_services.py tests/test_ml_execution.py tests/test_ml_workers.py tests/test_agent_harness_foundation.py -q`
  - Observed: `30 passed`.
- Command: `pdm run pytest tests/test_data_cleaning.py tests/test_data_transform.py tests/test_analysis_profile.py tests/test_analysis_graph.py -q`
  - Observed: `31 passed`.
- Command: `pdm run pytest tests/test_diagnostic_bundle.py tests/test_logging.py tests/test_observability.py -q`
  - Observed: `5 passed`.
- Command: `pdm run pytest tests/test_main.py::test_smoke_test_bootstraps_runtime_in_fresh_app_home tests/test_storage_bootstrap.py tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py tests/test_services.py tests/test_ml_execution.py tests/test_ml_workers.py tests/test_data_cleaning.py tests/test_data_transform.py tests/test_analysis_profile.py tests/test_analysis_graph.py tests/test_diagnostic_bundle.py tests/test_logging.py tests/test_observability.py -q`
  - Observed: `102 passed`.
- Command: `pdm run check`
  - Observed: passed.
- Command: `pdm run pytest -q`
  - Observed: `201 passed`.
- Command: `pdm run smoke`
  - Observed: passed; startup JSON logs include active OTel trace/span context.
- Command: `pdm run diagnostic-bundle -- --output .tmp/xenix-diagnostic-test.zip`
  - Observed: zip generated successfully.

### Not Run

- Full PyInstaller package build/smoke was not run in this implementation pass.
  `xenix.spec` was updated with OTLP exporter hidden imports for packaged
  collection.
