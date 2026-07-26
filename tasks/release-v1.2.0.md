# v1.2.0 Release Packet

## Status

Completed on 2026-07-24. The immutable `v1.2.0` tag and published candidate both
identify release commit `9fccee1a6a930995f70deff203c5f3a9a2cac366`.

## Objective

Publish Xenix Native v1.2.0 from the accepted Knowledge Base implementation,
including its native Knowledge OCR runtime, semantic and hybrid retrieval, task
queue, index lifecycle, Workspace loading model, and document removal behavior.

## Guardrails

- Build, tag, and publish from the clean `codex/release-v1.2.0` linked worktree.
- Preserve the user's unrelated changes in the primary worktree.
- Publish only the candidate manifest digest produced by the protected candidate
  workflow.
- Keep Setup and bundled PE files explicitly unsigned.
- Treat the Velopack Setup as a stable alias, not an immutable version-named
  artifact; immutable desktop and Knowledge OCR artifacts must never be
  overwritten.
- Do not expose candidate objects or build-time release credentials.

## Verification

- `pdm run release-identity` reports version `1.2.0` and the intended release
  commit; after tagging, `--require-tag` accepts exactly `v1.2.0`.
- `pdm run check` and `pdm run test` pass on the release commit.
- The protected `Native Release Candidate` workflow passes checks, the complete
  suite, package, packaged smoke, Velopack packaging, native OCR build and frozen
  OCR/DOCX/PPTX import/retrieval acceptance.
- The candidate workflow prints version `1.2.0` and one reviewed manifest
  SHA-256.
- The protected `Native Publish` workflow publishes that exact digest and verifies
  public artifact hashes, HTTP Range support, feeds, and the stable Setup alias.

## Current Truth

- `origin/develop` v1.1.0 and the eight accepted post-v1.1.0 commits have been
  joined without rewriting their identities.
- `origin/main` release fix `42b5dbd` has been joined. Its version-invariant Setup
  collision regression was reconciled with the schema-v2 manifest and mandatory
  external Knowledge OCR artifact.
- Release artifacts are partitioned into immutable artifacts, mutable feeds, and
  exactly one stable Windows Setup. The focused publication suite passes.
- `pyproject.toml` declares `1.2.0`.
- The clean release worktree passes `pdm run check`, the 633-test non-UI suite
  (`633 passed, 4 skipped`), and the 58-test App/UI entry suite.
- Candidate run `30065002770` passed identity, check, and the complete suite, then
  failed before any OSS upload because its non-Developer-Shell runner did not expose
  the locked Visual C++ OpenMP redistributable through `VCToolsRedistDir` or
  `System32`. The worker itself compiled successfully. The build resolver now uses
  Visual Studio installation metadata and the locked redistributable identity.
- Candidate run `30066768248` proved that fix by building and verifying the native
  OCR archive, then passed PyInstaller but returned exit code 1 from frozen smoke.
  The wrapper had destroyed its temporary runtime while reporting only that code.
  It now emits a bounded, secret-redacted error projection and Knowledge marker
  before cleanup; the stale pre-conversation-cutover hidden import was also removed.
- The same v1.2.0 source, packaged locally with the verified native OCR bundle,
  subsequently passed `pdm run smoke-package`; the CI-only failure remains
  non-reproducible, so the diagnostic projection is retained for the next candidate.
- Candidate run `30070534998` passed identity, checks, and the non-UI cohort
  (`635 passed, 4 skipped`) but was cancelled after the UI cohort exceeded 75
  minutes. Its cancellation dump exposed one application-lifetime defect:
  repeated `build_main_window()` calls reused one `QApplication` while each
  window started three Knowledge workers that were only stopped by
  `aboutToQuit`. Closing a window now notifies the application composition root,
  which performs the same idempotent shutdown; startup unwind uses that owner too.
- The lifecycle regressions pass, and the full App/UI cohort now completes as
  `60 passed` in 86.08 seconds. `pdm run check` also passes on the corrected
  release tree.
- Candidate run `30076677241` then exposed a second ownership defect in the
  non-UI cohort: a Knowledge task-queue query remained on Qt's global thread
  pool after its window closed, while the next `MainWindow` lifecycle disposed
  the shared SQLite runtime. The resulting native access violation occurred in
  `KnowledgeTaskQueryService.list_tasks`, before packaging or OSS upload.
- Knowledge Workspace, task queue, and Settings background work now belongs to
  dialog-local pools. Accepted `MainWindow` closure quiesces those owners before
  emitting the application-runtime shutdown signal, so service disposal cannot
  overtake a UI task.
- Cross-order local verification also exposed that the startup splash previously
  imported process-global Python modules and C extensions on a daemon thread.
  PySide's import hook can abort natively under that topology. Runtime imports
  now remain on the application thread and pump Qt events at each module
  boundary, preserving splash responsiveness without concurrent module
  initialization.
- The corrected tree passes the cross-order Knowledge/Settings/MainWindow/i18n
  cohort (`89 passed`), then the complete repository gate as `636 passed, 4
  skipped` plus the isolated `60 passed` MainWindow cohort.
- Candidate run `30078564319` passed identity, checks, and the complete suite,
  then built and verified native OCR and the frozen application. Its packaged
  smoke exposed a contract error in the acceptance harness before OSS upload:
  `import_file()` promises Canonical Ready, while the post-commit
  Import→Derivation notification is independently handed off. The smoke required
  the derivation row synchronously and raced that handoff. It now waits with a
  bounded timeout for derivation visibility without coupling the two services.
- Candidate run `30082556318` was cancelled while the App/UI cohort was still
  progressing. Its completed log later showed that the non-UI cohort had passed
  as `637 passed, 4 skipped`; the cancellation, not a test failure, produced the
  subsequent access-violation dump.
- Candidate run `30086692198` passed the complete test gate, native OCR build,
  packaged smoke, and installer construction. It was cancelled during the
  long-running private OSS upload, before a candidate manifest was committed.
- Candidate run `30092294272` completed successfully from tag `v1.2.0`. It
  passed the non-UI cohort as `637 passed, 4 skipped`, the App/UI cohort as
  `60 passed`, packaged smoke, native OCR and installer construction, private
  OSS upload, and full object SHA-256 verification.
- The accepted candidate identity is version `1.2.0` with manifest SHA-256
  `e1f1868cf3761ccd3a336f4591e9e980ceed5cbcb6e0baa0d62a04318b4e4647`.
- Publish run `30099493578` was rejected before runner allocation because the
  protected `native-publish` environment admits `main`, not tag refs. It
  executed no publication code and changed no public object.
- Publish run `30099580045` was therefore dispatched from `main` with the exact
  accepted candidate version and digest. It completed successfully and recorded
  rollback snapshot
  `published/publication-history/20260724T140742Z/`.
- Post-publication probes confirmed the `1.2.0` Full package in both channel
  feeds, HTTP 200 for the stable Setup alias with `Cache-Control: no-cache`, and
  HTTP 206 for a one-byte range request. The public Full package is
  `767,606,653` bytes and the stable Setup alias is `772,086,653` bytes.

## Release Notes

- Introduces the global Knowledge Workspace with TXT, DOC/DOCX, PDF, JPEG/PNG,
  PPT/PPTX import, drag-and-drop, task inspection, and document removal.
- Adds keyword, semantic, and hybrid Knowledge lookup for data-analysis Agents.
- Adds configurable Embedding and Knowledge settings, explicit index rebuilds,
  index task visibility, and embedding-generation compatibility.
- Adds the optional official Paddle Inference C++ local OCR runtime as a verified,
  on-demand release artifact.
- Improves Knowledge Workspace responsiveness with independent loading and status
  projections.

## Next Step

No release action remains. Future product work starts from the published
`v1.2.0` baseline; any rollback must use the recorded publication-history
snapshot through the protected `Native Publish` workflow.
