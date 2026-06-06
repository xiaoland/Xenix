# Public Beta Runtime Telemetry Exploration

## Objective & Hypothesis

- Objective: define the smallest vendor-neutral telemetry capability that helps
  diagnose internal program behavior during a small public beta.
- Hypothesis: a lightweight OpenTelemetry-based runtime instrumentation layer,
  default-off or consent-gated for remote export, can give useful traces,
  counters, durations, and correlated logs without committing Xenix to a vendor
  backend or collecting UI interaction events.

## Prompt

- The product is approaching a small public beta.
- The immediate need is observability for internal application behavior.
- UI hierarchy/user interaction event capture is explicitly not needed now.
- Preference: OpenTelemetry, low cost, low vendor lock.
- Work style: discuss, create, and design incrementally before implementation.

## Guardrails Touched

- Runtime state and logs live under the application runtime home.
- Service layer owns workflow semantics; UI should not own telemetry semantics.
- ML adapters emit progress/log events through service-owned callbacks or
  loggers.
- Storage and migration changes require explicit handshake before execution.
- Public beta telemetry must avoid sensitive dataset contents, file contents,
  credentials, provider keys, prompts, raw LLM responses, and user-managed paths
  unless a later explicit privacy contract allows a redacted form.

## Current Facts

- Existing app logs are local rotating text logs at `logs/xenix.log`.
- Existing ML task logs are task-scoped JSONL files under
  `artifacts/ml-tasks/<ml-task-id>/logs.jsonl`.
- Existing Python dependencies do not include OpenTelemetry packages.
- Existing AI observability work focuses on provider request/token usage and
  inline Chatbot display; it is not a general runtime telemetry pipeline.
- Xenix is a one-process native Python/PySide6 desktop app with local SQLite and
  filesystem-managed artifacts.
- Optional SSH ML workers exist; remote execution/cache state must return
  results to local service-managed task directories before success.
- OpenTelemetry Python currently supports OTLP exporters and environment-driven
  configuration; OTLP export through a Collector is the production best-practice
  path in official docs.

## Unknowns

- Whether beta telemetry should be opt-in, opt-out, or disabled by default with
  a support toggle.
- Whether remote export is needed in the very first beta build, or whether local
  telemetry bundles are enough for the first feedback loop.
- Which backend should receive OTLP if remote export is enabled.
- Whether logs should be exported as OTel logs in v1, or only correlated locally
  through trace ids.
- Whether telemetry storage should include a local OTLP file/JSONL spool for
  offline upload and crash-adjacent recovery.
- How much runtime identity is acceptable: anonymous install id, session id,
  build commit, OS, Python version, package mode, feature flags, worker kind.
- Cardinality budgets for attributes such as model key, tool name, task kind,
  provider key, exception type, and dataset shape buckets.

## Constraints Observed

- Avoid vendor-specific SDKs in application code.
- Keep beta cost low.
- Preserve local-first product posture.
- Minimize performance and package-size overhead.
- Avoid UI event telemetry for now.
- Prefer explicit service-level spans/events over blind monkey-patching for the
  first slice, because Xenix behavior of interest is mostly domain workflow,
  task execution, provider calls, storage bootstrap, and artifact handling.
- Keep discussion separated across three axes:
  1. Internal collection infrastructure.
  2. Instrumentation/semantic event design.
  3. Transport/export/backend.

## Candidate Paths

1. Infrastructure-first:
   - Define telemetry facade, lifecycle, runtime identity, redaction boundary,
     local buffering, and no-op behavior.
   - Defer exact instrumentation catalog and export backend until the base
     contract is stable.
2. Instrumentation-first:
   - Define the minimal event/span/metric catalog from beta diagnostic
     questions.
   - Defer transport decisions except for required attributes and privacy
     constraints.
3. Transport-first:
   - Choose local bundle, direct OTLP, or Collector-backed export first.
   - Then constrain infrastructure and event schema to what that path can
     support.
4. Three-axis convergence:
   - Discuss infrastructure, instrumentation design, and transport separately.
   - Recombine only at explicit checkpoints where decisions affect each other.

## Verification Anchors

- Unit tests prove telemetry initialization is no-op when disabled.
- Unit tests prove sensitive fields are redacted or absent from span/log
  attributes.
- Smoke test proves startup succeeds with telemetry disabled.
- Targeted test or fake exporter proves service spans/metrics are emitted when
  enabled.
- Packaged smoke test proves PyInstaller build includes required OTel packages
  only when selected.
- Manual collector test proves OTLP HTTP export can reach a local collector.

## Smallest Confirmation Needed

- Is beta telemetry allowed to send data remotely by default, or must it be
  explicit opt-in?
- Is the first beta success criterion "developer can diagnose from user-sent
  local bundle" or "developer can see aggregated remote dashboards"?
- Should v1 include traces and metrics only, or traces, metrics, and OTel logs?
- What backend budget exists, if any, for the beta period?
- Which axis should be solidified first: internal collection infrastructure,
  instrumentation design, or transport/export?

## Promotion Candidate Truths

- Leave empty until stable.
