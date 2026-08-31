# Job Feed Contract

## Admission

Knowledge services, ML services, persistence, the Job Scheduler, and the Job Center
UI all depend on one scheduling vocabulary and one authority split. Losing it lets a
second writer, a divergent status meaning, or a competing restart policy make the
Jobs window disagree with the underlying domain work.

This contract governs the unified background-work feed. It does not restate the
[ML task lifecycle](ml-task-lifecycle.md) or the
[Knowledge Base boundary](knowledge-base-boundary.md); those owners remain the
authority for their own domain rows.

## Identity and Authority

- `JobRow` owns the unified scheduling record: a `(domain, reference)` pair is
  unique, where `domain` is `knowledge` or `ml` and `reference` is the
  domain's own stable identity.
- The scheduler owns queueing, dispatch, concurrency, and `JobRow.status`. A domain
  handler owns its domain row lifecycle and reports only a terminal `JobOutcome`.
- `enqueue` is idempotent: re-registering the same `(domain, reference)` returns
  the existing `JobRow` instead of creating a duplicate.
- The job feed (`JobQueryService`) is read-only. Lifecycle authority deliberately
  remains with the originating Knowledge or ML service.

Exact fields, enums, the table shape, and the backfill edge are owned by source,
schemas, and the migration tests.

## Lifecycle

The shared semantic progression is:

```text
queued -> running -> succeeded | failed | cancelled
queued -> cancelled
```

- Dispatch claims queued rows first-in, first-out by `(created_at, id)` and marks
  them running with `started_at`.
- A handler exception becomes `failed` with an `error_summary`; the scheduler never
  infers success from a handler that raised.
- Concurrency is per domain. Knowledge work is serial (each Knowledge handler
  declares a limit of one); ML work uses the ML service's configured concurrent-task
  limit.

## Restart and Recovery

Restart semantics are domain-specific, not a global rule:

- **Knowledge** replays: a handler's `recover` resets its persisted running rows to
  queued and materializes a fresh `JobRow` for any domain unit that surfaced during
  recovery, so queued and running Knowledge work survives an application restart.
- **ML** is a permanent orphan: queued and running ML jobs are never auto-requeued or
  redispatched after a restart. They remain bounded terminal/observable evidence and
  must be re-driven explicitly.

## Cancellation

- A queued job is cancelled directly by the scheduler (`queued -> cancelled`).
- A running job is delegated to its handler's `request_cancel`; the domain decides
  how to stop the work and the scheduler records the terminal outcome it reports.
- Handlers advertise supported management actions via `JobCapabilities`; the feed
  and UI render only those actions.

## Feed Projection

The feed maps each domain's own status vocabulary into the shared `JobStatus`
vocabulary and fails loudly on an unrecognized status rather than misclassifying it.

- Knowledge: `pending`/`queued` -> queued; `running` -> running;
  `failed`/`needs_attention` -> failed; `cancelled` -> cancelled;
  `succeeded`/`canonical_ready`/`retrieval_ready`/`reused` -> succeeded.
- ML: `pending` -> queued; `running`/`succeeded`/`failed`/`cancelled` pass
  through unchanged.

The feed presents `knowledge:<reference>` and `ml:<id>` as stable presentation ids
while keeping the domain's raw identity separately for management actions.

## Verification

Scheduling and recovery behavior is covered by `tests/test_job_scheduler.py` and
`tests/test_job_service.py`; Knowledge dispatch by
`tests/test_knowledge_job_handlers.py`; the Job Center feed projection by
`tests/runtime/test_job_center.py`. Persistence and backfill are covered by the
migration tests under `tests/storage/`.
