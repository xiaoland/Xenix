# Service Orchestration Guidance

## Scope

Applies to the top-level orchestration and boundary services directly under
`src/xenix/services/*.py` (job layer, ML task service, knowledge services,
dataset service, and the analysis/data helpers). It does not restate the
subtree owners for `ml/`, `agent/`, `storage/`, or `llm/`.

## Tripwires

- Job scheduling authority lives in `JobScheduler`/`JobRow` (queue, dispatch,
  per-domain concurrency, cancel). A domain handler owns its domain row
  lifecycle and reports only a terminal `JobOutcome`. `JobQueryService` is a
  read-only feed projection. See
  [Job feed contract](../../../docs/20-prd-tdd/job-feed-contract.md).
- ML task state, finalization, and artifact ownership stay in `MLTaskService`;
  the scheduler adapts it through `MLJobHandler`. ML restart semantics are a
  permanent orphan. See
  [ML task lifecycle](../../../docs/20-prd-tdd/ml-task-lifecycle.md).
- Knowledge import/derivation/index services own their domain rows and
  recovery semantics; their handlers adapt them to the scheduler (serial,
  requeue-after-restart). See
  [Knowledge Base boundary](../../../docs/20-prd-tdd/knowledge-base-boundary.md).
- Persistence goes through `storage/` models and repositories only; do not
  write domain tables from a top-level service. See
  [Storage ownership](../../../docs/20-prd-tdd/storage-ownership.md).
- Do not recreate LLM conversation, Agent Harness, or Tool-invocation
  authority here; those belong to `llm/` and `agent/` and their contracts.

Verify scheduler/dispatch behavior in `tests/test_job_scheduler.py` and
`tests/test_job_service.py`; ML lifecycle in `tests/ml/`; knowledge behavior in
`tests/knowledge/`. Use source and the named contracts—not this file—for exact
methods, enums, and transitions.
