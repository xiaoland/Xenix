# Decision Closure

> Placement correction (2026-07-29): Xenix is a Windows desktop product and
> exposes only Private SSH Radeon for new deployment. The Local controller is
> composed cleanup-only for historical generations; new Local intent is
> rejected. Earlier Local/Private peer wording is retained below as historical
> plan evidence and is superseded by TP-20A and ADR 0010.

## Rule

The implementation tasks do not reopen the choices below. Apply the recorded
default and continue. Escalate only when new evidence contradicts a locked
constraint or requires product scope/authority outside this packet—not because an
implementation has several reasonable internal techniques.

## Locked Product and Architecture Choices

| Area | Locked choice |
| --- | --- |
| Product profile | One pinned Chat + Embedding + OCR profile; all three must verify for the profile to be usable |
| Placement | Current Windows product offers one explicit Private SSH Radeon target; historical Local Linux controller is cleanup-only and cannot accept new installation intent |
| Models/protocols | Granite/vLLM Chat, BGE-M3/vLLM Embedding, RapidOCR/KServe Binary Tensor PNG/PAGE 2024-07-15 |
| Deployment | `AmdAiDeploymentService` is a removable control-plane facade, never the inference path |
| Settings | Capability owner → one app-lifetime revisioned SettingsStore; no full-document shared save or cross-domain transaction |
| Managed identity | Owner-neutral capability ref with opaque `manager_id`, installation ID, and generation ID; G2 never replaces G1 |
| Selection | Deployment registers but never selects; each capability selection remains explicit and independent |
| Retry | Retry only when known not dispatched; possible dispatch makes binding loss terminal for the current semantic operation |
| Embedding switch | Switch-and-immediate-rebuild or cancel; failed rebuild leaves semantic retrieval unavailable |
| OCR failure | Legal no-text is empty success; provider/protocol failure fails the whole import and publishes no partial canonical document |
| Lifecycle | Immutable placement/generations, forward-only reconcile, no rollback/compensation, blocked upgrade leaves G1 untouched |
| Retirement | Commit desired absence and close admission, drain bounded scopes, expose blockers, never rewrite selections/Threads |
| SSH security | Explicit public-key credential reference, pinned isolated host trust, no password/TOFU/global fallback |
| Runtime security | Loopback-only authenticated services; unauthenticated requests must be rejected; protected secret handoff |
| User surface | No model/runtime/port/cache/GPU/fallback/continue-anyway tuning; show typed phase/status facts |
| Optional Model API | Separate explicit network-provider category, outside TP-00–24 and never fallback/core |
| Removability | AMD is a leaf composition slice; use release-N decommission then release-N+1 cut, or prove pre-release absence |

## External Admission Facts

These are measured or supplied facts, not product-design questions:

- target reachability and enrolled public-key/host-key validity;
- exact OS/kernel/GPU/gfx/driver/ROCm/HIP cell;
- persistent storage, VRAM, staging, install, and compile headroom;
- artifact source availability, license, revision, digest, and TLS validity;
- first-compile, readiness, request, and orphan-drain deadlines;
- OCR compressed/decode/XML/node/point/memory ceilings and accuracy;
- real ROCm workload/device attestation and three-service coexistence;
- fresh instance/PVC or equivalent clean-room attestation;

An absent, changed, insufficient, or unmeasured fact produces a typed admission
failure. It does not produce a new UI choice or silent fallback.

## Remaining Human Intent

The product still needs intentional commands, not architecture decisions:

- enter and verify one Private SSH target through the guided Install command;
- deploy, repair, upgrade, retire, or reinstall;
- explicitly select providers after registration;
- resolve a selection/reference blocker;
- provide/replace credential and pinned trust material through enrollment.

Implementation start, cloud mutation, branch/worktree, commit, release, and
submission permissions remain governed separately by the project protocol.
