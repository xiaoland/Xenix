# Internal Collection Infrastructure Open Source Research

## Question

Which mature open source solutions fit Xenix's internal observability collection
requirements without forcing us to build a bespoke event registry or couple
domain code to a vendor/backend?

## Current Correction

Local JSON logs and OTLP backend delivery should both be treated as export/sink
paths. They are not the internal collection substrate by themselves.

Clarified vendor-lock concern:

- The concern is lock-in at the observability analysis/backend layer, such as
  Better Stack, Datadog, or another hosted analysis product.
- OpenTelemetry itself is the desired vendor-neutral substrate and should be
  embraced broadly.
- Xenix facade should therefore be thin. It should not hide OTel so much that
  Xenix invents a parallel observability model.

Internal collection should focus on:

- instrumentation API;
- trace/span/owner context;
- semantic schema and type safety;
- local process and worker propagation;
- sink/export independence.

## Candidate: OpenTelemetry API + Semantic Conventions + Weaver

### Fit

This is currently the strongest candidate.

OpenTelemetry separates API and SDK. Application/library code can call the API,
while the application owner installs/configures the SDK to process and export
telemetry. The official Python docs describe using the API to instrument code
and the SDK to initialize/configure collection.

OpenTelemetry's client architecture separates signals while sharing context
propagation. This matches Xenix's need to handle traces, metrics, logs/events,
and worker propagation without making logs or OTLP the internal source of truth.

Semantic Conventions define names, attribute types, metric instruments, units,
span naming, logs, events, and resources. This is close to the "event registry"
need, but mature and standard.

Weaver is the OpenTelemetry tool for building, validating, documenting, evolving,
and generating artifacts from semantic convention registries. It supports custom
registries that import official OTel conventions. This may let Xenix define a
small domain semconv registry instead of building a custom registry system.

### Strengths

- Vendor-neutral.
- Mature ecosystem.
- Standard trace context propagation.
- Python supports traces and metrics as stable signals; logs are still marked
  development in the Python status page.
- API can be kept in or behind the Xenix facade while SDK/exporters remain
  configurable.
- Weaver can validate schema consistency, generate docs/constants, diff schema
  evolution, and potentially run live compliance checks.

### Risks

- OTel semantic convention tooling, especially custom registry/codegen, may be
  more ceremony than the first beta needs.
- Python logs signal is not as mature as traces/metrics.
- Exposing raw OTel APIs throughout domain code can weaken the Xenix-owned
  facade boundary unless disciplined.
- Some Xenix domain concepts will require custom semantic conventions.

### Possible Xenix Shape

- Xenix facade remains the only app-facing entrypoint.
- Facade internally delegates tracing/metrics context to OpenTelemetry API.
- SDK/exporters are configured only by runtime/export adapters.
- Xenix domain signal definitions live as a small semconv/weaver registry or a
  simpler constants layer generated/validated from it.
- Local JSON logs are one sink, produced from current context and structured log
  records.
- OTLP is another sink/export path, configured later.

## Candidate: structlog

### Fit

structlog is a mature Python structured logging library with contextvars support,
JSON rendering, stdlib logging integration, testing affordances, and OpenTelemetry
integration points.

### Strengths

- Good for structured local logs.
- Strong contextvars story.
- Integrates with Python stdlib logging.
- Mature and production-tested.

### Limits For Internal Collection

- It is logging-centered.
- It does not naturally cover metrics as a first-class signal.
- It does not provide standard trace/span propagation.
- If used as the internal collection substrate, it would bias the architecture
  toward "events as logs", which conflicts with the correction that local logs
  are an export path.

### Possible Xenix Shape

- Use `structlog + logging` as the mature structured log/event layer.
- Let structlog provide ergonomic structured log calls, context binding, JSON
  rendering, and stdlib logging interop.
- Let OpenTelemetry logging instrumentation inject trace/span/service context
  into log records.
- Do not use structlog to replace OTel traces, metrics, semantic conventions, or
  W3C propagation.

### Facade Implication

If "Xenix telemetry facade" means "a project-owned structured event/logging API",
then `structlog + logging` can mostly replace it.

If it means "the observability substrate for traces, metrics, logs, context
propagation, and export independence", then it should not replace OpenTelemetry.

The better composition is:

- Traces: OpenTelemetry tracer.
- Metrics: OpenTelemetry meter.
- Context propagation: OpenTelemetry propagators.
- Structured logs/events: structlog on top of stdlib logging.
- Log-trace correlation: OpenTelemetry logging instrumentation.
- Schema/naming: OTel Semantic Conventions and optional Weaver-generated custom
  conventions.

## Candidate: python-json-logger

### Fit

python-json-logger is a JSON formatter for Python's standard `logging` package.

### Strengths

- Minimal migration path from current logging setup.
- Keeps existing `logging.getLogger(__name__)` pattern.
- Good fit for local JSON log export.

### Limits For Internal Collection

- Formatter only.
- No trace/span model, metrics model, schema registry, or propagation.

### Possible Xenix Shape

- Candidate for the local JSON log sink.
- Not a collection substrate.

## Candidate: Eliot

### Fit

Eliot provides causal action chains for Python logs and supports cross-process
or distributed causal tracing concepts.

### Strengths

- Strong "why did this happen" model.
- Good causal chains for local logs.
- Scientific computing use case is adjacent to Xenix's ML workflows.

### Limits For Internal Collection

- Separate observability model from OTel.
- Logging-centered.
- Smaller ecosystem and weaker direct path to OTel metrics/trace standards.
- Would likely compete with OTel rather than complement it.

### Possible Xenix Shape

- Interesting reference model for causal actions.
- Not preferred as the core substrate unless OTel proves too heavy.

## Current Recommendation

Use OpenTelemetry as the mature internal observability substrate, while keeping
a thin Xenix facade boundary:

- Internal API: Xenix facade delegates directly to OTel API/SDK concepts for
  trace/span/context, metrics, and eventually logs/events where the Python signal
  maturity is acceptable.
- Internal schema: OTel Semantic Conventions plus a small Xenix custom semantic
  convention registry, ideally checked/generated by Weaver if the ceremony is
  acceptable.
- Exports: local JSON logs, local diagnostic bundles, and OTLP backends are sinks
  configured outside domain code.
- Logs: prefer `structlog + logging` if we want an ergonomic structured event/log
  authoring surface; otherwise stdlib logging with JSON formatting is enough.
  In either case, logs remain a signal/export path correlated with OTel traces.

This avoids building a custom event registry while keeping Xenix domain code
vendor-neutral and backend-independent.

## Facade Reassessment

The thin Xenix facade may be mostly solvable by mature OpenTelemetry libraries.
It should not become a framework.

Mature pieces that can replace facade responsibilities:

- Trace/span/context API: `opentelemetry-api`.
- Runtime providers/processors/exporters: `opentelemetry-sdk`.
- Standard configuration: OTel environment variables such as
  `OTEL_SDK_DISABLED`, `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES`, exporter
  configuration, span/log limits, and metric export intervals.
- Log correlation: `opentelemetry-instrumentation-logging` can inject trace id,
  span id, service name, and sampled flag into stdlib logging records.
- Third-party library spans: OTel Python instrumentation libraries where useful.
- Naming/schema: OTel Semantic Conventions plus optional Weaver custom registry.

Remaining Xenix-specific responsibilities are smaller:

- Project-local helper names for domain spans, if plain OTel calls become too
  repetitive.
- Xenix semantic convention constants or generated helpers.
- Privacy guardrails for domain attributes before setting span/log/metric
  attributes.
- Resource attributes such as build commit, app version, package mode, and
  persistent anonymous install id.
- A single bootstrap function that wires OTel configuration into the existing
  app startup path.
- Optional logging setup glue that configures structlog/stdlib logging and OTel
  log correlation consistently.

Therefore the target should be "OTel-first with tiny Xenix helpers", not "Xenix
telemetry facade backed by OTel".

## Sources

- OpenTelemetry Python docs: API/SDK packages, traces and metrics stable, logs
  development.
- OpenTelemetry Python SDK docs: SDK manages and exports traces, metrics, and
  logs, including batching and delivery.
- OpenTelemetry specification overview: signals share context propagation while
  remaining independent; SDK implements API; Collector can receive telemetry
  from OTel or other libraries.
- OpenTelemetry Python instrumentation docs: apps use SDK initialization and API
  instrumentation; libraries use API only.
- OpenTelemetry propagation docs: trace context can be manually injected and
  extracted through carriers.
- OpenTelemetry semantic conventions docs: conventions define names, attributes,
  instruments, units, span names, logs, events, resources.
- OpenTelemetry Weaver docs: custom registries, validation, code/docs
  generation, diffs, live checks, and generated sample telemetry.
- structlog docs: production structured logging, JSON output, contextvars, stdlib
  logging integration.
- python-json-logger docs: JSON formatter for Python stdlib logging.
- Eliot docs: causal chains of actions and structured logs.
