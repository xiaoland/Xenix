# Existing Models As Observability Sources

## Position

Xenix should treat existing domain records, service boundaries, and lifecycle
state transitions as the primary observability facts.

Telemetry should be a projection of already-owned runtime facts, not a parallel
application state model.

## Why This Matters

Existing models already encode business truth:

- Agent Harness records thread, turn, message, run, provider request, tool call,
  and turn completion guard semantics.
- ML task records encode task type, status, worker-dispatched execution, result
  finalization, and artifacts.
- Artifact rows encode generated outputs and ownership.
- Dataset rows and role bindings encode data/workflow state.
- Runtime logs and ML task logs already capture local diagnostic detail.

If telemetry introduces parallel entities, it can drift from durable truth,
increase migration burden, and create a second lifecycle to maintain.

## Primary Source Map

| Observability Need | Existing Source Of Truth | Telemetry Projection |
| --- | --- | --- |
| App startup and runtime paths | runtime bootstrap, `AppPaths`, logging setup, storage bootstrap | startup/storage spans, startup status metrics, structured logs |
| Storage schema and migrations | storage bootstrap/migration service, SQLite user version | storage bootstrap span, migration status event/metric |
| Agent turn lifecycle | `AgentTurnRow`, `AgentRunRow`, Harness turn methods | turn span, status metric/log |
| Provider request lifecycle and token usage | `AgentProviderRequestRow` | provider request span, duration/status metrics, usage metrics where available |
| Tool execution lifecycle | `AgentToolCallRow`, tool-call/result Messages, Tool Registry | tool call span, status/failure metrics, structured logs |
| Turn completion guard | `AgentTurnCompletionGuardRow` | guard request span/metric; no raw guard input/output export |
| Cancellation and step budget | `AgentRunRow`, turn status, Harness control flow | cancellation/step-budget span events and counters |
| ML task lifecycle | `MLTaskRow`, `MLTaskStatus`, `MLTaskType` | task span, status/duration metrics, structured logs |
| ML worker dispatch | worker pool/runner services, task logs | dispatch/stage spans, worker-kind metrics |
| ML outputs | `MLTaskArtifactRow`, trained-model rows, artifact rows | artifact finalization/register spans and metrics |
| Artifact registration | `ArtifactRow`, `ArtifactService` | artifact register span/event |
| Dataset registration/derivation | dataset rows, artifact metadata, service calls | dataset operation spans with bucketed metadata only |

## Strategic Rules

1. Prefer lifecycle transition instrumentation over new telemetry storage.
   - Emit telemetry when existing records are created, updated, finalized, or
     projected across a service boundary.
2. Reuse existing status enums.
   - Do not create telemetry-only status values unless a domain status cannot
     express the operational fact.
3. Reuse existing operation ownership.
   - Agent Harness owns Agent spans.
   - ML services own ML task/worker spans.
   - Storage bootstrap owns migration/startup spans.
   - Artifact service owns artifact registration spans.
4. Keep trace causality outside business payloads.
   - Use OTel trace/span context and propagators.
   - Do not add trace ids to persisted business rows unless a cross-process
     propagation requirement cannot be met otherwise.
5. Keep structured logs as projections.
   - Logs should report state transitions and boundary facts, not become the
     source of truth for workflow state.
6. Do not add telemetry tables in v1.
   - Local logs, OTel SDK processors/exporters, and existing business rows are
     enough unless offline durable telemetry spooling becomes a confirmed
     transport requirement.

## When Existing Models Are Enough

Existing models are enough when:

- The model already has a lifecycle row or service method for the operation.
- The state transition can be observed at service boundaries.
- The required diagnostic data is already present as safe low-cardinality enum,
  kind, status, duration, or resource metadata.
- The operation does not need durable telemetry replay after process crash.

Examples:

- Provider request success/failure from `AgentProviderRequestRow`.
- Tool call status from `AgentToolCallRow`.
- ML task status from `MLTaskRow`.
- Artifact finalization from `MLTaskArtifactRow` and `ArtifactRow`.

## When A New Entity Might Be Justified

A new entity requires an impact handshake and should be rare.

Possible justifications:

- Durable offline telemetry spool is required before transport is available.
- Crash-adjacent events must survive process death and are not represented by an
  existing business row.
- A support bundle needs a normalized local telemetry index that cannot be
  reconstructed from logs and existing rows.
- An operation is important, has no existing lifecycle owner, and adding a
  domain-owned lifecycle record is more correct than treating it as telemetry.

Non-justifications:

- Dashboard convenience.
- Easier query shape for analytics.
- "Minimal" telemetry table.
- Avoiding careful projection from existing records.

## Open Design Questions

- Should trace context be attached only to logs/exports, or should selected
  cross-process carriers be persisted inside ML task `request.json`?
- Is provider/model identity safe as existing model metadata, or should telemetry
  project it only as family/hash?
- Should existing error summaries be mapped to normalized error classes at
  emission time, or should services first grow domain error types?
- Should support bundles query SQLite rows plus logs, or rely only on exported
  telemetry/log files?
