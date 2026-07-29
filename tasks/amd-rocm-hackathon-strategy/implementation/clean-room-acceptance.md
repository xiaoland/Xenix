# Clean-room and Lifecycle Acceptance

> Current product correction: only the Windows-to-Private-SSH matrix is a product
> acceptance gate. The Local Linux row below is retained as historical controller
> evidence, not a Linux desktop or remaining manual acceptance requirement.

## Baseline Vocabulary

- **Feasibility lab:** manually prepared runtimes/assets/caches used to prove a
  framework/model/protocol combination. Never one-click evidence.
- **Clean-room:** new client runtime state and new target identity/root with no AMD
  installation, provider projection, managed process/listener/forward, or inherited
  product trust state.
- **Cold install:** clean-room plus empty product-controlled acquisition, model,
  runtime, plugin, and compile caches.
- **Cold start:** a verified generation exists, but no live service, binding, or
  runtime incarnation exists. The test records whether compile cache is retained.
- **Warm:** the same verified generation and declared caches remain; used for
  idempotence and steady-state measurements.

The stopped `/opt/xenix-rocm-lab` and `/workspace/xenix-rocm-lab` paths are
feasibility-only. Selective deletion cannot prove absence of ambient HOME/system
caches, so definitive acceptance uses a fresh instance/PVC or an equivalently
attested clean image.

## Two Placement Roles

| Role | Controller location | What it proves |
| --- | --- | --- |
| Private SSH | Packaged/headless Xenix client outside the Radeon host | SSH trust, staging, remote supervision, loopback forward, disconnect/reconnect, remote cleanup |
| Local Linux Radeon | Product controller runs headlessly on the Radeon host | Same-host detection, process supervision, direct loopback binding, device loss, restart, cleanup without SSH |

The same Radeon Cloud hardware family may host the two roles in separate fresh
baseline runs. The Local role does not prove native Windows ROCm or a Linux desktop
installer.

## Clean-room Attestation

Before the one product action:

- record a redacted target/run identity and package/commit;
- prove the product installation/generation/cache roots do not exist;
- redirect HF, uv/pip, torch/vLLM, plugin, XDG, temp, and compile caches into
  run-owned roots and prove they are empty;
- prove no related process, listener, forward, provider entry, or product
  installation row exists;
- use a temporary client runtime home;
- for SSH, use an isolated `known_hosts` and one credential reference rather than
  the developer alias, global agent, or global SSH config;
- record target GPU/OS/kernel/driver/ROCm/storage/capacity facts.

A reachable supported SSH host with valid operator-provided trust/credentials is a
Private placement prerequisite, not a hidden product deployment step.

## Lifecycle Matrix

| Scenario | Initial state and action | Required result |
| --- | --- | --- |
| Cold install | Clean-room; one public deploy action; acquire all three pinned services | Compatibility/capacity precede mutation; G1 components stage and verify on ROCm; three managed refs register independently; selection unchanged; only loopback bindings |
| Idempotent reconcile | Warm verified G1; repeat ensure 2–3 times | No new generation/provider/revision/event/download/process incarnation; no settings rewrite. A lost ephemeral binding may rematerialize without changing durable identity |
| Repair | Corrupt download/hash/member/cache, kill service, leave stale lock/PID | Phase-specific typed result; no unverified registration; exact-manifest repair only; unrelated settings/files untouched; no fallback |
| Restart/reconnect | Kill controller/service, disconnect SSH, reboot target, occupy port, deliver late callback | Same generation/provider ref; old incarnation fenced; current operation fails honestly; next operation succeeds; no leaked process/forward/listener |
| Upgrade blocked | Selected/running G1; capacity hook prevents G2 coexistence/self-test | G1 remains selected and operational; G2 is blocked/unverified/unregistered. Once admitted, G2 receives a new provider identity and is not selected |
| Retire | Selected/referring/in-flight G1; accept desired absence; crash at each phase | `RETIRING` closes admission; issued scopes drain; blockers yield `REMOVAL_BLOCKED`; no selection/thread rewrite; exact projections and owned realization remove forward to absent |
| Reinstall | Fully absent after retirement; explicit deploy | A new generation/installation identity is created; no retired identity is resurrected |
| Hard cut-off | Release N retires/cleans all installations, then N+1 omits AMD; or pre-release attestation proves none ever existed | Generic product starts/packages with AMD slice absent; old refs are typed unavailable without fallback; inert tables migrate; no AMD UI/process/network/resource side effect |

## Capability Proofs

- Chat: non-streaming, SSE usage, automatic Tool Call and follow-up; server-received
  disconnect does not cause a second semantic request; abandoned stream releases
  its permit.
- Embedding: stable 1024-dimensional BGE-M3 vectors; request omits `dimensions`;
  partial multi-batch failure publishes no vectors and does not retry a possibly
  dispatched batch.
- OCR: fixed mixed Chinese/English PNG; all Det/Cls/Rec parameters and real inputs
  on ROCm Torch; one Binary Tensor request returns bounded PAGE XML that passes the
  pinned XSD; typed empty/failure distinction.
- Security: unauthenticated requests are rejected; services bind remote/local
  loopback only; tokens/endpoints are absent from settings, results, diagnostics,
  command summaries, and repository evidence.

## Evidence Chain

```text
package/commit
  -> clean baseline attestation
  -> InstallationSpec
  -> component manifest digests
  -> acquisition receipts
  -> GenerationRealization
  -> RuntimeAttestation
  -> capability self-tests
  -> managed-provider document revisions
  -> operation journey
  -> lifecycle cleanup attestation
```

Repository evidence is redacted. Private-key paths/material, host keys, GPU UUID,
live PIDs, ports, tokens, cloud endpoints, and user/business inputs stay out of the
task packet.

## Cold-versus-Warm Measurement Rule

Deployment self-tests themselves compile kernels and load models. First
compile/inference timing is captured inside those self-tests and labeled cold.
Later journey and steady-state measurements are labeled warm. A warm run may never
be presented as one-click cold latency.
