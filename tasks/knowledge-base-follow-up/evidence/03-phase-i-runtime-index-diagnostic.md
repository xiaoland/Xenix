# Slice 03 Phase I — Runtime and Index Failure Diagnosis

**Date:** 2026-07-23
**Scope:** read-only runtime, database, artifact, configuration, and source inspection
**Mutation:** none; API keys, document bodies, and provider response bodies were not
recorded

## Local PaddleOCR setup

The active app runs from `scripts/run_dev.py`. Its source package root does not
contain the generated `resources/knowledge_ocr/runtime_catalog.json`, and neither
`XENIX_KNOWLEDGE_OCR_CATALOG` nor `RELEASES_OSS_PUBLIC_URL` is configured.

The deployment state machine therefore stops before download:

```text
install
  -> catalog absent
  -> knowledge_ocr_catalog_unavailable
```

If only a catalog were supplied, artifact URL resolution would next stop at
`knowledge_ocr_download_unavailable`. No
`%LOCALAPPDATA%/Xenix/cache/knowledge-ocr` tree exists, which agrees with failure
before staging. The UI worker catches every exception and returns `None`, so the
settings dialog replaces the structured error with generic setup-failed copy and
the application log has no causal event.

This is not evidence of a broken Paddle worker. The generated archive
`dist/knowledge-ocr/xenix-knowledge-ocr-win-x64-paddle-inference-3.3.0-paddleocr-3.7.0-win-x64.zip`
is 205,199,992 bytes and its SHA-256/size match the adjacent runtime catalog. The
packaged-smoke field `paddle_native_deployment=true` is a capability marker;
`paddle_native_activation=false` confirms that smoke did not activate this archive.

## Text-vector rebuild

The active database passes `PRAGMA quick_check` and contains one current searchable
document:

- retrieval projection v3;
- 67 current/distinct Units, ordinals 0–66;
- 1,509 total characters; maximum Unit 377 characters;
- no empty or over-limit Unit.

The corpus-change task `c0822c976a964ca99edaf30b7a3b6d8d` was created at
2026-07-23 06:03:47.810979 UTC and failed about 0.632 seconds later. It records:

```text
index kinds: ["text_vector"]
status/phase: failed/failed
error code: knowledge_semantic_unavailable
profile fingerprint: null
corpus fingerprint: null
vector generation: null
```

There are no `knowledge_vector_generation` rows and no index/staging generation
directories. The failure therefore precedes LanceDB write and SQLite publication.

The configured generic OpenAI-compatible profile is enabled and has a key, endpoint,
model `qwen3.7-text-embedding`, provider-default dimensions, batch size 64, and a
120-second timeout. A single-input probe returns a finite 1024-dimensional vector.
Bounded batch probes against the same configured endpoint succeed through 20 inputs
and return `embedding_provider_http_error` with HTTP 400 at 21; this matches the
provider's documented 20-input limit. The 67-Unit rebuild currently sends 64 inputs
in its first request.

The persisted generic error is a second defect in the evidence boundary:
`KnowledgeSemanticService` converts every Embedding validation/provider error into
`KnowledgeSemanticUnavailable`; `KnowledgeIndexService` can then persist only
`knowledge_semantic_unavailable` and generic copy. The safe HTTP status and
Embedding error code are lost even though neither contains user content.

## Disposition

- KB-D36 is a confirmed deployment-source composition and observability gap.
- KB-D37 was a confirmed configuration/provider-limit mismatch plus an index-task
  error-projection gap; it was not LanceDB corruption.

## Embedding repair verification

Sir authorized a configurable Batch size with default 20. The existing settings UI
already owns and persists values from 1 through 2,048, so implementation changes the
single `EmbeddingSettings` default rather than introducing another setting.

The current user profile was changed from 64 to 20 while preserving enabled state,
Provider/dialect, endpoint, key, model, dimensions, and timeout. Manual task
`7badcc09b6f14c7c8fd15d4f3b2e6b46` then completed successfully:

```text
status/phase: succeeded/completed
error code: none
requests: 4 for 67 Units (20+20+20+7)
generation: 65026b0b24d2483c85b8efed672bdc83
dimensions: 1024
unit count: 67
vector state: ready
```

The previous failed task remains unchanged as history, and an explicit semantic
lookup returns three matches. The remaining Phase I product decision is the OCR
bundle-source and safe error-projection boundary.
