# AMD Execution Placement Options

This file owns the placement review for managed AMD ROCm inference. It corrects the
earlier SSH-only topology without claiming that every local OS/GPU/runtime cell is
already supportable.

## Finding

The previous scheme could not support one-click deployment for a user whose desktop
already has a compatible AMD GPU. It explicitly made a private SSH target the sole
AMD product placement and embedded SSH target facts in `AmdAiDeploymentService`,
`AmdExecutionProfile`, and the runtime session.

SSH was selected because the current development machine has no AMD GPU. That
development constraint should choose the first test driver, not define the product
architecture.

The product concept is **managed AMD ROCm deployment**. Local Radeon and private SSH
are placement variants behind the same deployment/component contract:

| Placement | User meaning | Execution boundary | Product status |
| --- | --- | --- | --- |
| Local Radeon | Run all admitted neural inference on a compatible AMD GPU in this user's machine | Local process/runtime; optionally a separately admitted Windows-local Linux environment such as WSL | Required architecture path; exact compatibility cells unproven |
| Private SSH Radeon | Run on a user-controlled AMD machine reached over SSH | SSH/SFTP, remote process supervision, local forwarding | Required architecture path and current cloud-development path |
| Dedicated Model API | Explicit platform-managed network provider | External HTTPS provider | Optional provider, not a managed placement |

“Local” is a product/data-boundary fact, not a claim that arbitrary Radeon hardware,
native Windows, WSL, or Linux is supported. A local target is admitted only when the
exact OS, GPU/gfx, driver, ROCm, engine, model, and packaging cell passes all three
component gates.

## Placement-Neutral Deployment

The AMD deployment domain owns installation intent and component lifecycle, not
SSH; `AmdAiDeploymentService` is its public facade.
Composition registers the available drivers; an immutable installation spec owns
exactly one tagged target and selects the matching driver at runtime:

```text
AmdAiDeploymentService
  -> installation coordinator/repository
       -> private placement-driver registry
            -> Local Radeon target driver
            -> Private SSH Radeon target driver
            -> possible WSL execution driver, only after separate admission
```

The target contract is deliberately operational rather than protocol-semantic:

- inspect and attest the target compatibility cell;
- materialize and hash artifacts for an app-owned immutable generation ID;
- start, observe, and stop that generation realization;
- expose a memory-only loopback binding for an exact generation;
- collect bounded runtime/device/workload evidence;
- remove only app-owned target realizations and transient state.

It does not expose Chat, Embedding, OCR, Knowledge, provider selection, or result
interpretation.

The versioned component manifest is the authority for exact
artifact/runtime/model/protocol/self-test requirements. An immutable
`InstallationSpec` pins one execution profile and manifest digests but contains no
live connection. Placement-specific configuration belongs to its tagged target
reference:

- a local reference identifies the admitted local compatibility cell and contains
  no remote credential;
- an SSH reference identifies the trusted remote target and credential reference,
  never private-key material;
- a WSL reference, if admitted, identifies the managed distribution/environment
  and its host/GPU compatibility facts rather than pretending to be a native
  process.

Installation/component generation reference shape is placement-independent.
Provider settings therefore continue to store `installation_id` and
`component_generation_id` without a target URL. Placement identity itself is
immutable inside one installation: switching Local/SSH creates a new installation,
not merely a new generation and never an endpoint edit.

The desktop `ComponentGenerationRecord` is the sole normative owner of generation
ID, manifest digest, desired presence, and lifecycle. A target driver owns only
`GenerationRealization` facts such as files, processes, listeners, caches, and
observations. It executes idempotent commands for a supplied generation ID and
returns evidence; the installation coordinator decides and records lifecycle
transitions.

## Runtime Sessions

The earlier `AmdAiRuntimeSession` name obscured its SSH coupling. The private live
abstraction is an `AmdExecutionSession` with placement-specific implementations:

- `LocalAmdExecutionSession` owns local child processes, local runtime directories,
  loopback listeners, local GPU observations, and process-tree cleanup;
- `SshAmdExecutionSession` owns SSH/SFTP, remote processes, local forwards, remote
  owner fencing, and remote cleanup;
- a future `WslAmdExecutionSession` is distinct if Windows-local deployment needs
  WSL command/filesystem/process boundaries.

Each session publishes the same private HTTP binding shape:
`(installation, component generation, runtime incarnation, loopback base URL,
memory-only credential)`. Name it `LoopbackHttpBinding`; do not claim transport
generality beyond the current OpenAI/KServe HTTP protocols. Capability adapters and
provider settings do not branch on placement.

Local placement does not require SSH or port forwarding. It still needs dynamic
binding materialization because local service ports and processes are runtime state
and must not become durable provider authority.

## Shared Versus Placement-Specific Lifecycle

Shared:

- immutable installation/profile shape and component-manifest schema; concrete
  manifest variants may differ by execution cell;
- compatibility and capacity admission;
- download/hash/signature/license checks;
- generation staging, protocol self-test, ROCm workload proof, and verification;
- forward-only provider registration;
- operation generation pinning;
- monotonic removal and local canonical finalization.

Placement-specific:

| Concern | Local Radeon | Private SSH Radeon |
| --- | --- | --- |
| Trust | Local OS user/runtime directories | Host key, SSH authentication, remote owner |
| Artifact transfer | Local materialization | SFTP/remote download and hash verification |
| Process ownership | Local process tree/job/cgroup equivalent | Remote supervisor plus SSH controller fencing |
| Binding | Direct loopback service | Loopback service through SSH local forward |
| Cleanup | Local app-owned paths/processes | Remote app-owned paths/processes and local forward |
| Disconnect | Local process/runtime failure | SSH/forward/remote process failure |
| Privacy claim | Machine-local within declared OS boundary | Private remote boundary; explicitly not offline |

These differences belong inside target drivers. They must not fork the LLM,
Embedding, or OCR provider models.

## Windows, WSL, and Linux

Architecture support is broader than an accepted compatibility claim:

- Linux Radeon/ROCm is the strongest complete-service candidate and the available
  cloud evidence cell.
- Native Windows currently has a narrower ROCm/PyTorch surface than Linux. It may
  admit particular components, but the complete OCR + LLM + Embedding profile is
  not accepted until all three runtimes work in one pinned cell.
- A Windows-local WSL path may provide the Linux runtime needed by components such
  as vLLM while remaining local from the user's product perspective. It is not
  equivalent to native Windows and requires its own driver, installation,
  filesystem, networking, GPU, shutdown, and recovery evidence.

One-click must fail with a precise unsupported-cell diagnosis when the target is
outside the compatibility manifest. It must never silently choose CPU, an external
API, or an SSH machine.

The volatile native Windows/Linux framework differences and first-party source
links are tracked in [AMD platform evidence](amd-platform-boundaries.md).

## Admission Evidence

Before claiming local one-click deployment:

- detect and record the exact supported local OS/GPU/gfx/driver/ROCm cell;
- prove OCR, LLM, and Embedding neural inference on that same local Radeon;
- prove fresh setup without an SSH daemon or manual endpoint configuration;
- prove local process-tree ownership, restart, occupied-port handling, crash
  cleanup, upgrade-blocked behavior, and monotonic removal;
- prove loopback-only exposure, memory-only bindings, settings registration, and
  no CPU/network fallback;
- package and test the exact native or WSL driver separately;
- show that the same capability/provider paths work unchanged for local and SSH
  placements.

The current no-AMD development machine can verify target-driver contracts and use
the SSH driver against Radeon Cloud. It cannot itself provide Local Radeon
acceptance. A fresh compatible Radeon Cloud instance may provide the Linux Local
cell only by running the product controller headlessly on the GPU host; that is a
separate baseline/role from an externally controlled Private SSH run and does not
prove native Windows, WSL, or Linux desktop packaging.
