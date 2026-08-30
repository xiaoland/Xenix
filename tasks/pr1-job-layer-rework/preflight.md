# PR1 Job Layer Rework — Preflight

Executed before implementation. Evidence-based; results recorded per item.

## Baseline

- pdm run check: PASSED (exit 0). [run at task creation]
- pdm run test (full suite): PASSED — 185 passed in 137.67s (488 warnings, none failing).

## Migration machinery (for JobRow, D1=B)

- CURRENT_SCHEMA_VERSION = 26 (storage/migrations.py L12).
- New edge pattern: migrate_v25_to_v26 = raw SQL CREATE TABLE + indexes +
  PRAGMA user_version (L1708-1757); chain entry at L1897. v26→v27 will follow
  this pattern plus a backfill INSERT from the four domain task tables.
- Fresh bootstrap = SQLModel.metadata.create_all (L25-30) → JobRow in
  models.py must match the raw SQL column-for-column.
- Test pattern: tests/storage/test_migrations.py builds an old-version DB with
  raw SQL, runs the edge, asserts result (L44+). Reuse for v26→v27.
- Storage AGENTS.md: add a forward edge; never rewrite; prove fresh bootstrap
  AND upgrade; inspect enum representation before raw SQL (JobRow enums will
  use lowercase values like MLTaskRow).

## Scheduling touch points inventory

- ML: ml_task_service.py — queue.Queue L149, dispatcher thread L151/L305-342,
  submit via _queue.put L216, per-task threads L319. Drivers: ml_service.py
  submit_ml_task call sites L443, L601, L629 (fit/tuning/evaluate+apply flows).
- Knowledge import: knowledge_import_service.py — queue L185, worker thread
  L192-204, _worker_main L440, enqueue_file L208-246, _recover_imports L856
  (queued/running → requeue or needs_attention).
- Knowledge derivation: knowledge_derivation_service.py — queue L71, thread
  L73-77, _worker_main L332; enqueued via enqueue_generation used as
  canonical_ready_notifier (app.py L590).
- Knowledge index: knowledge_index_service.py — queue L77, ThreadPoolExecutor
  L78 (status only), thread L86-96, _worker_main L436; enqueue_rebuild L98.
- Job feed: job_service.py reads MLTaskRow directly (L105-138) and Knowledge
  via KnowledgeTaskQueryService (L90-103); GUI JobCenterDialog is read-only.

## Bug evidence (user-reproduced)

- JobStatus vocabulary: queued/running/succeeded/failed/cancelled.
  MLTaskStatus vocabulary: pending/running/succeeded/failed/cancelled.
  job_service.py L132 JobStatus(task.status.value) raises ValueError on
  "pending". Confirmed via StrEnum member check.

## GUI test capability

- Offscreen dialog test pattern exists: tests/runtime/test_settings_dialog.py
  (QT_QPA_PLATFORM=offscreen + QApplication + _wait_until/processEvents).
  JobCenterDialog action tests can follow it.

## Tooling

- Scripts: pdm run test (i18n-compile + run_pytest), pdm run check,
  pdm run smoke, pdm run package. Full check runs agent-skills lint+typecheck
  — any new module must pass ruff + strict mypy.

## Gating questions answered before implementation

- D1=B confirmed (unified job table). D3 ML permanent orphan confirmed
  deliberate. D4 actions approved. D5/D6 defaults approved.
- ML orphan + JobRow: at startup the scheduler leaves queued ML JobRows
  exactly as persisted and never auto-dispatches them; they stay visible as
  queued in the Jobs feed (today's behavior, preserved).
