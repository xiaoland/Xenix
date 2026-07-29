# TP-10 — Manifest Catalog and Compatibility Planner

**Status:** Core catalog/planner implemented; concrete recipe resources and automated tests remain pending.

## Outcome

Replace task-local Markdown feasibility facts with a machine-readable product
manifest authority and a pure planner that rejects unsupported targets before
installation or settings mutation.

## Owned Mutation

- add `src/xenix/services/amd/manifests.py`;
- add versioned resources under `src/xenix/resources/amd/manifests/`;
- add `tests/test_amd_manifests.py`.

The central profile index is initially owned here; TP-19 alone updates its final
three-recipe aggregation/digests.

## Manifest Content

- schema/version/digest/license/source and exact immutable refs;
- supported OS/architecture/GPU/ROCm/HIP/framework/runtime cells;
- artifacts, hashes, model/tokenizer/runtime/plugin identities;
- protocol/profile, launch, self-test, authentication, capacity, deadlines, and
  cache/config isolation requirements;
- clean incompatibility reasons and acquisition receipts.

The first cell represents the verified `gfx1100`, Ubuntu 24.04, ROCm 7.2.1
combination without claiming all Radeon Cloud or all AMD GPUs.

V1 publishes one pinned Granite/BGE-M3/RapidOCR profile. It exposes no
model/runtime/cache/port/GPU tuning choice. `required_persistent_bytes` includes
download, staging, install, and first-compile headroom measured by a cold run;
until that external fact is recorded, the cell remains unadmitted rather than
asking the user to guess or continuing on the observed 20 GiB volume.

## Invariants

- mismatch fails before target/settings/SQLite mutation;
- no ambient plugin discovery, unbounded prerelease resolution, TLS bypass, or
  unpinned model revision;
- component manifests may evolve independently;
- manifests answer what; placements answer where/how; adapters answer wire/result;
- compatibility/capacity observation is typed and redacted.

## Acceptance

- exact verified cell is admitted and near-miss cells are rejected with the
  correct phase/reason;
- BGE `dimensions=None`, ROCm device proof, RapidOCR three-stage backend, and
  protocol/auth self-tests are mechanically represented;
- digest change is detected as a new technical generation;
- task-local evidence files are not runtime-loaded.
- the desktop base dependency set contains no ROCm/vLLM/RapidOCR target-runtime
  requirement; those are manifest-governed acquisitions.

## Verification

- manifest schema/digest/cell matrix tests;
- resource collection smoke;
- `pdm run check`.

## Current Implementation Slice

- `src/xenix/services/amd/manifests.py` now provides immutable component/profile
  descriptors, canonical SHA-256 identities, explicit source-verification and
  admission blockers, and an exact-digest read-only catalog.
- `src/xenix/services/amd/compatibility.py` now provides redacted target facts and
  a pure profile/component planner with typed manifest, target-cell, and capacity
  rejection reasons.
- No concrete product manifest or acquisition URL was added. The observed remote
  overlay and evidence-only lab paths are not accepted as product persistent
  storage; `free_persistent_bytes` means the product-authorized persistent root.
- This bounded slice used compile, Ruff, strict mypy, and an in-memory acceptance
  script. Per current task authority, no automated test file was added and pytest
  was not run.
