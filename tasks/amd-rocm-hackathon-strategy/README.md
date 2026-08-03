# AMD ROCm One-click Deployment

**Status:** implementation and automated acceptance complete; only manual
placement acceptance remains

**Opened:** 2026-07-26

**Completed implementation:** 2026-07-28

## Objective

Deliver a removable AMD Radeon/ROCm deployment slice that installs one pinned
Chat, Embedding, and OCR profile on either a compatible Local Linux Radeon host
or a pre-enrolled Private SSH Radeon target. Each verified component becomes an
ordinary generation-specific provider instance in its own LLM, Embedding, or OCR
domain; Xenix remains authoritative for settings, SQLite state, Knowledge,
conversations, and Artifacts.

## Guardrails

- `AmdAiDeploymentService` is a forward-only control plane. It is not an
  inference gateway, settings owner, or extension of the SSH ML worker pool.
- AMD/ROCm is target deployment provenance. Chat and Embedding retain ordinary
  OpenAI-compatible transports; OCR retains KServe V2 Binary Tensor plus the
  pinned PAGE profile.
- Capability settings owners alone own provider catalogs and selections. AMD
  submits idempotent owner-scoped commands through those owners to the one
  app-lifetime `SettingsStore`; it never changes a selected provider.
- Live endpoint, port, token, process, forward, health, and runtime-incarnation
  facts remain memory-only. Target cleanup is exact-generation and
  identity-fenced.
- AMD remains a removable leaf. Generic services have no direct AMD import;
  AMD-free packaging must remain usable even if its runtime environment requests
  the optional feature.
- Private SSH is private, not offline. No cloud address, credential, host key,
  endpoint, token, PID, or target path is retained in this packet.

## Verification

- [x] The three pinned manifests are admitted for the declared Radeon Cloud
  compatibility cell after real target acquisition, ROCm self-tests, and exact
  retirement cleanup.
- [x] The actual product composition prepared Chat, Embedding, and OCR over a
  Private SSH target; all three generic adapters operated and exact retirement
  reached `removed` with no target runtime residue.
- [x] Automated regression covers manifest/cell admission, exact vLLM wheel
  acquisition semantics, deployment-to-retirement lifecycle, OCR durable
  provenance, retirement-only mode, generic-to-AMD import fencing, and v24
  storage migration.
- [x] `pdm run test` passed (45 tests), `pdm run check` passed, and `pdm run
  smoke` passed.
- [x] The default AMD-enabled Windows package and its packaged smoke passed.
- [x] An AMD-absent package (`XENIX_BUILD_AMD_ONE_CLICK=0`) contained no AMD
  slice paths and passed packaged smoke even with `XENIX_ENABLE_AMD_ONE_CLICK=1`.

The detailed evidence and remaining acceptance boundary are in
[verification](verification.md).

## Current Truth

- The released profile is the admitted Granite/vLLM Chat, BGE-M3/vLLM Embedding,
  and RapidOCR/KServe/PAGE OCR set for the captured Linux Radeon Cloud cell.
- The product has both `LocalAmdPlacement` and `PrivateSshAmdPlacement` behind
  one deployment lifecycle. The Private SSH path has real cloud product-level
  evidence; the Local Linux implementation has static/lifecycle coverage but no
  physical Radeon acceptance host in this workspace.
- The settings repair is architectural, not a mutex: UI and deployment submit
  domain commands to LLM/Embedding/OCR owners, which write through one
  revisioned `SettingsStore`. A former UI test that bypassed this writer was
  updated to exercise the real authority path.
- No rollback or compensation journal was introduced. Retirement commits desired
  absence first, fences admission, and progresses only forward.
- The transient feasibility/product target was retired after validation. The
  validation root has no generated runtimes, receipts, tombstones, listeners, or
  owned process residue.

## Next Step

Perform only manual acceptance:

1. A user-guided Private SSH setup/removal walkthrough against a fresh enrolled
   Radeon target, including visible status and redacted failure handling.
2. A fresh compatible Local Linux Radeon host walkthrough. This is the required
   hardware acceptance for same-host placement; it does not imply native Windows
   ROCm support.

No architecture or product decision remains open for this task.

## Packet Map

- [Final verification record](verification.md)
- [Cloud and product development validation](development-validation.md)
- [Completion architecture review](implementation/completion-review.md)
- [Implementation plan and delivery map](implementation/README.md)
- [Hard cut-off contract and record](implementation/hard-cutoff.md)
- [Lifecycle acceptance boundary](implementation/clean-room-acceptance.md)
- [Original scheme review and issue dispositions](scheme-review.md)
- [Locked decisions](implementation/decision-closure.md)
