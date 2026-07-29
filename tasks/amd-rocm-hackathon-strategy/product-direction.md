# Product Direction

This file owns the proposed product story and scope. The task control surface
remains in [README](README.md); implementation is not authorized.

## Product Promise

Xenix should let a non-technical business user prepare a private SSH AMD ROCm
target from the Windows desktop, then complete a source-linked
workflow with OCR, LLM, and Embedding model inference on the managed services. The
desktop Xenix installation remains the sole application authority; the execution
target holds only app-owned generation realizations, runtime/cache, process, and
bounded transient-request state. The desktop installation record owns normative
generation identity and lifecycle. The user should not have to configure model
endpoints, tunnels, containers, or GPU parameters by hand.

The product should present business capability and truthful derived status, not an
AMD model laboratory.

“AMD integration” is the product concept: one guided Private SSH deployment
control plane and one truthful status projection backed by independent OCR, LLM,
and Embedding services. Private SSH is a placement, not a different semantic
provider. It is not one universal inference provider and not a new authority over
Knowledge, conversations, indexes, or Artifacts.

## Track 2 Fit

The official Track 2 scope is private AI Agents with reasoning, planning, Tool use,
memory, and task execution. It requires at least two of these capability categories:
local RAG, Tool calling, multi-step planning, local multi-turn memory, and explicit
permission/privacy controls.

Xenix already has evidence-bearing boundaries for:

- local Knowledge import and source-linked RAG;
- registered Tool invocation;
- a multi-step Agent sampling/Tool loop;
- locally authoritative multi-turn conversation history.

The submission should claim only the capabilities it actually demonstrates.
Desktop authority supports privacy, but the chosen execution placement still has a
declared data boundary; neither fact is automatically an explicit permission
control.

## Primary Demonstration

Use the existing rainy-season restocking case:

1. The user drops a scanned purchasing-rule document into the Knowledge Workspace.
2. Xenix creates searchable, source-linked Knowledge.
3. The user attaches the inventory CSV to a conversation and asks the existing
   Chinese restocking question.
4. The LLM invokes locally authoritative Knowledge and data Tools; its model
   executes through the private SSH AMD target used for the contest demonstration.
5. Xenix returns the cited rule, exact restocking quantities, and a locally
   registered derived Dataset or Artifact without modifying either source.

The success claim is a shorter, source-linked, locally authoritative
scan-to-decision path with correct and reviewable output. Inputs required for model
inference cross the declared contest SSH boundary; engine names, live transport
bindings, deployment commands, and GPU placement remain behind the service
boundary. The current product does not claim a Linux desktop or native Windows
ROCm placement.

## Product Scope

Selected task-plan product scope:

- connect to a supported Private SSH Radeon target and verify its OS, driver,
  HIP/ROCm, capacity, and transport facts;
- offer one guided setup action for the complete AMD ROCm execution profile;
- admit exactly the pinned Granite/BGE-M3/RapidOCR profile from bounded hardware
  facts, or reject before acquisition;
- download, verify, self-test, publish, repair, and remove app-owned runtime/model
  generations on the selected target;
- run OCR detection/recognition, LLM, and Embedding model inference through ROCm;
- show truthful installed/operational/blocked status, AMD device identity, backend
  identity, and bounded performance evidence;
- automatically register one managed provider instance through each independent
  LLM, Embedding, and OCR configuration boundary;
- create a new immutable provider-instance identity for every component generation,
  so an upgrade cannot redirect an existing selection;
- route every UI and deployment settings mutation through one versioned physical
  writer and typed capability-owned commands;
- preserve their independent selection, compatibility, and result authority;
- never equate automatic registration with automatic selection or aggregate
  profile activation;
- optionally configure the Radeon Cloud Dedicated Model API
  (`Deploy Type = vLLM Model API`) as an explicitly
  networked LLM provider, with its own credentials and data-boundary disclosure.

Explicitly outside this product slice:

- claiming arbitrary local Radeon, native Windows, WSL, or Linux compatibility
  without an admitted execution cell;
- requiring a graphical desktop for the inference services or on a Private SSH
  target;
- a centrally hosted, multi-user, or remotely authoritative Xenix backend;
- exposing Docker, manual serve commands, raw SSH port-forwarding, or GPU placement
  as ordinary business-user choices;
- implicit remote inference fallback;
- asking the user or Agent to choose an ML worker or accelerator;
- treating a remote model cache, index, Dataset, conversation, or result as
  authoritative;
- claiming that a Radeon Cloud Linux run proves another OS/GPU/runtime cell;
- adding a Project entity, per-project Knowledge library, or hosted Xenix backend.

This scope does not remove or redesign the accepted ADR 0005 SSH ML worker pool. It
remains a guided batch-execution product adapter with local authority. A persistent
remote inference target may reuse proven SSH configuration primitives, but needs a
separate lifecycle boundary and durable decision instead of extending the pool by
accident.

## Product Modes and Placements

The product must not blend managed execution with compatibility or an external
provider:

1. **Private SSH AMD ROCm:** Xenix services and canonical state remain on the
   desktop. Through `AmdAiDeploymentService`, the AMD deployment domain prepares and
   supervises the user-controlled target with its internal coordinator/driver, then
   registers three ordinary managed provider instances. Their providers are
   materialized at natural operation boundaries by AMD-module-owned implementations
   of the separate capability factory ports; capability code consumes neither an
   AMD binding nor an endpoint-resolver object. The deployment facade is not in the
   request path and does not change capability selections.
   “Private” means the accepted
   SSH/loopback/no-external-inference-API profile; it does not mean offline and
   remains bounded by the cloud/provider threat model.
2. **Compatibility profile:** existing providers and the verified Paddle Inference
   OCR remain available and truthfully named, but the product does not label this
   as complete AMD/ROCm execution.
3. **Optional Dedicated Model API:** an explicit platform-managed network provider
   choice for bounded use cases. It is outside the managed deployment placement
   and does not replace the Track 2 core path.

CPU work that is not neural-model inference—image decoding, resizing, OCR
postprocessing, orchestration, persistence, and Tool execution—does not invalidate
the ROCm profile. Backend and target provenance must make this boundary observable.

## OCR Decision

Sir selected complete ROCm coverage as the product target. The current accepted OCR
contract still points to an official Paddle Inference Windows x64 bundle. The
Radeon Cloud spike has now proven RapidOCR 3.9.2 PP-OCRv6 Det/Cls/Rec on PyTorch
ROCm, KServe V2 Binary Tensor PNG input, and PAGE 2024-07-15 output on the exact
captured cell. The task plan selects that engine-neutral protocol/profile—not a
local `RocmOcrAdapter` or a newly invented API. Product admission still must prove:

- Chinese text detection and recognition quality against the current baseline;
- supported operators, precision, memory, and absence of silent model fallback;
- immutable runtime/model identity and compatible worker output;
- target-aware deployment, self-test, forward-only repair/recovery, and monotonic
  removal without settings rollback.

Until TP-02 records the new ADR, Paddle remains the durable accepted compatibility
path and the PyTorch ROCm backend remains task-plan scope rather than a shipped
claim.

## Resolved Design and External Admission Facts

The task fixes the `AmdAiDeploymentService` control plane, current Private SSH
placement, fixed three-component profile, strict public-key SSH trust,
authenticated loopback services, forward-only lifecycle, owner-neutral managed
refs, PAGE-only OCR profile, and removable AMD composition slice. The optional
Dedicated Model API remains outside the managed slice as an ordinary explicit
network-provider category and is never fallback.

The exact persistent bytes, deadlines/resource ceilings, artifact availability,
licenses, target reachability/trust, and clean-room hardware/
runtime evidence are external admission facts. Unsupported or unmeasured cells are
rejected; they do not create user-facing model, backend, fallback, or
continue-anyway decisions.
