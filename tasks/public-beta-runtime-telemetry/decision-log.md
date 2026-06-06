# Public Beta Runtime Telemetry Decision Log

## 2026-06-05

- Input classified as `Intent + Constraint`.
- Current mode is `Explore`.
- User preference captured: OpenTelemetry, low cost, low vendor lock.
- Scope captured: internal application behavior telemetry; UI hierarchy/user
  interaction event capture is excluded for now.
- Existing `issue-84-ai-observability` is related but not the owner for this
  work, because it covers AI token/provider usage display rather than a general
  runtime telemetry pipeline.
- No implementation or durable documentation mutation has been approved.
- User corrected the discussion shape: separate internal collection
  infrastructure, instrumentation design, and transport/export instead of
  treating them as one mixed telemetry topic.
- Packet updated with `discussion-axes.md` and the working design now uses the
  three-axis model.
- Internal collection infrastructure draft added: Xenix-owned telemetry facade,
  no-op-safe lifecycle, allowlist redaction, trace-log correlation, and context
  propagation across ML worker boundaries.
- User accepted the Xenix-owned facade direction but prefers mature SDKs or
  Python built-ins where possible, avoiding unnecessary new entities.
- User prefers a typed event registry over a generic attribute allowlist for type
  safety, analysis quality, and information safety.
- User agrees existing `logs/xenix.log` remains the primary diagnostic asset and
  recommends migrating it to JSON logs.
- User prefers context propagation based on trace, span, and owner rather than
  custom attributes or body payloads.
- User considers `session_id` less important and prefers a persistent anonymous
  install id.
- User noted the previous topology was too flat.
- User states OpenTelemetry SDK should be treated as export/transport, while
  internal collection infrastructure should be completed first.
- User clarified that mature open source solutions should be investigated before
  building a bespoke event registry.
- User clarified that local logs are an export/sink, equivalent in layer to OTel
  export, rather than the internal collection substrate.
- Research file added for OpenTelemetry API/Semantic Conventions/Weaver,
  structlog, python-json-logger, and Eliot.
- User clarified that vendor-lock concern is about downstream
  observability/analysis products such as Better Stack or Datadog, not about
  OpenTelemetry itself.
- Direction updated: fully embrace OpenTelemetry as the desired vendor-neutral
  substrate; keep Xenix facade thin rather than building a thick parallel model.
- User challenged whether even a thin Xenix facade should be solved by mature
  libraries. Reassessment: most facade responsibilities should be covered by
  OTel API/SDK, OTel logging instrumentation, environment configuration,
  Semantic Conventions, and Weaver. Xenix should keep only tiny helpers for
  bootstrap, resource attributes, domain naming, privacy gates, and worker
  context propagation.
- User suggested `structlog + logging` may replace the Xenix telemetry facade.
  Current refinement: it can replace a Xenix-owned structured logging/event
  facade, but should not replace OTel traces, metrics, semantic conventions, or
  propagation. Preferred composition is OTel for traces/metrics/context plus
  structlog/stdlib logging for structured logs/events with OTel trace
  correlation.
- User clarified that "Xenix telemetry facade" means the structured
  logging/event developer interface. Stage conclusion: mature tooling is enough
  for the internal observability substrate and telemetry transport discussion.
  The conversation can move to instrumentation strategy and tactics.
- Started `beta-diagnostic-question-matrix.md` so the user can make scope
  tradeoffs across P0/P1/P2 diagnostic questions.
- User accepted the `Initial Cut Proposal`: keep P0 by default unless privacy or
  implementation concerns reject an item; promote only selected P1 items that
  directly support public beta feedback loops; defer P2 unless nearly free after
  P0/P1 instrumentation exists.
- User clarified the desired collaboration level for instrumentation: they will
  provide high-level strategy and tactics, not review concrete event names,
  fields, or privacy rules. Event names should be self-explanatory; tracing
  information must live in trace/span/owner context rather than attributes/body;
  existing models should be reused wherever possible; no new entity should be
  introduced merely because it is described as minimal.
- Opened `model-as-observability-source.md` to discuss reusing existing domain
  records and lifecycle transitions as telemetry sources before considering any
  new telemetry-specific entities.
- Added `implementation-slices.md` as a design slicing document, not an
  implementation start.
- User approved implementation start on 2026-06-06.
- Scope decision: implement all slices.
- Product/privacy decision: persistent anonymous install id is approved.
- Logging decision: use `structlog`.
- Transport decision: include OTLP remote export in the first batch. Acceptance
  will include a manual OTLP remote connection by the user; development and
  packaged distribution connection shape still needs implementation detail.
- Implementation completed for the first batch on 2026-06-06 with OTel
  bootstrap/export configuration, structlog JSON local logs, install id,
  startup/storage/Agent/ML/artifact/data-analysis instrumentation, diagnostic
  bundle support, docs, tests, and PyInstaller hidden-import updates.

## Rejected Or Deferred

- Vendor-specific SDK in application code: rejected for now because it conflicts
  with the vendor-lock constraint.
- Full UI interaction analytics: explicitly deferred by prompt.
- Raw dataset/prompt/path capture: rejected for privacy and beta trust.
