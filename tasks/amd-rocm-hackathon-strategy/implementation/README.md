# AMD ROCm Implementation Plan

**Prepared:** 2026-07-28

**Status:** delivered; automated verification complete; physical placement
acceptance remains manual

**Permission boundary:** this directory now records the approved implementation
and its evidence. It still does not authorize a commit, release, submission, or
new cloud mutation.

## Outcome

Implement one guided AMD deployment capability that:

- supports a compatible Radeon host through either `LocalAmdPlacement` or
  `PrivateSshAmdPlacement`;
- installs pinned Chat, Embedding, and OCR generations, proves real ROCm execution,
  and exposes them through existing capability-owned protocols;
- adds generation-specific managed provider instances through LLM, Embedding, and
  OCR settings owners without changing any current/default selection;
- keeps live URL, port, token, process, tunnel, health, and runtime-incarnation
  facts out of durable provider settings;
- resumes install, repair, upgrade, restart, and retirement only forward from
  authoritative current state;
- remains a removable composition slice whose absence leaves ordinary Xenix
  startup, persistence, providers, Knowledge, OCR, packaging, and diagnostics
  complete;
- never falls back from AMD to CPU, SSH, Local, or an external API without an
  explicit new user choice.

The manually prepared feasibility lab has been stopped and remains
`manual-preheated/acceptance-ineligible`. It may supply evidence and engineering
diagnostics, but it may not supply product runtime files or caches to a cold
one-click acceptance run.

## Why the Facade Is Not First

`AmdAiDeploymentService` is the final deep control-plane facade, not the first
implementation seam. The current repository first needs:

1. a physical revisioned settings writer;
2. capability-owned provider catalogs, factories, and semantic operation scopes;
3. an engine-neutral OCR parent/spawn boundary;
4. an AMD lifecycle kernel proven with fake placements and deterministic faults.

Only then can the facade coordinate forward reconcile without becoming a settings
owner, inference gateway, SSH worker pool, or service locator.

## Architecture Lock

The implementation must preserve these ownership rules:

| Fact | Sole authority |
| --- | --- |
| Installation identity, immutable placement, desired presence, component-generation lifecycle | Desktop AMD installation repository |
| Exact runtime/model/protocol/self-test definition | Versioned component manifest |
| Target files, processes, forwards, runtime incarnation, live health | Exact Local/SSH execution session |
| Provider instances and selections | Matching LLM, Embedding, or OCR settings owner |
| Per-document revision and atomic JSON publication | One app-lifetime `SettingsStore` |
| Semantic operation scope | Matching capability service/factory |
| Admission to one AMD generation and scoped use count | AMD-private generation gate |
| Conversation, vector-space, OCR result, and Knowledge publication semantics | Existing capability owners |
| Product status | Read-only derived projection |

The baseline transport is `LoopbackHttpBinding`. There is no public
`EndpointLeaseResolver`, public `AmdRuntimeBindings`, generic AMD inference
gateway, aggregate `READY`, cross-domain settings transaction, or rollback
journal.

## Hard Cut-off Lock

AMD one-click is optional at composition, not optional inside capability
correctness. Generic LLM, Embedding, OCR, Knowledge, Agent, SettingsStore, storage,
smoke, and diagnostics never import the AMD module. Capability-owned managed
references are owner-neutral and remain readable as typed unavailable projections
when their manager implementation is absent; no selection or fallback changes.

The removable files, bounded app/spec anchors, inert-migration rule, two-release
decommission sequence, and negative-build proof are canonical in
[the hard cut-off contract](hard-cutoff.md). A plan or implementation that needs
to delete or conditionalize TP-03–07 to remove AMD is rejected.

## Implementation Lanes

The task files are deliberately smaller than the product feature. Shared edit
hotspots have a single owner and are sequenced rather than implemented in
parallel.

| Lane | Tasks | Purpose |
| --- | --- | --- |
| Durable contract recording | TP-00–TP-02 | Record already resolved lifecycle, LLM-reference, and OCR contracts |
| Settings and capability seams | TP-03–TP-07 | Establish the sole settings writer and three capability-owned data paths |
| AMD control plane | TP-08–TP-11 | Add SQLite authority, runtime kernel, manifests, and forward reconcile |
| AMD data-plane adapters | TP-12–TP-14 | Bind Chat, Embedding, and OCR operation scopes to exact AMD generations |
| Placement and recipes | TP-15–TP-18 | Realize Private SSH and three pinned ROCm services |
| Product integration | TP-19–TP-21 | Compose, expose guided UI, package, and operate the vertical slice |
| Local and final acceptance | TP-22–TP-24 | Prove Local semantics, removability, and clean-room lifecycle behavior |

See [the dependency graph](dependency-graph.md), [the implementation
rehearsal](rehearsal.md), [clean-room acceptance](clean-room-acceptance.md), and
[the hard cut-off contract](hard-cutoff.md). [Decision closure](decision-closure.md)
separates locked choices from external admission facts.

## Delivery Record

The original subtask files preserve the execution decomposition. Their delivery
state is summarized here; final evidence is in the
[completion review](completion-review.md) and
[verification record](../verification.md).

| ID | Task | Depends on | State |
| --- | --- | --- | --- |
| TP-00 | [Managed AMD durable decision](subtasks/TP-00-managed-amd-decision.md) | — | Delivered |
| TP-01 | [LLM managed-reference policy](subtasks/TP-01-llm-reference-policy.md) | — | Delivered |
| TP-02 | [OCR PAGE and failure profile](subtasks/TP-02-ocr-product-profile.md) | — | Delivered |
| TP-03 | [Revisioned SettingsStore](subtasks/TP-03-settings-store.md) | — | Delivered |
| TP-04 | [LLM capability and operation seam](subtasks/TP-04-llm-capability-seam.md) | TP-01, TP-03 | Delivered |
| TP-05 | [Embedding provider catalog](subtasks/TP-05-embedding-provider-catalog.md) | TP-03 | Delivered |
| TP-06 | [Engine-neutral OCR extraction](subtasks/TP-06-ocr-neutral-extraction.md) | TP-02 | Delivered |
| TP-07 | [OCR settings, KServe/PAGE, and spawn](subtasks/TP-07-ocr-kserve-spawn.md) | TP-03, TP-06 | Delivered |
| TP-08 | [AMD installation repository](subtasks/TP-08-amd-installation-repository.md) | TP-00 | Delivered |
| TP-09 | [AMD runtime kernel](subtasks/TP-09-amd-runtime-kernel.md) | TP-08 | Delivered |
| TP-10 | [Manifest catalog and compatibility planner](subtasks/TP-10-amd-manifest-planner.md) | TP-00 | Delivered and cloud-admitted |
| TP-11 | [Deployment coordinator and reconcile](subtasks/TP-11-amd-deployment-reconcile.md) | TP-04, TP-05, TP-07, TP-08, TP-09, TP-10 | Delivered |
| TP-12 | [AMD Chat adapter](subtasks/TP-12-amd-chat-adapter.md) | TP-04, TP-09 | Delivered |
| TP-13 | [AMD Embedding adapter](subtasks/TP-13-amd-embedding-adapter.md) | TP-05, TP-09 | Delivered |
| TP-14 | [AMD OCR adapter](subtasks/TP-14-amd-ocr-adapter.md) | TP-07, TP-09 | Delivered |
| TP-15 | [Private SSH placement](subtasks/TP-15-private-ssh-placement.md) | TP-09, TP-10 | Delivered and cloud-validated |
| TP-16 | [Granite/vLLM recipe](subtasks/TP-16-granite-recipe.md) | TP-10, TP-15 | Delivered and cloud-validated |
| TP-17 | [BGE-M3/vLLM recipe](subtasks/TP-17-bge-recipe.md) | TP-10, TP-15 | Delivered and cloud-validated |
| TP-18 | [RapidOCR/PAGE recipe](subtasks/TP-18-rapidocr-recipe.md) | TP-07, TP-10, TP-15 | Delivered and cloud-validated |
| TP-19 | [Private SSH vertical slice](subtasks/TP-19-private-ssh-vertical-slice.md) | TP-11–TP-18 | Delivered and product-validated |
| TP-20 | [Guided AMD UI](subtasks/TP-20-guided-amd-ui.md) | TP-19 | Delivered; manual walkthrough remains |
| TP-21 | [Packaging and operations](subtasks/TP-21-packaging-operations.md) | TP-20 | Delivered and package-validated |
| TP-22 | [Local Linux Radeon placement](subtasks/TP-22-local-linux-placement.md) | TP-09–TP-14, TP-16–TP-18 | Delivered; physical Radeon acceptance remains |
| TP-23 | [Clean-room lifecycle acceptance](subtasks/TP-23-clean-room-acceptance.md) | TP-19, TP-21, TP-22, TP-24 | Automated/Private evidence complete; manual cells remain |
| TP-24 | [AMD feature hard cut-off proof](subtasks/TP-24-amd-hard-cutoff.md) | TP-21 | Delivered |

## Delivery Waves

Tasks within a wave may run in parallel only when their ownership tables do not
overlap.

1. **Record resolved contracts:** TP-00, TP-01, TP-02.
2. **Foundations:** TP-03 independently; TP-08 and TP-10 after TP-00.
3. **Capability paths:** TP-04, TP-05, then TP-06 → TP-07; TP-09 may proceed from
   TP-08 independently.
4. **Control/data-plane join:** TP-11 and TP-12–TP-14 after their prerequisites.
5. **Private placement:** TP-15, then TP-16–TP-18, then TP-19.
6. **Product surface:** TP-20 → TP-21.
7. **Local, cut-off, and lifecycle proof:** TP-22 and TP-24, then TP-23.

The critical path is OCR:

```text
OCR policy
  -> neutral extraction
  -> settings/KServe/spawn
  -> AMD OCR adapter
  -> RapidOCR recipe
  -> Private SSH vertical
```

## Implementation Impact Record

The approved implementation acknowledged and completed these cross-owner changes:

- a forward SQLite migration for AMD installation/generation authority;
- revision-envelope migrations for LLM and Embedding JSON settings and a new OCR
  settings document;
- changes to Chat retry semantics, Embedding provider identity, Knowledge OCR
  spawn/provenance/failure behavior, Settings UI conflict handling, packaging, and
  diagnostics;
- remote downloads, process creation, SSH trust/credentials, loopback listeners,
  GPU/VRAM/storage use, and exact identity-guarded cleanup;
- one optional composition anchor, owner-neutral managed refs, inert released AMD
  tables, and an AMD-absent package/smoke proof;
- no branch, worktree, commit, push, release, or submission unless separately
  authorized.

The source implementation followed the planned dependency order; it did not begin
with the deployment facade or hide settings/transport behavior inside it.

## Completion Definition

The feature is complete only when all of the following are true:

- a fresh Private SSH target and a fresh same-host Linux Radeon target each pass
  the lifecycle matrix;
- one public product action performs compatibility check, acquisition, install,
  ROCm self-test, publication, and independent provider registration;
- Chat SSE/Tool, 1024-dimensional BGE-M3 Embedding, and PNG-to-PAGE OCR pass
  through product adapters with unauthenticated access rejected;
- no managed provider persistence contains a URL, port, token, health fact, PID,
  tunnel, or runtime incarnation;
- G2 never redirects or auto-selects over G1;
- interrupted install/reconcile/restart/retirement resumes only forward;
- current operations are never silently replayed on binding loss;
- the TP-24 negative build passes with the AMD slice/resources absent, old managed
  refs typed unavailable, inert AMD tables readable, and no generic-to-AMD import;
- product code and packaged smoke pass the repository verification manifest.

The Local proof may run headlessly on a fresh Radeon Cloud instance by executing
the product controller on the GPU host itself. That proves same-host Linux
placement semantics; it does not claim native Windows ROCm or a Linux desktop
installer.
