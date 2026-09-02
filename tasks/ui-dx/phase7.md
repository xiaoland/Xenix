# Phase 7 — Isolated runtime profile

## Status

Implemented and locally verified: typed profile resolution, a home-scoped
single-instance mutex, the `--isolated` launcher flag, a run manifest, and the
success/failure home handling. The launcher removes an isolated home on
successful exit and preserves bounded/redacted failure evidence outside the
home.

The original Phase 7 design also bundled a per-edge `Capabilities` surface
(update auto-check, remote OTLP, remote ML worker admission, SSH worker setup,
and live LLM/embedding denial). That denial surface was later removed: it
encoded a deterministic/offline verification concern inside the launcher, was
not driven by any CI or script, and weakened the ability to debug real remote
paths under an isolated home. The deterministic/offline verification need is
already served separately by `scripts/ui_lab`, `CapturePolicy`, and the pytest
fixtures, which construct synthetic views without touching the launcher flag.

## Frozen flag matrix

Resolution happens in `src/xenix/runtime_profile.py` before application import.

| Flags | Profile | Home | Mutex |
| --- | --- | --- | --- |
| (none) | production | `XENIX_APP_HOME` if set, else platform default | home fingerprint |
| `--smoke-test` | production | same as none (no isolation) | home fingerprint |
| `--isolated` | isolated | unique fresh temp home | home fingerprint |

Priority rules:

1. `--isolated` always isolates the home; it overrides an inherited
   `XENIX_APP_HOME` because isolation is the point of the flag.
2. Without `--isolated`, the existing `XENIX_APP_HOME` override wins, else the
   platform default. `--smoke-test` selects startup-validation behavior only and
   does not by itself isolate the home.
3. The single-instance mutex is always the SHA-256 fingerprint of the normalized
   home. Same home -> same mutex; different homes -> independent. A plain smoke
   run against the real home contends with a running production GUI instead of
   using a separate mutex name.
4. Abnormal exit keeps the profile fixed: the home is resolved first and never
   renegotiated during recovery. Cleanup of an isolated home on successful exit
   is the launcher's responsibility.

## Implemented

- `src/xenix/runtime_profile.py`: `RuntimeProfile` (`production` / `isolated`),
  `RuntimeProfileContext`, `resolve_runtime_profile`, `is_isolated_home_path`,
  mutex fingerprint, and run manifest. Pure, strict-mypy, unit-tested.
- `src/xenix/main.py`: `--isolated` flag; profile resolution; isolated-home
  override; home-scoped mutex; run manifest on stderr; bounded redacted
  `failure.json` outside the home on abnormal exit; home removal on successful
  exit.

## Remaining

- **Isolated smoke probe:** run `--isolated --smoke-test` once and confirm it
  leaves no `xenix-isolated-*` home behind.

## Verification so far

- `tests/test_runtime_profile.py`: mutex scoping, production home resolution,
  isolated-home resolution, and the run manifest.
- `tests/test_launcher_evidence.py`: evidence redaction/bounding, isolated-home
  removal, and the bounded redacted `failure.json` writer.
- `pdm run typecheck`: strict modules pass; `pdm run lint`: pass; `pdm run
  check`: pass.