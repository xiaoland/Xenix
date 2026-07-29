# TP-14 — AMD OCR Adapter

## Outcome

Implement the OCR-owned attempt port that turns an exact AMD generation binding
into an ordinary ephemeral `OcrSpawnSpec` while the parent retains the generation
permit.

## Owned Mutation

- add `src/xenix/services/amd/adapters/ocr.py`;
- add `tests/test_amd_ocr_adapter.py`.

Do not import AMD from the OCR worker or KServe client, and do not edit deployment,
placement, or `app.py`.

## Behavior

- resolve selected `ManagedOcrProviderRef` to an exact session;
- acquire one permit/binding before spawn preparation;
- return only the ordinary TP-07 spec plus a parent-owned attempt context;
- keep permit until child exit/cancel/crash/timeout settles;
- never persist or log the live binding/token;
- disconnect fails the attempt and never falls back to Paddle/CPU/API.

## Acceptance

- real spawn fixture observes permit held through child lifetime;
- cancel, timeout, launch failure, crash, and normal exit each release once;
- worker imports contain no AMD dependency;
- token/URL scanners pass for request/result/log/error/diagnostics;
- two installations and stale/retired generations resolve/fail exactly.

## Verification

- `pdm run pytest --direct tests/test_amd_ocr_adapter.py`;
- focused TP-07 spawn tests;
- `pdm run check`.
