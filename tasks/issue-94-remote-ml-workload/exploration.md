# Issue 94 Remote ML Workload Exploration

## Objective & Hypothesis

- Objective: Design remote ML workload execution for training, follow-up evaluation, and model apply while preserving Xenix Native's local service, local metadata, and local artifact authority.
- Hypothesis: A configurable SSH-backed `MLWorkerRunner` can move task execution to remote Python environments without introducing a remote API, separate remote client, or remote artifact authority.

## Prompt

- GitHub issue: https://github.com/xiaoland/Xenix/issues/94
- User-facing goal: support running ML workloads remotely with as little configuration as possible for non-technical users.
- Initial requirements from the issue:
  - Remote Python environment.
  - Dataset and trained model are present on the remote target during execution.
  - Model apply artifacts are downloaded back after completion.
  - No independent remote client.
  - Minimal configuration.

## Guardrails Touched

- `docs/10-prd/product-scope.md`: Native scope currently retains local artifacts and removes remote ML backend deployment.
- `docs/20-product-tdd/runtime-boundaries.md`: UI talks to services; services own workflow semantics; ML adapters execute native model work.
- `docs/20-product-tdd/ml-task-lifecycle.md`: `MLTask` identity, status transitions, task directories, logs, and artifact result contracts.
- `docs/20-product-tdd/storage-ownership.md`: SQLite stores metadata; filesystem stores dataset/model/apply bytes and user-openable artifacts.
- `docs/20-product-tdd/artifact-links.md`: `ArtifactService` remains the authority for local artifact links.
- `docs/20-product-tdd/adr/0004-native-architecture-separate-from-web.md`: Reintroducing remote APIs or deployment-style boundaries requires a new ADR.
- `src/xenix/services/ml/AGENTS.md`: `MLTaskService` owns task lifecycle; `MLWorkerRunner` is only a process helper.

## Current Facts

- Confirmed decision: the default remote target type is SSH.
- Confirmed decision: multiple SSH instances should be configurable.
- Confirmed decision: local artifacts remain the final authority; remote storage is always execution and cache only.
- Confirmed decision: credentials may stay outside Xenix, but Xenix should provide a setup wizard because the audience is non-technical.
- Current local execution boundary is `MLTaskService -> MLWorkerRunner.run(entrypoint, task_dir, cancel_requested=...)`.
- Current task working directory shape is `artifacts/ml-tasks/<ml-task-id>/` with `request.json`, `result.json`, `logs.jsonl`, `input/`, `output/`, and `models/`.
- Current task finalization expects worker result paths to be local filesystem paths before canonical model/apply artifact registration.
- Training can trigger follow-up evaluation, so remote execution should handle `fit`, `hyperparameter_tuning`, `evaluate`, and `apply` even if the product phrase says training and inference.

## Unknowns

- Whether the first implementation should include the full setup wizard UI or land a service/config foundation first.
- How the wizard should verify a target: SSH connectivity only, Python import smoke, package version checks, writable remote cache root, or a small end-to-end task.
- Whether Xenix should generate remote bootstrap commands/scripts, or only display copyable commands for the user to run.
- Whether remote dependency installation is in scope for the wizard, or the wizard only validates an existing environment.
- How remote target selection should work: global default only, per-thread, per-task, or automatic fallback.
- How much remote cache state should be inspectable and cleanable from Xenix.
- Whether cancellation should terminate the remote process reliably in v1 or mark the local task cancelled and best-effort kill the remote command.

## Constraints Observed

- Do not introduce a remote HTTP backend or long-running remote service for v1.
- Do not introduce a standalone remote client product.
- Do not let UI construct remote or local artifact paths directly.
- Do not let remote paths become user-facing artifact authority.
- Do not add ML task statuses unless the lifecycle contract is updated.
- Keep provider/tool-facing model contracts stable: `model.train`, `model.hyper_train`, `model.apply`, and `model.task.query` should continue using existing payload semantics.
- Keep credentials out of normal artifact/task payloads and logs.
- Durable docs updates are part of implementation, not optional follow-up. Any slice that changes worker pool semantics, remote execution boundaries, setup UX, runtime config, concurrency, task lifecycle behavior, storage ownership, or operations guidance must update the governing docs in the same slice.

## Candidate Paths

1. SSH runner foundation first.
   - Add `LocalMLWorkerRunner` and `SshMLWorkerRunner`.
   - Add ML execution settings with multiple SSH targets.
   - Provide a config-file-first path and tests.
   - Defer wizard UI.
   - Risk: does not satisfy the non-technical setup requirement early enough.

2. Wizard plus SSH runner thin slice.
   - Add ML execution settings service.
   - Add Settings entry for ML execution targets and a guided SSH setup/test flow.
   - Add a minimal `SshMLWorkerRunner` that can run one real ML task remotely.
   - Risk: crosses service, UI, i18n, runtime docs, and execution boundaries in one slice.

3. Wizard-only discovery/prototype first.
   - Build the setup wizard and target verification without remote task execution.
   - Risk: user-visible setup may get ahead of actual workload capability.

## Proposed Direction

- Use path 2, but split it into small execution slices:
  1. Durable contract update: PRD/TDD/ADR text that remote SSH runner is an execution adapter, not remote backend deployment.
  2. Settings service and config model for multiple SSH targets.
  3. Setup wizard target validation path.
  4. `SshMLWorkerRunner` with staging, path rewriting, remote command execution, log/result download, and local result path rewriting.
  5. Cache and cleanup refinements after the first end-to-end proof.

## Discussion Sync

- Setup wizard should exist because the product serves non-technical users, even if Xenix does not store SSH credentials.
- Confirmed credential boundary for v1: support key/agent-based SSH only. Xenix may store target names, host/user/port, remote root, Python command, and identity-file path references, but not passwords or private-key material.
- Confirmed setup boundary: the wizard may write `~/.ssh/config`, but Xenix-managed blocks must be explicitly commented and use a reserved naming style such as `xenix.*`.
- Confirmed remote environment boundary: the wizard should include remote environment setup, not only validation.
- Preferred transport implementation for v1: invoke OpenSSH-family commands as subprocesses instead of adding a Python SSH stack. This preserves user SSH config, agent, ProxyJump, identity selection, and platform behavior.
- Multiple execution targets should be modeled as a worker pool. The pool can include the local machine and SSH workers.
- Confirmed configuration model: the worker pool is configurable, and each worker is individually configurable.
- Confirmed UX model: remote SSH workers are configured through a setup wizard that guides connection, SSH config, remote environment setup, and validation.
- There is no explicit user-facing default worker in v1. The scheduler automatically chooses an available or low-load worker. No failed retry or failover behavior is included in v1.
- Agent tools must not expose worker selection. `model.train`, `model.hyper_train`, and `model.apply` remain workload requests, not placement requests.
- A task may record which worker was selected in metadata for diagnosis, but the worker does not become artifact authority.
- V1 remote target assumption: POSIX-like SSH server with Python 3.12+ and project ML dependencies available.
- Remote code execution needs a versioned worker bundle or installed package contract. The bundle is preferred because it keeps "no independent remote client": Xenix uploads execution code/cache as task material instead of asking users to install and run a separate client app.
- The wizard should verify, at minimum:
  - local `ssh`/transfer command availability,
  - SSH connectivity,
  - writable remote root,
  - remote Python version,
  - remote environment setup result,
  - required Python imports,
  - upload/download round trip,
  - optional tiny worker smoke command.
- Confirmed implementation rule: durable docs updates belong to the implementation work itself. They should not be deferred to a separate cleanup unless the slice is purely exploratory and makes no durable behavior change.

## Candidate Target Config Shape

- `schema_version`
- `pool`
  - `enabled`
  - `selection_policy`
  - `max_concurrent_tasks`
  - `local_worker_enabled`
- `workers[]`
  - `id`
  - `display_name`
  - `kind`: `local` or `ssh`
  - `enabled`
  - `weight`
  - `max_concurrent_tasks`
  - `capabilities`
  - `host`
  - `user`
  - `port`
  - `ssh_alias`
  - `identity_file_path`
  - `remote_root`
  - `python_command`
  - `setup_state`
  - `last_validation`

## Candidate Pool Selection Rules

- Filter to enabled workers that pass their latest validation or can be cheaply revalidated.
- Prefer an idle local worker for small workloads only if remote setup is absent or remote workers are unavailable.
- For v1, use a simple deterministic score rather than a distributed scheduler:
  - current in-process active task count,
  - last validation freshness,
  - optional remote load probe if cheap,
  - local/remote preference from settings if later needed.
- If the selected worker fails during execution, the task fails normally. No automatic retry, failover, or duplicate execution in v1.

## Verification Anchors

- Unit tests for ML execution settings load/save/default target validation.
- Contract tests proving `MLTaskService` status transitions are unchanged under a fake SSH runner.
- Runner tests proving request path rewriting and result path rewriting for dataset, trained model, holdout, model output, and apply output paths.
- Integration test using a local fake SSH transport or loopback runner to execute a tiny task with remote-shaped staging.
- UI tests for setup wizard validation states and translated user-visible strings if the wizard lands in the same slice.
- Existing ML lifecycle tests remain passing, especially `tests/test_ml_execution.py` and Agent tool async behavior tests.

## Implementation Notes

- 2026-05-23: User confirmed full issue implementation can proceed in one workstream, split into 2-3 commits if useful.
- Implementation must include durable docs updates in the same slice as behavior changes.
- Keep SQLite schema unchanged for v1; worker pool settings are local JSON config.
- Full implementation should add the configurable worker pool, SSH setup wizard, remote environment setup, SSH runner staging/execution/download/path rewrite, tests, translations, and docs.

## Smallest Confirmation Needed

- Confirmed: implementation should complete the full issue rather than stop at a config-backed foundation.
- Confirmed: wizard may write or update clearly marked `xenix.*` OpenSSH config blocks.
- Confirmed: v1 requires key/agent-based SSH and does not store passwords, passphrases, or private-key material.
- Confirmed: wizard should perform remote environment setup, not only validate a pre-created environment.

## Promotion Candidate Truths

- Remote ML execution is an ML execution adapter behind local services, not a remote backend deployment.
- SSH is the first and default remote execution transport.
- Local SQLite metadata and local service-managed artifacts remain the final product authority.
- Remote files are execution/cache state and can be recreated or cleaned without changing local artifact truth.

## Implemented Surface

- Added `MLWorkerSettingsService` and `config/ml_workers.json` as the v1 worker pool configuration owner.
- Added a local/SSH worker pool behind `MLTaskService`; Agent tool payloads remain placement-agnostic.
- Added SSH task staging, remote worker bundle upload, remote command execution, result/log/output/model download, and remote-to-local result path rewriting.
- Added a Settings SSH setup wizard that writes only clearly marked `Host xenix.*` OpenSSH config blocks, performs key/agent-based SSH setup, creates a remote virtual environment, installs required ML dependencies, and runs validation/smoke checks.
- Added package data for the worker source bundle so packaged builds can upload the remote execution code without requiring a separate remote client.
- Updated product, product TDD, unit TDD, deployment docs, ADR index, and ML service local guidance to make remote workers execution/cache adapters rather than artifact authorities.

## Verification Run

- `python -m compileall src tests`: passed.
- `pdm run pytest tests/test_ml_workers.py -q`: passed, including worker settings persistence, SSH config block replacement, direct-host setup behavior, pool selection/concurrency, path rewrite/download behavior, and wizard save boundary.
- `pdm run pytest tests/test_i18n.py tests/test_main.py -q`: passed.
- `pdm run pytest tests/test_ml_execution.py tests/test_agent_harness_first_slice.py tests/test_services.py -q`: passed.
- `pdm run pytest -q`: passed, 156 tests.
- `pdm run check`: passed.
- `pdm run smoke`: passed.
- `git diff --check`: passed.

## Remaining External Proof

- The OpenSSH path is covered by fake SSH transport and setup-service tests, but has not been exercised against a real remote host in this workspace.
