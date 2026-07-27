# Slice 03 Phase H — Production PPTX Import Failure

**Observed:** 2026-07-23
**Posture:** read-only runtime diagnosis followed by approved structural repair
**Runtime mutation:** none; the user database, CAS, logs, and source file were not
changed

## Reproduction Identity

- source: `2026半年度工作汇报（品牌营销）.pptx`
- source size: `53,093,313` bytes
- source SHA-256:
  `effa60d7951eac3b88e260c9e09e9e3e46d4a0b197650d8222950af92d89c939`
- import ID: `67a1905431784f2c9d4a237318b9d6f6`
- source Artifact ID: `ead1e0c6190248a8afda6b96afdfaf98`
- planned Document ID: `075a21ab4e1444c9912920d24a3b3a0a`
- Import worker PID: `16236`

## Runtime Evidence

The original file and app-owned source snapshot have the same size and SHA-256.
The snapshot is a readable OOXML package with 231 entries, 50 slides, and
`ppt/presentation.xml`. The failure is not source mutation, snapshot corruption,
format admission, probing, database publication, derivation, or indexing.

The task log records this UTC sequence:

```text
03:44:23.249 import_queued
03:44:23.376 source_snapshot_started
03:44:23.646 source_snapshot_published
03:44:23.652 source_probed
03:44:26.685 worker_started
03:44:26.751 normalization_started
03:44:26.871 routing_started
03:44:26.876 parsing_started
03:44:30.360 worker_failed
03:44:31.361 knowledge_docling_parse_failed
```

SQLite ends with `status=failed`, `phase=failed`,
`error_code=knowledge_docling_parse_failed`, and no Document, Canonical Generation,
Derivation, envelope hash, content hash, or canonical path. Direct Docling conversion
and JSON serialization of the same CAS snapshot succeed in the current environment;
the serialized DoclingDocument is about 86.7 MB.

## Diagnosed Boundary

Production uses two process boundaries:

```text
KnowledgeImportService thread
  -> spawned Knowledge Import worker + Windows Job Object
       -> nested Docling subprocess
            -> large DoclingDocument JSON
```

Phase G's named-fixture public-import exercise injected a normalizer and therefore
selected `InlineKnowledgeImportWorkerRunner`; it did not exercise the production
spawn. Packaged smoke directly exercises the frozen Docling worker, while its spawned
Import exercise uses TXT. No test covered the full topology above with PPTX.

The exact leaf exception is not recoverable from current persisted evidence:

- the nested Docling process sends stdout and stderr to `DEVNULL`;
- its entrypoint catches every exception and returns only exit code `1`;
- the parent folds non-zero exit, missing output, and invalid JSON into
  `knowledge_docling_parse_failed`;
- the outer worker persists only the safe error code and retryability.

The evidence therefore supports an architectural diagnosis, not an invented Docling
exception: a redundant and untested nested process boundary failed, and its outcome
contract destroyed the information required to distinguish the leaf cause.

## Phase H Repair Direction

1. Make the spawned Import worker the single process-isolation boundary for Docling
   work. The parent runner supervises cancellation and a bounded operation timeout;
   the worker executes Docling directly and publishes only through the existing
   canonical/result protocol.
2. Model structured, content-free failure stages so launch, conversion,
   serialization, output validation, timeout, and process crash remain
   distinguishable in the task log without exposing document content.
3. Add a production-topology regression using the real spawned runner and the named
   PPTX. Package acceptance must exercise that same topology, not only the nested
   helper in isolation.
4. Complete adjacent PPT/PPTX error-copy coverage and rename the Workspace-local
   user-facing `Knowledge tasks` / `Knowledge Task Queue` labels to `Task queue`.

Phase H does not change SQLite schema, canonical IR, format registry, derivation,
retrieval, Tool contracts, OCR runtime, or multimodal scope.

## Implemented Resolution

- `knowledge_docling.py` is a direct Docling adapter, not an executable worker.
  `knowledge_pipeline.py` calls it inside the already spawned Import worker. The
  nested process, discarded output streams, and approximately 86.7 MB intermediate
  JSON transfer are gone.
- The parent remains the only SQLite and publication authority. Its worker runner
  owns launch supervision, a 15-minute operation bound, cancellation, Job Object
  cleanup, result validation, and publication eligibility.
- Default service composition always selects the spawned runner. Inline execution is
  now an explicit test seam rather than an implicit side effect of injecting a
  normalizer or OCR double; only tests whose actual subject is an injected boundary
  may select it.
- Worker result schema v2 carries only `outcome`, `failure_stage`, and a safe
  `diagnostic_code` in addition to the canonical success payload. Parent-owned
  launch, timeout, process-crash, and invalid-result failures remain distinct.
- Package smoke now imports both generated DOCX and PPTX through the frozen app's
  default spawned runner, then derives and retrieves the presentation text. It no
  longer treats direct parser-helper execution as production-topology evidence.
- The Workspace button and modeless dialog use `Task queue` / `任务队列`; internal
  `KnowledgeTask*` names and separate import/derivation/index authorities are
  unchanged.

## Acceptance

- affected integration cohort: `92 passed, 1 skipped`;
- complete repository gate: `616 passed, 3 skipped`, followed by the app-entry
  session at `58 passed`;
- named 53,093,313-byte PPTX: default spawned
  Import→Canonical→Derivation→keyword lookup passes and retrieves `菜单瘦身`;
- fresh package: `dist/xenix/xenix.exe`, 100,429,503 bytes, built in 1,093.4 seconds;
- frozen packaged smoke: passes in 133.5 seconds with spawned DOCX and PPTX imports,
  PPTX derivation, and keyword retrieval;
- UI/i18n: English/Chinese `Task queue`, `Task Failed`, and `Task Details` survive
  runtime `LanguageChange`;
- static checks and `git diff --check`: pass.

The full-suite rerun also exposed and closed a test-topology defect: implicit Inline
selection loaded Docling into the pytest/Qt process and triggered native abort/access
violations. Making runner selection explicit and replacing the fake-OCR test's
unrelated real Docling call with a light content-IR shell lets the complete suite run
in one process while real Docling remains covered by spawned source/package tests.

Phase H is locally accepted. No user database/CAS mutation, commit, or publication
was performed.
