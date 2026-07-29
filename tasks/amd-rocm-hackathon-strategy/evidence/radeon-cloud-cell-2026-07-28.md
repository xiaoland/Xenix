# Radeon Cloud Cell Baseline — 2026-07-28

This evidence records a bounded, read-only probe of the currently assigned Radeon
Cloud Notebook cell. The public endpoint, SSH key path, host-key fingerprint, GPU
UUID/serial, and other access material are intentionally omitted. These observations
are facts about this cell, not guarantees made by Radeon Cloud and not Local Radeon
product acceptance.

## Result

The cell is suitable for the first Linux/ROCm workload experiments:

- SSH public-key authentication succeeds after the image's `sshd` is started.
- The container has one usable Radeon device exposed through `/dev/kfd` and
  `/dev/dri`; ROCm enumerates one GPU even though host PCI enumeration exposes
  additional physical devices.
- ROCm runtime initialization, device allocation, device memset, synchronization,
  and an 8 MiB device-to-host validation round trip all succeed.
- SSH local forwarding is enabled, so the cell can exercise the candidate Private
  SSH loopback-forward topology.

This read-only baseline alone does not prove PyTorch, OCR, LLM, Embedding, vLLM,
KServe V2, PAGE, or the Xenix headless journey. The subsequent
[ROCm runtime evidence](radeon-cloud-rocm-runtime-2026-07-28.md) records the
framework/model/protocol work performed after this baseline.

## Captured Cell

| Dimension | Observation |
| --- | --- |
| OS | Ubuntu 24.04.4 LTS |
| Kernel | Linux 6.8.0-79-generic, x86_64 |
| Assigned GPU count | 1 |
| GPU architecture | `gfx1100` / `gfx11-generic` |
| GPU silicon | Navi 31 XTW-C, PCI device `1002:744b` |
| Compute units | 96 |
| VRAM | 49,136 MB / 51,522,830,336 bytes, GDDR6, 384-bit |
| GPU power limit | 241 W maximum/socket limit reported |
| Driver | `amdgpu` 6.14.14 |
| ROCm | 7.2.1 |
| HIP | 7.2.53211 |
| AMD SMI | 26.2.2 |
| Python | CPython 3.12.3 |
| Visible CPU/memory | 128 logical CPUs and 1 TiB RAM; cell observation only |

The system includes the ROCm development/runtime libraries needed to begin
compatibility work, including HIP, rocBLAS, MIOpen, RCCL, rocSOLVER, and rocSPARSE.
`rocminfo`, `rocm-smi`, `amd-smi`, `hipcc`, and `rocm_agent_enumerator` are present.

## Runtime Smoke

A file-free Python `ctypes` probe loaded `libamdhip64.so` and performed:

1. `hipInit`;
2. `hipGetDeviceCount`, returning one device;
3. `hipMemGetInfo`;
4. an 8 MiB `hipMalloc`;
5. device `hipMemset`;
6. `hipDeviceSynchronize`;
7. `hipMemcpyDeviceToHost` and byte-for-byte validation;
8. `hipFree`.

The successful observation was:

```text
HIP_RUNTIME_SMOKE_OK devices=1 total_vram=51522830336
free_vram=51403292672 verified_bytes=8388608
```

This proves basic HIP runtime and memory-operation viability. It is not
workload-correlated neural inference evidence.

## Base Image and Storage

- No PyTorch, torchvision, torchaudio, vLLM, Transformers,
  sentence-transformers, PaddlePaddle, PaddleOCR, or ONNX Runtime distribution is
  installed in the base Python environment.
- Docker and Podman are absent. Git 2.43.0, CMake 3.28.3, Ninja 1.11.1, pip, and
  Python `venv` support are present.
- `/workspace` is a separate ext4 mount of approximately 20 GiB and was almost
  empty during the probe.
- `/` is a large container overlay with approximately 1.6 TiB free during the
  probe. Its capacity and lifetime must not be treated as persistent model storage.
- The platform's configured persistent-storage policy still needs confirmation
  before model artifacts are placed in `/workspace`.

The 20 GiB persistent candidate is a material constraint: the first LLM,
Embedding, and OCR model set must either fit with explicit headroom or use a
separately admitted storage layout.

## SSH Surface

The effective server configuration reports:

- public-key authentication enabled and password authentication disabled;
- root login restricted to non-password authentication;
- TCP forwarding enabled with `permitopen any`;
- `GatewayPorts no`.

This is compatible with developer SSH access and local-only port forwards. It does
not by itself prove product-owned host trust, process ownership, reconnect,
incarnation fencing, cleanup, or privacy behavior.

## Outbound Network

TLS-verified HEAD probes observed:

| Destination | Result |
| --- | --- |
| PyPI and `files.pythonhosted.org` | reachable |
| `download.pytorch.org` | reachable |
| `repo.radeon.com/rocm` | reachable |
| `hf-mirror.com` | reachable |
| ModelScope | reachable |
| Hugging Face primary domain | connection timeout |
| GitHub | self-signed certificate observed for the resolved route |

No deployment recipe may disable TLS verification to work around the GitHub
result. Artifact acquisition needs pinned sources, hashes, bounded retry, and a
tested mirror strategy; the primary Hugging Face domain cannot currently be the
only model source for this cell.

## Consequences

- Pin the first Private SSH manifest to this exact Ubuntu/ROCm/gfx cell rather than
  a generic “ROCm” label.
- Treat GPU assignment as one container-visible device, not as the host's physical
  PCI inventory.
- Make accelerator architecture explicit when building HIP artifacts; an anonymous
  stdin-only `hipcc` experiment did not provide a trustworthy implicit target.
- Budget all persistent model artifacts against the observed 20 GiB volume until
  a larger durable mount is verified.
- Keep model acquisition and runtime installation separate so mirrors and artifact
  hashes can change without changing capability protocols.
- Do not infer Local Radeon support, neural-model compatibility, inference
  performance, or contest completion from this baseline.
