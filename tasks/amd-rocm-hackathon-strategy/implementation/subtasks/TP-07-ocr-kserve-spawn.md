# TP-07 — OCR Settings, KServe/PAGE, and Spawn Boundary

## Outcome

Add the capability-owned OCR provider catalog and ordinary KServe V2/PAGE client,
then carry a memory-only selected provider binding across the real parent/spawn
worker boundary without importing AMD in the worker.

## Owned Mutation

- add `src/xenix/services/ocr/settings.py` and
  `src/xenix/services/ocr/kserve_v2.py`;
- extend `src/xenix/services/ocr/composition.py`;
- modify `src/xenix/services/knowledge_import_service.py` and, after TP-06,
  `src/xenix/services/knowledge_import_worker.py`;
- add OCR settings, KServe provider, resource-bound, and spawn black-box tests.

## Ports and Sequence

- `LocalPaddleTarget | ManagedOcrProviderRef`; the managed ref has an opaque
  `manager_id` and no AMD type;
- typed user/managed-projection commands over TP-03;
- an app-scoped explicit provider registry whose Paddle/KServe built-ins need no
  AMD import or entry-point discovery;
- `OcrAttemptFactory.prepare()` returns a parent-owned attempt and frozen ordinary
  `OcrSpawnSpec`;
- parent holds the operation scope from before process creation through child
  exit/cancel/crash/timeout;
- child constructs Paddle or KServe client from the ordinary spec and never
  imports `xenix.services.amd`.

`OcrSpawnSpec` is extra-forbid, pickle-safe, redacted in representation, and never
written to durable import request/result/log state. Live token and endpoint travel
only through the multiprocessing handoff.

## Protocol

- KServe V2 health/metadata/inference;
- Binary Tensor `BYTES[1]` PNG input and PAGE XML `BYTES[1]` output;
- exact TP-02 PAGE hierarchy, coordinate, resource, authentication, timeout, and
  typed failure contract;
- hostile XML parsing has external entity/network access disabled.

## Acceptance

- parent permit spans real child lifetime and releases on every terminal path;
- child crash/disconnect cannot cause transparent retry or partial canonical
  publication;
- legal no-text remains a successful empty result;
- settings, result, log, exception, and diagnostic scans find no token/live URL;
- fixed PNG/PAGE XSD, wrong model/content type, unauthenticated, oversized, and
  hostile payload cases pass.
- a removed/unknown manager is typed unavailable before spawn, with no fallback or
  selection mutation; ordinary Paddle/KServe spawn remains functional without AMD.

## Verification

- focused OCR settings/KServe/spawn tests using spawn, not only inline runner;
- official PAGE XSD validation;
- `pdm run check`.
