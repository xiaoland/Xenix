# Slice 03 — Current OCR Service Topology

**Date:** 2026-07-23
**Scope:** source, native build, UI composition, Import execution, and release path

## Runtime composition

```text
GUI process
|-- PaddleOcrDeploymentService(paths)
|   |-- Knowledge Settings: status/install/repair
|   `-- Knowledge Workspace Service: footer status
|
`-- KnowledgeImportService
    `-- coordinator thread
        `-- spawned Python Import worker
            |-- PaddleOcrDeploymentService(request.paths)
            |-- PaddleOcrService
            `-- xenix-ocr.exe --stdio
```

Deployment owns catalog, archive acquisition, verification, activation, and
generation resolution. Execution owns one native session. The GUI does not execute
OCR. Each Import attempt runs in a spawned Python worker protected by a Windows Job
Object; only OCR-routed attempts launch the native child.

The Import worker reconstructs deployment/execution services from the same
`AppPaths`; it does not receive a live GUI service. This keeps native process
authority inside the already isolated Import attempt.

## Deployment state and storage

```text
runtime catalog + release origin
              |
              v
download/cache exact archive
              |
              v
safe extract -> runtime/member hashes -> native self-test
              |
              v
bundles/<generation> --atomic pointer--> active.json
              |
              `-------------------------> verification.json
```

The catalog binds archive name, bytes, SHA-256, runtime ID, model-pack ID, engine,
and protocol. A fixed-length content-addressed generation ID hashes the runtime,
model-pack, and full artifact identities; descriptive identities stay in manifests
instead of lengthening native Windows paths.
`active.json` selects one immutable generation. A freshness-bound verification
record avoids hashing the 205 MB archive closure on every Workspace refresh; stale
evidence enters `CHECKING` and full verification runs off the UI thread.

Primary states are `not_installed`, `checking`, `ready`, `repair_required`,
`installing`, and `failed`.

## Import and native execution

```text
parent: snapshot source into CAS
  -> spawn Import worker
  -> child: verify -> normalize -> page/image route -> parse
       -> if OCR pages exist:
            open one PaddleOcrSession
            version -> initialize
            render/recognize each OCR page
            shutdown
       -> freeze canonical bundle + result.json
  -> parent validates hashes/identity
  -> parent alone publishes SQLite state
  -> derivation/index
```

PDF page routes are evidence-based:

- credible native text -> `docling-pdf-native`;
- absent native text -> `paddleocr-page`;
- suspect native text -> `paddleocr-hybrid-page`;
- OCR unavailable -> `text-projection-unavailable`.

Images use a Docling shell plus OCR text projection. One Import attempt initializes
the native model once and reuses the session across all routed pages. A page failure
is page-scoped and does not discard successful pages.

The native protocol uses a four-byte big-endian frame length plus bounded UTF-8
JSON. Its lifecycle is `version -> initialize -> recognize* -> shutdown`. The C++
worker returns only engine-neutral text, confidence, and polygon values; it has no
SQLite, HTTP, release, or Artifact publication authority.

## Build and release

```text
runtime.lock.json
  -> pinned source/dependencies/models
  -> MSVC/CMake native build
  -> worker + DLL/model/license closure
  -> runtime.json member hashes
  -> native self-test + golden recognition
  -> deterministic ZIP + runtime_catalog.json
  -> release manifest/candidate
  -> immutable OSS artifact
```

The desktop package embeds only `runtime_catalog.json`, not the 205 MB archive. A
public release build freezes the release origin, and local OCR setup downloads the
separate immutable artifact. Packaged smoke preloads the same exact archive into an
isolated runtime home and exercises install, spawned Import, native OCR, canonical
provenance, derivation, and lookup.

## Source-development composition

```text
dist/knowledge-ocr/{archive,catalog}
                  |
                  v
scripts/run_dev.py -> LocalPaddleOcrBundleSource
                  -> PaddleOcrDeploymentService
                  -> shared verification/activation state machine
```

The diagnosed break was the absence of this composition. Phase I now gives
deployment one `PaddleOcrBundleSource` contract containing catalog authority plus
one artifact materialization operation. `run_dev.py` selects the generated local
catalog/archive when neither explicit development override is present. Frozen
composition loads the embedded catalog and resolves its archive through the
immutable release origin. Both transports feed the same cache, size/SHA, safe
extraction, manifest, self-test, and atomic activation path.

Self-test runs after the candidate reaches its final immutable generation path and
before `active.json` publication. A shorter staging path is not evidence that the
final Windows `.pdiparams` path is usable.

The settings QRunnable now converts only typed `knowledge_ocr_*` failures into a
content-free failed status. Knowledge Settings presents distinct unavailable,
download, integrity, and self-test guidance without arbitrary exception text.
Existing active generations remain executable when no install source is present.

## Assessment

The process topology, immutable generation model, protocol, publication authority,
and repaired source boundary are structurally sound:

1. catalog identity plus local/remote artifact access form one explicit bundle-source
   dependency;
2. development and frozen release select sources at composition time;
3. deployment alone verifies and activates generations;
4. the UI task boundary carries typed, content-free failures only.
