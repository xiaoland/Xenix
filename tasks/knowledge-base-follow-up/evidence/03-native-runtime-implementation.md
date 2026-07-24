# Slice 03 Evidence — Native OCR and Operations Implementation

**Run:** 2026-07-22 through 2026-07-23
**State:** Phases B–F accepted; final task closed by Sir on 2026-07-24
**Platform:** Windows x64, Visual Studio Build Tools 2022

## Native component

The production build path compiled the pinned PaddleOCR/Paddle Inference worker from
a clean work root, applied the reviewed optional-`resize_long` compatibility patch,
and staged the manifest-owned DLL/model/license closure. The build uses a persistent
length-delimited JSON protocol and initializes the model once for multiple requests.

The deterministic output recorded by `runtime_catalog.json` is:

| Field | Value |
| --- | --- |
| Artifact | `xenix-knowledge-ocr-win-x64-paddle-inference-3.3.0-paddleocr-3.7.0-win-x64.zip` |
| Bytes | `205,199,992` |
| SHA-256 | `968410e7777e89ae1361aa6587962334b4f536228a2988a461f41b2b5b35aa21` |
| Runtime ID | `paddle-inference-3.3.0-paddleocr-3.7.0-win-x64` |
| Model pack | `pp-ocrv6-medium-zh-en-1` |
| Protocol | `2` |

Build verification completed `version`, initialization, self-test, ten consecutive
golden recognitions in one session, and clean shutdown. The archive contains only
the 23 runtime-manifest members plus `runtime.json`; exact model paths and a pinned
MSVC OpenMP redistributable are part of the closure.

## Real deployment exercise

An isolated application home installed the generated archive through a local HTTP
origin using the production deployment service. The observed phase sequence was:

```text
downloading_bundle -> extracting_bundle -> verifying_bundle
-> self_testing -> activating_bundle -> ready
```

The service then reopened the activated generation offline and recognized the
accepted boarding-pass image with 34 regions, including Chinese and English text.
No Python, pip, PATH mutation, `.paddlex`, or upstream model download participated.

## Application topology realized

- one native OCR session is lazily owned by one spawned import attempt and reused
  across its OCR-routed pages;
- the parent import service retains all SQLite/canonical publication authority;
- schema v23 publishes projection version, bounded content fingerprint, and Unit
  count, invalidates v2 random Unit identities, and re-derives deterministic Units;
- Workspace construction is lightweight and applies only the latest asynchronous
  snapshot;
- Knowledge Task Queue asynchronously folds import/initial derivation while showing
  independent content preparation and index builds with owner-supported actions;
- global OCR/keyword/text-vector state is rendered in the muted footer below the
  logical-document list; and
- release catalog, manifest, upload, publication, and packaged smoke paths use the
  native artifact contract. Packaged smoke accepts only the already built catalog
  artifact, seeds it into an isolated download cache, and makes the frozen app run
  the production verify/extract/self-test/activate path without network access.

The measured cold Workspace path imports its lightweight module in about 213 ms and
constructs/shows the shell in about 134 ms on the development machine (about 347 ms
combined). The index-rebuild dialog's semantic-index dependency is loaded only when
that separate action is opened. The Workspace cold path imports neither the Docling
pipeline nor the index service.

## Phase F convergence evidence

- All supported formats now travel through one validated capability graph binding
  probe, normalizer, route-planner, and parser providers. Generated PDF fixtures
  cover born-digital, scanned, mixed, and suspect OCR-layer routes; broken-font
  evidence is classified suspect, while generic complex-layout understanding remains
  explicitly outside the claim.
- Retrieval projection v3 derives Unit IDs from document/canonical generation/
  projection version/ordinal. A vector build consumes one frozen SQLite metadata+
  Unit snapshot and rechecks its identity before generation publication and index
  task success. The reproduced same-count replacement no longer lets fast status
  disagree with strict semantic search.
- Native OCR READY now depends on a 24-hour verification record produced by full
  manifest-member hashing and native self-test. Missing/stale evidence reports
  checking and refreshes in a background task. Canonical pipeline provenance records
  the exact generation, runtime, model pack, engine/version, protocol, and manifest
  hash used by OCR.
- Every spawned Import worker arms a Windows kill-on-close Job Object before task
  execution. A real stubborn grandchild test proves forced cancellation converges
  the entire worker tree.
- Source and newly frozen packaged runs install the real 205,199,992-byte runtime,
  import the locked boarding-pass image through the independent worker, publish
  Canonical content, derive bounded Units, retrieve `BOARDING` through FTS lookup,
  and verify the recorded runtime generation.

## Verification status

- `pdm run check` passes with 368 finished translations in each locale.
- The complete source suite passes: 662 passed, 3 skipped, with only three existing
  scikit-learn warning messages.
- `pdm run package` produces the fresh 100,425,853-byte frozen executable and
  `pdm run smoke-package --timeout-seconds 300` passes in 96 seconds while running
  the real OCR import-to-lookup chain offline.
- `pdm run smoke` passes the source application/data boundary.
- Fresh Velopack output and release manifest schema 2 pass. The manifest has two
  desktop artifacts, three update-feed artifacts, and exactly one
  `knowledge_ocr_runtime` with the catalog's bytes and SHA-256.
- The live `knowledge.rainy_season_restock` cell using `kimi/kimi-k2.6` and the
  independent Embedding profile completes with semantic pass and integrity true.
  Its oracle grades the Agent's final answer and exact derived Dataset, not Tool
  execution telemetry. The Phase F rerun persisted successfully in 64.22 seconds.
- Windows-native Chinese visual QA confirms the logical-document list, absent
  description, muted footer, unified task columns, and lack of displayed internal
  identifiers.

The only remaining Slice 03 closure gate is the final review with Sir across
Import, Storage, Tool, UI, OCR runtime, release, and index-generation boundaries.
The generated `dist/` bytes are local acceptance evidence only: no commit was
authorized, so their embedded build commit is the pre-change `HEAD`. They must not be
published; an authorized final commit requires a fresh release-candidate build.

## Phase G presentation import evidence

- Format registry v2 adds PPT/PPTX as complete capabilities rather than UI suffix
  exceptions. DOCX/PPTX share one parameterized OOXML safety verifier; DOC/PPT share
  one bounded LibreOffice conversion profile model with different targets.
- Generated direct PPTX, encrypted PPTX, OOXML spoof/path-safety, and real
  LibreOffice PPT→PPTX→Docling imports reach bounded lookup evidence.
- Workspace file picker and shell/list drag-and-drop converge on one ordered,
  deduplicated submission operation. The drop adapter owns no probe or enqueue
  authority.
- The exact 53,093,313-byte Chinese presentation under `tests/.mock-data` passes
  public Import→Canonical→Derivation→lookup and returns
  `先做“菜单瘦身”，再做“产品强化”`.
- The complete suite passes 669 tests with 3 skips. A fresh 100,430,292-byte frozen
  executable and 140.6-second packaged smoke pass; the marker proves the frozen
  Docling worker parsed PPTX as well as DOCX.
