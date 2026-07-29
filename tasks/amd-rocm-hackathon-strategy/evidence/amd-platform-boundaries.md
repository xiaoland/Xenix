# AMD Platform and Repository Evidence

This file records volatile first-party platform facts and repository observations.
It does not turn either into product scope.

## First-Party AMD Boundary

As reviewed on 2026-07-26:

- ROCm 7.14 is a production Core SDK release. Exact library, framework, GPU, and OS
  support still varies and must be checked in the matching compatibility table and
  release notes. The 7.14 AI ecosystem table lists a current PyTorch version for
  Windows while vLLM, MIGraphX, and ONNX Runtime entries remain Linux:
  <https://rocm.docs.amd.com/en/docs-7.14.0/about/release-notes.html>.
- The supplied Radeon Cloud guide guarantees a Linux development entry through
  JupyterLab and optionally SSH, plus OpenAI-compatible Model APIs and one-port
  `rc-tunnel`. It does not promise the exact compute cell or any graphical desktop:
  <https://github.com/AMD-DEV-CONTEST/Radeon-hackathon-2026-07/blob/main/Radeon-Cloud-User%20Guide/README.md>.
- AMD's Windows PyTorch selector publishes ROCm 7.14 wheels for declared Radeon/gfx
  cells, so a native PyTorch ROCm OCR spike is credible. That wheel is not evidence
  that an OCR library, model, or the rest of ROCm is supported:
  <https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html>.
- AMD's Radeon/Ryzen limitations still expose a substantially narrower native
  Windows surface than Linux: PyTorch is available, while the rest of the ROCm stack
  is Linux-only in that support statement:
  <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/limitations/limitationsrad.html>.
- TheRock's Windows source-support document additionally marks native Windows and
  PyTorch work as relatively new and not mature, with ROCr, `rocminfo`, AMD SMI, and
  ROCprofiler unavailable there. Product attribution therefore needs
  framework/device/workload evidence rather than Linux-only tools:
  <https://github.com/ROCm/TheRock/blob/main/docs/development/windows_support.md>.
- AMD's Radeon/Ryzen compatibility tables must still bind the exact OS, Radeon,
  gfx, driver, PyTorch, Python, and ROCm combination:
  <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html>.
- AMD publishes validated Radeon `llama.cpp` prebuilt binaries for Windows and
  Linux. The current Radeon guide's downloadable desktop bundle is tied to ROCm
  7.2.1 and therefore does not by itself prove a 7.14 product combination:
  <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/advanced/advancedryz/windows/llm/llamacpp.html>.
- vLLM on ROCm is a Linux inference-server path. A developer-started Notebook/SSH
  process is initially development and contest evidence; reusing it behind a
  product-managed `AmdAiDeploymentService` remains a separately gated lifecycle
  decision. The
  Dedicated Model API is a different optional provider:
  <https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/inference/vllm.html>.
- ONNX Runtime removed its former ROCm Execution Provider in 1.23 and directs ROCm
  users toward MIGraphX. A generic Windows DirectML fallback would not be a ROCm or
  AMD-specific claim:
  <https://onnxruntime.ai/docs/execution-providers/ROCm-ExecutionProvider.html>.
- Linux AMD SMI and ROCprofiler evidence can attribute utilization and kernel work
  to an AMD GPU. Native Windows and WSL require different evidence routes; a
  provider name alone is insufficient:
  <https://rocm.docs.amd.com/projects/amdsmi/en/latest/index.html>.

These are research-time facts. An implementation decision must pin the actual
artifact versions and rerun the compatibility review.

## Repository Evidence

- Product truth keeps conversations, datasets, models, Knowledge, and artifacts
  authoritative on the desktop. Local or SSH execution may provide
  runtime/cache/process/transient-request capacity only.
- `LLMService` and `EmbeddingService` already use independent OpenAI-compatible
  boundaries.
- `OpenAICompatibleChatProvider` currently expects a non-empty API key; a managed
  loopback runtime needs an explicit local credential policy rather than a hidden
  placeholder.
- The OCR manifest validation fixes the existing engine and architecture to Paddle
  Inference on Windows x64 and records runtime/model/protocol identities.
- Official Paddle Inference ROCm material is a source-built Linux-era path and does
  not establish the supplied Radeon Cloud cell or a native Windows Radeon runtime.
  A complete AMD execution profile therefore needs a separately deployed OCR
  service and engine-neutral client, on either an admitted Local Radeon or Private
  SSH target, rather than relabeling the current bundle or adding a
  `RocmOcrAdapter`.
- ML worker configuration has a `capabilities` field, but current selection does not
  use it. That is relevant to future batch ML acceleration, not evidence that the
  pool should own reusable OCR/model processes or SSH tunnels.
- The rainy-season benchmark already supplies an outcome-bearing, source-linked
  business scenario suitable for AMD acceptance.
- The lack of a local Radeon test machine is an evidence limitation, not a sound
  reason to encode SSH into the deployment facade. Native Windows, WSL, and Linux
  local targets remain separate compatibility cells.

The detailed candidate comparison and source links are in
[ROCm OCR options](rocm-ocr-options.md).
The concrete repository abstractions and leaks are in
[current adapter seams](current-adapter-seams.md).

## Evidence Classification

- **Official support:** only claims made by the matching AMD/ROCm compatibility or
  release documentation.
- **Observed integration:** facts reproduced on the exact assigned Radeon Cloud
  cell or a test machine.
- **Product acceptance:** behavior reproduced through the packaged Xenix product on
  a declared supported Radeon configuration.
- **Proposal:** every topology, model choice, fallback, or deployment state not yet
  authorized and implemented.
