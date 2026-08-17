# Impact Handshake LLM-RB — Retryable Transient Errors and Retry Backoff

**Status:** approved by Sir on 2026-08-16 (Layer 1 of the Judge-calibration
diagnosis). Product-side LLM-service change.

## Evidence Trigger

The five Judge calibration suites failed 14 of ~60 provider calls with
`provider_retry_count: 0` and ~0.3s latency, while the Judge's own
classifications were 45/46 correct. `_should_retry` only retries
`retryable=True` exceptions, and `providers._http_error` marks only
`{408,409,425,429,500,502,503,504}` as retryable; transient server/CDN 5xx
outside that set are raised without any retry, and retries have no backoff.

## Address and Object

- `src/xenix/services/llm/providers.py::_http_error` — broaden the retryable
  HTTP status set.
- `src/xenix/services/llm/service.py` — add `import time`, a
  `_retry_backoff` helper, and backoff in `_complete_with_retry` and
  `stream`.

## State Diff

- **From:** `retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504}`;
  retries are immediate.
- **To:** `retryable = exc.code >= 500 or exc.code in {408, 409, 425, 429}`
  (purely additive); a `time.sleep(min(2 ** (attempt_number - 1), 8.0))`
  backoff precedes each retry in both the complete and stream paths.

## Blast Radius

The whole LLM conversation/agent/benchmark call chain (subject and Judge). The
change is conservative: it only (a) retries transient 5xx it previously dropped
and (b) adds a bounded sleep before retries. Non-retryable 4xx (400/401/403/404)
and non-transient errors still fail immediately.

## Invariants

- Non-retryable client errors (4xx outside 408/409/425/429) still fail without
  retry.
- Retry counts, budget accounting, and `retry_callback` semantics are
  unchanged; only the retryable set and inter-attempt delay change.
- No streaming, message, tool, or settings-schema change.

## Verification

- `pdm run test -q`; `pdm run check`; `pdm run smoke`;
  `pdm run benchmark-agent-harness-check -q`.
- Re-run the five Judge calibration suites with `kimi/kimi-k2.5`.

## Return-to-Discussion Triggers

- A retry would retry a non-transient 4xx, or the backoff would exceed a
  hard time budget.
