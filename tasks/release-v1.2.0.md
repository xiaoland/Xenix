# v1.2.0 Release Packet

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
- No v1.2.0 candidate artifact or public publication exists yet.

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

Run the local release gate, commit the release identity, create annotated tag
`v1.2.0`, push the release commit to `origin/develop`, and run the protected
candidate workflow for that tag.
