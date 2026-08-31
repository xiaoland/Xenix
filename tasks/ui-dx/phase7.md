# Phase 7 — Agent-safe full-app profiles

## Status

Foundation implemented and locally verified: typed profile resolution, a
home-scoped single-instance mutex, launcher flags, run manifest, and the four
composition-based remote denials (update auto-check, remote OTLP, remote ML
worker admission, SSH worker setup) plus live LLM/embedding denial. The launcher
removes an isolated home on successful exit and preserves bounded/redacted
failure evidence outside the home.

## Frozen flag matrix

Resolution happens in `src/xenix/runtime_profile.py` before application import.

| Flags | Profile | Home | Capabilities | Mutex |
| --- | --- | --- | --- | --- |
| (none) | production | `XENIX_APP_HOME` if set, else platform default | all | home fingerprint |
| `--smoke-test` | production | same as none (no isolation) | all | home fingerprint |
| `--agent-dev` | agent-dev | unique fresh temp home | all remote denied | home fingerprint |
| `--ephemeral` | ephemeral | unique fresh temp home | all remote denied | home fingerprint |
| `--agent-dev --ephemeral` | ephemeral | unique fresh temp home | all remote denied | home fingerprint |

Priority rules:

1. A profile flag (`--agent-dev` or `--ephemeral`) always isolates the home; it
   overrides an inherited `XENIX_APP_HOME` because isolation is the point of the
   profile. `--ephemeral` names the profile when both flags are present.
2. Without a profile flag, the existing `XENIX_APP_HOME` override wins, else the
   platform default. `--smoke-test` selects startup-validation behavior only and
   does not by itself isolate the home (unchanged existing behavior).
3. The single-instance mutex is always the SHA-256 fingerprint of the normalized
   home. Same home -> same mutex; different homes -> independent. A plain smoke
   run against the real home now contends with a running production GUI instead
   of using a separate mutex name.
4. Abnormal exit keeps the profile fixed: the home and capabilities are resolved
   first and never renegotiated during recovery. Cleanup of an isolated home on
   successful exit is the launcher's responsibility.

## Implemented

- `src/xenix/runtime_profile.py`: `RuntimeProfile`, `Capabilities`,
  `RuntimeProfileContext`, `resolve_runtime_profile`, mutex fingerprint, and run
  manifest. Pure, strict-mypy, unit-tested.
- `src/xenix/main.py`: `--agent-dev` and `--ephemeral` flags; profile resolution;
  isolated-home override; home-scoped mutex; run manifest on stderr; bounded
  redacted `failure.json` outside the home on abnormal exit; home removal on
  successful exit.
- `src/xenix/app.py`: `run()`/`build_main_window()` accept `Capabilities`.
  Update service and its auto-check controller are omitted when update is denied.
  `setup_observability` receives `allow_remote_export`. `LLMService` and
  `build_headless_agent_services` receive `live_llm`; the Settings factory
  receives `ssh_worker_setup`.
- `src/xenix/observability.py`: `setup_observability(..., allow_remote_export=...)`
  constructs no exporters when remote export is denied.
- `src/xenix/services/llm/service.py`: `LLMService(..., allow_live=...)` denies
  `complete()`/`stream()` with `error_code="live_llm_denied"` and reports no
  thread-title/guard model when denied.
- `src/xenix/services/embedding_service.py`:
  `OpenAICompatibleEmbeddingService(..., allow_live=...)` reports embedding as
  unavailable when denied, so knowledge recovery skips the remote semantic index.
- `src/xenix/services/ml/worker_pool.py` / `ml_task_service.py` /
  `agent/composition.py`: `allow_remote_workers` denies SSH worker admission at
  the pool seam, so `SshMLWorkerRunner` (and its ssh/scp subprocesses) is never
  selected.
- `src/xenix/ui/settings_dialog.py`: `ssh_worker_setup=False` disables the SSH
  worker setup button and refuses to construct `SshWorkerSetupWizard`, closing
  the `~/.ssh/config` write and ssh/scp side-effect entry.

## Remaining

- **Subprocess network-denial acceptance:** the composition-level denials close
  the only subprocess-spawning network paths (SSH runner, SSH setup), but an
  end-to-end probe that asserts no child process reaches the network has not yet
  been run. This belongs with Phase 8 integration acceptance.
- **Real failure-bundle inspection:** `failure.json` is emitted on abnormal exit;
  a deliberate isolated-run failure should be inspected once in CI/local before
  the task is closed.

## Verification so far

- `tests/test_runtime_profile.py`: mutex scoping, production home resolution,
  agent-dev isolation, flag composition, and the run manifest.
- `tests/test_agent_safe_capabilities.py`: remote-worker admission denial, live
  LLM `complete`/`stream`/title/guard denial, and live embedding denial.
- `tests/test_launcher_evidence.py`: evidence redaction/bounding, isolated-home
  removal, and the bounded redacted `failure.json` writer.
- `tests/ui/test_settings_dialog.py`: SSH worker setup button disabled and the
  wizard not constructed when `ssh_worker_setup=False`.
- `pdm run typecheck`: 42 strict modules pass; `pdm run lint`: pass; `pdm run
  check`: pass.
- Focused UI portfolio passes 61/61. An isolated `--agent-dev --smoke-test` run
  completed successfully and left no `xenix-agent-dev-*` home behind.
