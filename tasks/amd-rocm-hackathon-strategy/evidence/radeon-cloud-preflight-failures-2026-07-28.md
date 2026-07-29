# Radeon Cloud Preflight Failures and Consequences — 2026-07-28

These failures occurred while preparing the exact
[Radeon Cloud runtime cell](radeon-cloud-rocm-runtime-2026-07-28.md). They are
retained because each changes the deployment design or diagnostic contract.

## Runtime Resolution

| Observation | Diagnosis | Implementation consequence |
| --- | --- | --- |
| The public PyTorch ROCm 7.2 index offered newer 2.13 builds | “Newest for ROCm 7.2” is not the same as AMD's certified Radeon 7.2.1 cell | Resolve an exact compatibility manifest before installing; keep certified PyTorch and vLLM compatibility cells separate |
| Stable vLLM targeted ROCm 7.2.3 | Host/runtime patch mismatch | Reject it for this cell; use the exact ROCm 7.2.1 nightly only as an experimental pinned cell |
| A vLLM dry run with global `--pre` selected unrelated alpha/RC dependencies | Pre-release admission widened the whole resolver | Pin the exact prerelease artifact without globally enabling prereleases |
| Auto-discovered AMD Quark failed to import a removed vLLM symbol | Third-party entry points expanded the runtime surface without being selected | Use a manifest-owned plugin allow-list; an empty list is safer than ambient discovery |
| `VLLM_USAGE_STATS_COLLECTION` was reported as unknown | Assumed environment variable was not part of this vLLM version | Validate runtime flags against installed code; use `VLLM_NO_USAGE_STATS=1` and `VLLM_DO_NOT_TRACK=1` |
| vLLM initially wrote compile artifacts under `/root/.cache/vllm` | Cache ownership was implicit | Set component/generation-owned config and cache roots |

## Acquisition and Storage

| Observation | Diagnosis | Implementation consequence |
| --- | --- | --- |
| Hugging Face mirror metadata led BGE-M3 to Xet CAS, which returned 401 | Mirror reachability did not imply Xet data-path authorization | Disable Xet for this cell and retain a normal LFS mirror path with exact revision/hash checks |
| Hugging Face primary timed out; GitHub route presented a self-signed certificate | Multiple upstream routes are not trustworthy/reachable in the same way | Keep bounded, pinned mirror policy and never disable TLS verification |
| A 5 MB lxml wheel took about 4m17s | Small byte count does not imply quick installation | Progress and timeout policy must distinguish resolver, transfer, verify, install, and first-compile phases |
| LOC ALTO schema returned HTTP 403 while PAGE remained reachable | Unrelated comparison schema blocked the leading PAGE check | Release validation must fetch only the selected profile's pinned schemas; do not put online schema access in inference readiness |
| `/workspace` is about 20 GiB while models plus runtimes exceed it | Persistent-candidate capacity cannot hold the complete current lab | Probe storage class/capacity before planning; keep acquisition cache, installed runtime, models, and durable evidence as separate quotas |

## Process and Tunnel Lifecycle

| Observation | Diagnosis | Implementation consequence |
| --- | --- | --- |
| Terminating a local SSH command left remote `uv` children running and holding a shared cache lock | SSH session lifetime did not own the remote task process tree | Every task needs deployment-owner incarnation, exact process group/start identity, bounded cancellation, and orphan reconciliation |
| A second install waited on the first task's shared cache lock | Cache/lock ownership was not generation-scoped | Use task/generation-specific caches and report lock owner/wait state explicitly |
| `ss` was absent; a port check inside a shell conditional did not fail under `set -e` | Tool availability and shell error semantics were assumed | Use a Python socket preflight with explicit exit status |
| The first local cleanup guard compared a composed command substring in the wrong order and refused cleanup | String-shaped process identity was brittle | Verify executable, host, and each forward independently; refusal is correct when identity cannot be proven |
| PID files survived as convenient observations | PID reuse/replacement can make them stale | A PID file never authorizes stop/reconnect; bind PID, process group, start ticks, command fingerprint, generation, and runtime incarnation |
| Developer-daemonized services became zombies after termination because container PID 1 did not reap them | `setsid` plus reparenting is not a process supervisor | Product execution must retain a reaping supervisor/control process or use a target service manager; shutdown completion checks both listener closure and terminal/reaped process state |
| Granite first health took about 76 seconds; BGE took about 43 seconds | Weight load and ROCm graph compilation dominate first readiness | Use phase-aware progress and deadlines; port-open is not model-ready |

## Capability Contracts

| Observation | Diagnosis | Implementation consequence |
| --- | --- | --- |
| BGE-M3 rejected `dimensions=1024` with HTTP 400 | Equal requested/actual dimension is still an unsupported Matryoshka override | Persist `None`, omit the wire field, and verify actual 1024 dimensions during self-test |
| The loopback spike accepted Xenix's Bearer header but did not enforce it | Loopback binding and SSH forwarding constrain exposure but are not application authentication | Decide authentication per placement; if enabled, generate/store capability-owned secrets without putting them in commands, logs, manifests, or provider URLs, and test unauthorized requests |
| RapidOCR defaults to ONNX Runtime CPU and `use_cuda=false` | Installing RapidOCR does not select ROCm | Exclude fallback runtimes, configure all three stages as Torch/CUDA, and attest stage parameter/input devices |
| RapidOCR's default recognition dictionary path points inside the installed package | Library cache ownership crosses deployment boundaries | Acquire dictionary as a manifest asset and pass an explicit generation-owned path |
| PAGE XSD rejects fractional points | RapidOCR produces floating-point polygons while PAGE uses integer coordinates | Declare and measure a coordinate quantization/inverse-mapping policy; never round silently |
| KServe V2 provides no standard server-side cancellation | Transport conformance does not bound remote work after disconnect | Add placement/request deadlines and orphan-work policy outside the wire dialect |
| Whole-device utilization reached 100% with three services resident | A global sample cannot attribute one stage | Combine device identity, model/input tensor assertions, process identity, and workload-correlated samples; do not use utilization alone |

## Design Conclusions

The preflight supports these concrete seams:

1. compatibility planning must finish before mutation and produce an immutable,
   exact runtime/model manifest;
2. acquisition, verification, installation, first compile, service publication,
   and capability registration are distinct forward phases;
3. the placement session owns remote processes, caches, loopback listeners,
   tunnels, and live incarnation—not provider settings;
4. capability self-tests own semantic wire assertions, such as Tool deltas,
   Embedding vector identity, and PAGE structure;
5. provider settings persist only generation-specific managed references;
6. diagnostics expose the failing phase and typed cause without attempting
   cross-domain rollback.

None of these failures justifies a public endpoint resolver, AMD inference gateway,
global settings service, or a rollback protocol.
