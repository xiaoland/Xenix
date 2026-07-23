# Slice 03 Phase I — Runtime Distribution and Vector Failure Truth

**Date:** 2026-07-23
**State:** locally accepted; final coupled Slice 03 review pending

## Delivered boundary

OCR deployment now depends on one `PaddleOcrBundleSource` contract:

```text
development: generated catalog + exact local archive --\
                                                       > deployment state machine
frozen build: embedded catalog + immutable release ---/
  -> cache -> size/SHA -> safe extract -> member manifest
  -> native self-test -> immutable generation -> atomic active pointer
```

Transport selection occurs at application composition. It does not branch or weaken
verification and activation. An already active generation remains usable without an
install source. Setup converts only typed `knowledge_ocr_*` failures into
content-free status; Knowledge Settings presents unavailable/download/integrity/
self-test guidance without raw exceptions.

Embedding Batch size remains a generic OpenAI-compatible setting and now defaults to
20. Index rebuilds may preserve bounded `embedding_*` leaf errors in the existing
task code/summary fields. Provider response bodies, request text, vectors, API keys,
and arbitrary exceptions remain excluded. Interactive lookup retains its existing
Knowledge-domain availability contract.

## Real runtime evidence

The source launcher selected `LocalPaddleOcrBundleSource` from the generated
`dist/knowledge-ocr` catalog and 205,199,992-byte archive. The real deployment
reached:

```text
state: ready
runtime: paddle-inference-3.3.0-paddleocr-3.7.0-win-x64
model pack: pp-ocrv6-medium-zh-en-1
generation:
  ocr-ed0410220efec5cec8a61c70a2b1dc04
```

The resolved native executable plus detection and recognition model directories all
exist. Deployment performed the same archive/member/self-test/activation path used
by release sources.

The first fresh frozen smoke found one additional delivery defect. Native initialize
reported no `.pdiparams` after the bundle had passed setup because setup self-tested
the short staging location, then moved the same tree beneath an overlong descriptive
generation directory. The Python `knowledge_ocr_response_invalid` was merely EOF
after that native failure. Generation directory names are now 36-character content
addresses over the complete runtime/model/archive identity, and self-test executes
on the final generation path before `active.json` is written. The rebuilt frozen
application passes the same native image route.

The configured 67-Unit corpus rebuilt as `20+20+20+7`, published one 1024-dimensional
generation, reached vector `ready`, and passed explicit semantic lookup. Tests also
prove that a provider HTTP rejection persists only its safe code/status/actionable
summary.

## Verification

- Final Phase I focused cohort: `53 passed, 1 skipped`.
- OCR deployment/source/final-path tests after repair: `13 passed`.
- Real source spawned native-OCR acceptance: `1 passed` in 94.95 seconds.
- Translation compilation: English and Chinese each `375 finished, 0 unfinished`.
- Real source-mode install/status/open-runtime plus `BOARDING` recognition: passed
  with generation `ocr-ed0410220efec5cec8a61c70a2b1dc04`.
- Static gate: passed.
- Full repository final run: `623 passed, 3 skipped`; the separate app-entry session
  passed `58` tests. An earlier run's only failure was an unrelated ML bulk-tuning
  60-second wait; that case passed alone and in the final complete rerun.
- Fresh frozen package after the final-path repair: passed.
- Rebuilt packaged smoke: passed in 120.6 seconds, including spawned DOCX/PPTX and
  real native image OCR through canonical derivation and lookup.

Passing Phase I does not close Slice 03: the promised Import/Storage/Tool/UI/OCR/
runtime/release/index cross-review remains mandatory.
