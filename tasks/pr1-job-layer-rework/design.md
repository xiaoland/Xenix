# PR1 Job Layer Rework — Design

## Decisions (resolved)

- D1 = B: deep rework. One unified JobRow table becomes the queue and lifecycle
  record; domain queue mechanics retire. Scheduler owns dispatch; domain
  services keep results, recovery semantics, and artifact finalization.
- D2: absorbed by B — JobRow is the queue record; no separate queue table.
- D3 restart semantics: ML = permanent orphan (deliberate, preserve exactly —
  queued ML jobs are never auto-requeued after restart). Knowledge = requeue
  after domain-side verification (existing _recover_imports / index recovery).
- D4: Job Center gains per-job actions (cancel / retry / view log) shown by
  capability, routed through domain services. Keep the window modeless.
- D5: global FIFO dispatch within per-domain concurrency caps (ML cap from
  worker settings pool; Knowledge serial per service).
- D6: product vocabulary (naming, user-facing statuses) — deferred to Phase 5,
  owner docs/10-prd.

## Product design

- "Job" = one unit of user-visible background work from ML or Knowledge,
  managed in one place (Jobs window): submit, observe, cancel, retry.
- Unified lifecycle: queued → running → succeeded / failed / cancelled.
  Knowledge "needs_attention" remains a domain state, displayed under
  failed/attention in the unified view.
- Restart behavior is visible, not hidden: ML queued jobs surviving a restart
  stay queued forever (orphan) by product decision; Knowledge jobs resume.
- The Jobs window is the single management surface for both domains; domain
  dialogs (Knowledge workspace) keep their existing flows.

## Technical design

### Storage

- New JobRow table (SQLModel, enum values lowercase like MLTaskRow):
  id (str PK), domain (StrEnum: knowledge/ml), kind (str), reference (str,
  domain row id), status (JobStatus StrEnum), phase (str), created_at,
  updated_at, started_at/finished_at nullable, error_summary nullable.
  Indexes: (status), (domain, status), (updated_at).
- Migration edge v26→v27: raw SQL CREATE TABLE + indexes, then BACKFILL job
  rows from ml_task / knowledge_import / knowledge_derivation /
  knowledge_index_task with status normalization (pending→queued, canonical
  completion states→succeeded, failed/needs_attention→failed). Bump user_version.
- models.py JobRow must match the raw SQL exactly; fresh bootstrap goes through
  SQLModel.metadata.create_all.

### Scheduler

- New src/xenix/services/job_scheduler.py: JobScheduler + JobHandler protocol.
  JobHandler: enqueue(job) → reference; recover() → list[JobRow] to requeue
  (domain decides after its own verification); run(job_row) executes domain
  work via domain service methods; request_cancel(job_row); capabilities(job).
- Dispatch loop: persisted FIFO over JobRow where status=queued, gated by
  per-domain concurrency cap; transitions job row queued→running (and back on
  domain cancel). Thread-per-running-job dispatch (matches today's ML pattern);
  heavy compute stays in domain subprocess workers.
- Recovery at startup: walk JobRow where status in (queued, running); ask each
  domain handler; ML handler returns none (permanent orphan — running rows
  reset to queued? NO: leave rows exactly as persisted; never auto-dispatch).
  Knowledge handler runs its existing verification and returns requeue list.
- JobQueryService repurposed: feed now reads JobRow (single source), joins
  domain rows only for display names (dataset/file titles). The pending→queued
  mapping bug disappears by construction once the feed reads JobRow.

### Domain integration

- ML: MLTaskService loses queue.Queue/dispatcher/_dispatch_loop/
  _ensure_dispatcher_locked; keeps create/start/complete/fail/cancel/finalize
  and ALLOWED_TRANSITIONS. MLService call sites (3x submit_ml_task) become
  scheduler.enqueue via MLJobHandler. Handler run() calls start_ml_task +
  worker runner as today.
- Knowledge: import/derivation/index services lose their queue+worker threads;
  enqueue_file / enqueue_generation / enqueue_rebuild submit to the scheduler
  through their handlers. _recover_imports keeps source-snapshot verification
  but reports requeue decisions to the scheduler instead of a private queue.
  Synchronous waiters (wait_for_import) keep polling domain rows.
- Consistency invariant: handler transitions update JobRow first, then the
  domain row through existing domain methods; domain finalization never writes
  JobRow directly.

### GUI

- JobCenterDialog keeps the QThreadPool + generation pattern; adds action
  buttons enabled per job capability (capabilities come from JobHandler).
  Actions route through the scheduler/domain services, never touch DB directly.
  i18n: extract, complete both catalogs, compile.

## Risks

- Dual state drift between JobRow and domain rows — mitigated by single
  transition path (handler methods) + integration tests.
- Migration backfill correctness for deployed DBs — mitigated by edge test
  covering every domain status value.
- Knowledge synchronous import_file path (agent tools) must keep working —
  covered by existing tests + new integration test.
