# TP-06 — Engine-neutral OCR Extraction

## Outcome

Remove Paddle from Knowledge routing, result, status, provenance, log, and
production spawn semantics while preserving the verified Paddle feature as the
first OCR adapter.

## Owned Mutation

- add `src/xenix/services/ocr/contracts.py` and
  `src/xenix/services/ocr/composition.py`;
- modify `src/xenix/services/paddle_ocr_service.py`;
- modify `src/xenix/services/knowledge_pipeline.py` and
  `src/xenix/services/knowledge_import_worker.py`;
- modify Knowledge workspace service/UI only where persisted status/provenance
  vocabulary requires it;
- extend Knowledge OCR runtime, import authority, provenance, and packaged-smoke
  tests.

TP-07 follows this task; the two tasks may not edit the pipeline/worker in parallel.

## Extraction

- `OcrService`, `OcrSession`, `OcrRuntimeDescriptor`, normalized result, and typed
  failure contracts;
- semantic route IDs such as `ocr-page`, `ocr-hybrid-page`, and `ocr-image`;
- provider-derived log/provenance/status instead of Paddle constants;
- explicit spawn-safe OCR composition for the existing Paddle target;
- legal empty OCR result distinct from provider/protocol failure.
- the default Paddle/static composition is complete with the AMD package absent
  and performs no ambient provider discovery.

No KServe, PAGE network client, managed reference, or AMD import is added.

## Acceptance

- no `startswith("paddleocr-")` or Paddle service name controls Knowledge routing;
- the production spawned worker still performs real Paddle OCR;
- existing install/repair/session/provenance/canonical publication behavior passes;
- malformed/provider failures are no longer silently equivalent to no text;
- an AMD-module-absent spawned-worker probe performs the ordinary Paddle path;
- ADR 0009 and packaged Paddle smoke remain valid.

## Verification

- focused Knowledge OCR/import tests;
- `pdm run smoke` OCR slice where available;
- `pdm run check`.
