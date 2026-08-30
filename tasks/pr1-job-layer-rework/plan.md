# PR1 Job Layer Rework — Implementation Plan

Each phase lands as one verified slice. No commit without explicit instruction.

## Phase 0 — Stopgap bug fix (isolated, lands first)

- src/xenix/services/job_service.py: add _ml_status() mapping MLTaskStatus →
  JobStatus (pending→queued, rest 1:1, unknown → ValueError), mirroring
  _knowledge_status(); use it in _ml_jobs instead of JobStatus(task.status.value).
- tests/test_job_service.py: regression test — ML task with PENDING status
  projects to QUEUED and list_jobs() does not raise.
- Verify: pdm run pytest tests/test_job_service.py -q, pdm run check.
- Note: superseded by Phase 1/2 feed switch to JobRow; kept as cheap relief.

## Phase 1 — Job table + scheduler core

- models.py: JobRow (id, domain, kind, reference, status, phase, timestamps,
  error_summary) with lowercase StrEnum columns; indexes on status,
  (domain, status), updated_at.
- migrations.py: migrate_v26_to_v27 — CREATE TABLE job + indexes, backfill
  from ml_task / knowledge_import / knowledge_derivation / knowledge_index_task
  with status normalization; wire into chain; CURRENT_SCHEMA_VERSION → 27.
- tests/storage/test_migrations.py: v26→v27 edge test (old DB, backfill
  assertions incl. pending→queued and every Knowledge terminal state) +
  fresh-bootstrap equivalence (create_all vs migrated shape).
- services/job_scheduler.py: JobScheduler (FIFO dispatch, per-domain caps,
  cancel, recovery walk, handler registry) + JobHandler protocol.
- tests/test_job_scheduler.py: fake handlers — FIFO order, per-domain cap
  blocks second job, cancel queued/running, recovery applies per-domain policy
  (ML orphan: rows left untouched, never dispatched; Knowledge requeue list).
- Verify: focused pytest + pdm run check.

## Phase 2 — ML adapter

- services/ml_job_handler.py (or job_handlers/ml.py): MLJobHandler wrapping
  MLTaskService; creates JobRow on task creation/submission; run() =
  start_ml_task + worker runner + finalize as today.
- ml_task_service.py: remove _queue/_dispatcher_thread/_dispatch_loop/
  _ensure_dispatcher_locked/_run_queued_task/_submitted_ids; keep state
  machine, finalization, observability, callbacks.
- ml_service.py: 3 submit_ml_task call sites route through scheduler.enqueue.
- app.py: compose JobScheduler + handlers; inject where MLTaskService started.
- Update affected tests (tests/ml/test_ml_task_service.py and ML flow tests):
  prove tasks still run end to end via the scheduler; orphan policy test —
  fresh scheduler over DB with queued ML job does not dispatch it.
- Verify: focused pytest + pdm run check.

## Phase 3 — Knowledge adapters

- Handlers for import / derivation / index services; enqueue_file /
  enqueue_generation / enqueue_rebuild submit via scheduler; retire each
  service's queue + worker thread; _recover_imports returns requeue decisions
  to the scheduler (snapshot verification preserved).
- Keep synchronous wait_for_import polling domain rows.
- Knowledge requeue policy test: fresh scheduler + verified source → job
  dispatched; missing snapshot → needs_attention, not dispatched.
- Verify: tests/knowledge/* + pdm run check.

## Phase 4 — GUI actions

- job_service.py: JobQueryService feeds from JobRow (single source); JobItem
  gains capability flags (can_cancel/can_retry/can_view_log) and domain
  reference; drop _knowledge_status/_ml_status normalizers once feed is JobRow.
- job_center.py: action buttons wired to scheduler/domain services; refresh
  after action; i18n extract/complete/compile both catalogs.
- tests/runtime/test_job_center.py: offscreen dialog tests (pattern from
  test_settings_dialog.py) — feed render, filters, summary counts, actions
  enabled/disabled by capability, cancel/retry route correctly.
- Verify: focused pytest + pdm run check + pdm run smoke.

## Phase 5 — Vocabulary + full verification

- docs/10-prd: adopt unified Jobs vocabulary (D6) if user approves wording.
- Full suites: pdm run test, pdm run check, i18n-compile, pdm run smoke,
  pdm run package (spot).
