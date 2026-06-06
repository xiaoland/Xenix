# Runtime Telemetry Discussion Axes

## Why Split The Discussion

The first exploration mixed three concerns:

- How telemetry is collected inside the app.
- What should be instrumented.
- How telemetry leaves the machine, if at all.

Those concerns interact, but they should not be decided as one bundle. Keeping
them separate makes the design easier to reason about and lowers the chance of
accidentally choosing a backend before the product/privacy contract is clear.

## Axis 1: Internal Collection Infrastructure

Core question:

- What is the minimum in-process telemetry substrate Xenix needs, regardless of
  where data goes later?

Topics:

- Telemetry facade location and ownership.
- OpenTelemetry API/SDK dependency boundary.
- Disabled/no-op behavior.
- Runtime/session/install identity.
- Semantic schema, redaction, and attribute filtering.
- Sink/export independence, including local logs and remote export.
- Trace-log correlation with existing `xenix.log`.
- Lifecycle: initialization, shutdown flush, failure isolation.
- Testability through fake exporters or in-memory readers.

First-principles invariant:

- Product/service code should emit stable domain signals; it should not know the
  eventual vendor/backend.

### Current Proposed Shape

The internal infrastructure should be OTel-first. A Xenix facade, if present,
should be tiny: project-local helpers and conventions, not a separate telemetry
framework.

Mature OTel responsibilities:

- Trace/span/context API.
- Metrics API and SDK readers.
- Runtime processors/exporters.
- Environment-driven SDK/export configuration.
- Log correlation through OTel logging instrumentation.
- Standard semantic conventions and optional Weaver custom semconv registry.

Mature logging responsibilities:

- `logging` remains the Python logging interoperability backbone.
- `structlog` can provide structured event/log authoring, context binding, and
  JSON rendering.
- OTel logging instrumentation can inject trace/span/service context into stdlib
  logging records and can bridge logs into OTel log processing/export.

Remaining Xenix responsibilities:

- Initialize telemetry once during runtime bootstrap, near logging setup.
- Define project-local semantic conventions for Xenix owners where official OTel
  conventions do not apply.
- Provide tiny helpers only where raw OTel calls would be noisy or unsafe.
- Add build/version/package/install-id resource attributes.
- Prevent unsafe domain attributes from being attached to spans, metrics, or log
  records.
- Provide context propagation helpers for background workers, subprocess ML
  execution, and SSH worker task requests.
- Flush and shut down cleanly on application exit.
- Fail closed: telemetry failures are logged locally at most and never break app
  workflows.

Proposed non-responsibilities:

- It should not decide the full instrumentation catalog.
- It should not decide the remote backend.
- It should not collect UI interaction events by default.
- It should not expose raw OpenTelemetry SDK types to services.
- It should not hide OpenTelemetry behind a thick abstraction. The desired shape
  is a thin Xenix facade over OTel concepts, because OTel is the preferred
  vendor-neutral substrate.
- It should not duplicate OTel APIs such as `start_as_current_span`, meters, log
  correlation, propagators, or environment configuration unless a Xenix-specific
  safety rule requires it.
- It should not treat local logs as the internal source of truth; local JSON logs
  are an export/sink path just like OTLP export is.

### Minimum Xenix Helper Concepts

- `configure_otel(paths, build_info, install_id)`: one bootstrap integration.
- `configure_logging(paths)`: one bootstrap integration for stdlib logging,
  optional structlog processors, JSON output, and OTel log correlation.
- `xenix_resource_attributes(...)`: safe process/app resource attributes.
- `xenix_span_name(owner, operation)`: naming helper if semconv constants are not
  enough.
- `safe_domain_attributes(owner, values)`: project privacy gate for domain
  attributes.
- `inject_context(carrier)` / `extract_context(carrier)`: thin wrappers over
  OTel propagators for process and worker boundaries.

### structlog + logging Boundary

`structlog + logging` can replace a Xenix-owned structured logging/event facade.
It should not replace OTel's trace, metric, semantic convention, or propagation
APIs.

The intended split:

- Use OTel spans to describe operation boundaries and causality.
- Use OTel metrics for counts, durations, and distributions.
- Use structlog/logging for parseable local diagnostic events.
- Use OTel log correlation so logs carry the active trace/span context.
- Avoid modeling spans as log lines or metrics as log aggregation.

The facade should prefer Python built-ins and mature SDK concepts where they fit:

- `logging` for local diagnostic logs.
- `contextvars` for in-process context.
- OpenTelemetry API concepts for trace/span/context and metrics, while keeping
  backend-specific exporters outside domain code.
- OpenTelemetry SDK may be part of internal runtime collection when enabled; the
  lock-in concern is hosted backend/analysis tooling, not OTel itself.
- OpenTelemetry Semantic Conventions and potentially Weaver for schema,
  validation, documentation, and generated constants/helpers.
- `dataclasses`, `typing`, `enum`, and/or Pydantic only as thin local typing
  helpers if the mature schema tooling does not provide enough Python ergonomics.

### Local Runtime Identity

Always acceptable:

- Ephemeral `session_id`.
- Build/version metadata.
- Runtime mode and package mode.
- OS/Python coarse metadata.

Needs explicit product/privacy confirmation:

- Persistent anonymous install id. Current user preference favors this over
  ephemeral session id for beta diagnostics.
- Any machine fingerprint.
- Any hashed path, provider key, model key, SSH host, or user-config-derived
  identifier.

### Worker Boundary Implication

Xenix already has local and SSH ML worker paths. Internal telemetry should be
able to propagate correlation through `request.json`, environment variables, or
task metadata so task logs and parent service spans can be connected later.

This does not require remote telemetry from workers in the first slice. The
minimum is enough correlation data for local task logs and support bundles.

### Logging Implication

Existing `logs/xenix.log` remains the primary local diagnostic artifact. The
infrastructure should enrich log records with safe correlation fields such as:

- `trace_id`
- `span_id`
- `owner` when already in context, for example `agent.turn`, `ml.task`, or
  `storage.bootstrap`
- optional stable owner id when the owner has an existing safe internal id

The formatter should tolerate telemetry being disabled.

Current direction: migrate `xenix.log` from line-oriented text to JSON Lines so
it can be reliably parsed, bundled, filtered, and joined with typed telemetry
events.

### Mature Schema Tooling Instead Of Bespoke Registry

The previous draft used a generic attribute allowlist, then a bespoke typed event
registry. The better direction is to investigate mature open source schema and
semantic-convention tooling before building anything project-specific.

Current preferred direction:

- Treat local JSON logs and OTLP as export paths, not internal collection
  substrate.
- Use Xenix facade as the app-owned boundary.
- Fully embrace OpenTelemetry API/SDK concepts for trace/span/context and metrics
  inside or behind a thin facade.
- Prefer OpenTelemetry Semantic Conventions and potentially Weaver for schema,
  registry, documentation, validation, and code generation.
- Use stdlib logging/JSON formatting or structlog only for local log export, not
  as the internal source of truth.

A Xenix-specific registry should only exist if mature tooling is too heavy or
does not cover the needed domain schema. If it exists, it should likely be a thin
semantic convention layer, not a custom telemetry framework.

Desired properties:

- Each event/span/metric family has a typed schema.
- Each field has a declared type, cardinality class, privacy class, and optional
  projection to logs, metrics, traces, or exports.
- Unknown fields are rejected rather than scrubbed.
- Derived/exported telemetry is generated from registered fields, not arbitrary
  payload dictionaries.
- This gives better type safety, safer privacy behavior, and more stable
  downstream analysis.

Example registry concepts:

- `owner`: durable domain owner such as `app.startup`, `agent.turn`,
  `agent.provider_request`, `ml.task`, or `artifact.register`.
- `kind`: operation subtype such as task kind, provider request kind, or tool
  name when cardinality is bounded.
- `status`: `started`, `succeeded`, `failed`, `cancelled`.
- `duration_ms`: numeric projection for metrics.
- `error_type`: exception class name or normalized domain error code.

Raw message/body fields are not part of the default registry.

## Axis 2: Instrumentation Design

Core question:

- Which internal behaviors should be measured so beta feedback becomes
  diagnosable?

Topics:

- Diagnostic questions.
- Span taxonomy.
- Metric taxonomy.
- Event naming.
- Attribute schema and cardinality budget.
- Privacy rules for attributes.
- Coverage priorities by workflow.
- Required correlation ids: thread id, turn id, task id, artifact id, session id.
- What not to instrument in v1.

First-principles invariant:

- Every signal must answer a known operational or product-quality question.
  Otherwise it is noise, cost, and privacy risk.

### Stage Entry

Internal collection and transport assumptions are now sufficiently clear:

- OTel owns traces, metrics, propagation, semantic conventions, SDK/export
  configuration, and backend neutrality.
- `structlog + logging` owns the structured logging/event developer interface
  and local JSON log authoring.
- OTel logging instrumentation correlates logs with active trace/span context.
- Xenix-specific code is limited to bootstrap glue, resource attributes,
  privacy guardrails, optional semantic convention constants/helpers, and ML
  worker propagation wiring.

Instrumentation design can now focus on what to measure and why.

### Strategic Questions

- What beta diagnostic questions must be answerable without asking the user for
  a repro first?
- Which workflows are core to public beta success?
- Which failures are most expensive to diagnose from ordinary logs alone?
- Which signals should exist as traces, which as metrics, and which as
  structured logs/events?
- What must not be captured even if it would be diagnostically useful?

### Tactical Questions

- Where are the minimum durable span boundaries?
- Which metrics need histograms versus counters?
- Which structured log events should be emitted at workflow start/end/failure?
- Which attributes are low-cardinality and safe?
- Which workflow ids are safe correlation fields?
- What is the v1 sampling policy by workflow?
- What tests prevent accidental sensitive-field capture?

### User Decision Level

The user will make high-level strategic and tactical decisions, not review every
event name, field name, or privacy rule.

Accepted user principles:

- Event names should be self-explanatory.
- Attributes and bodies must not carry tracing-purpose information; tracing
  belongs to trace/span/owner context.
- Reuse existing domain models, identifiers, lifecycle states, and error shapes
  where possible.
- Do not add new entities unless an existing model cannot carry the required
  observability meaning.
- "Minimal" is not a sufficient justification for a new entity.

Implication:

- Detailed signal contracts are an engineering deliverable derived from these
  principles.
- Before implementation, the handshake should summarize scope, model reuse,
  entity additions if any, and verification, not ask the user to approve a large
  field-by-field spec.

## Axis 3: Transport / Export

Core question:

- How should telemetry reach the developer during beta, and what cost/vendor
  tradeoff is acceptable?

Topics:

- Local-only diagnostic bundle.
- Direct OTLP export.
- OTLP through OpenTelemetry Collector.
- Backend choice and budget.
- Consent model.
- Offline behavior and retry.
- Payload size and rate limits.
- Sampling.
- Failure mode when telemetry endpoint is unreachable.

First-principles invariant:

- Telemetry transport must never block, slow, or break the user workflow.

## Current Working Separation

Recommended discussion order:

1. Internal collection infrastructure.
2. Instrumentation design.
3. Transport/export.

Reason:

- Infrastructure sets the safety boundary.
- Instrumentation then defines the useful signal catalog.
- Transport is easier to swap when the first two layers are clean and
  vendor-neutral.
