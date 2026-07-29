# ROCm OCR Options

This file owns the research-time comparison for running Xenix OCR model inference
through ROCm. The supplied Linux Radeon Cloud cell is the first available target.
Local Radeon is a peer product placement, but native Windows, WSL, and Linux local
cells each require separate acceptance. This records candidate evidence, not an
accepted replacement for ADR 0009.

## Required Meaning

For this task, “ROCm OCR” means:

- both text-detection and text-recognition neural inference execute through a
  PyTorch/HIP or another evidenced ROCm backend on the declared Radeon;
- framework identity, `torch.version.hip` or equivalent backend identity, selected
  AMD device, model tensor placement where observable, and a correlated workload
  signal are captured;
- CPU image decoding, resizing, box processing, text decoding, and other
  non-neural postprocessing remain allowed and are reported honestly;
- a missing operator or failed device path does not silently run model inference on
  CPU while the product reports AMD readiness.

## Available Target Constraint

The exact Radeon Cloud GPU, OS, driver, ROCm, framework, and operator cell is not
promised by the guide and must be captured. PyTorch/HIP is the leading first probe
because it gives one implementation route for both a controlled OCR pair and
EasyOCR while preserving explicit device evidence.

AMD admits PyTorch ROCm wheels for selected Windows Radeon/gfx cells, making a local
native OCR experiment credible. Its limitations state that only PyTorch—not the
rest of the ROCm stack—is currently available, so this does not admit the complete
local OCR/LLM/Embedding profile:

- <https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html>
- <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/limitations/limitationsrad.html>
- <https://rocm.docs.amd.com/en/develop/about/release-notes.html#ai-ecosystem-support>

PyTorch intentionally uses the `torch.cuda` API for HIP devices. A valid proof must
combine `torch.version.hip`, device availability/name, actual model/tensor device,
and workload evidence:

- <https://docs.pytorch.org/docs/main/notes/hip.html>

TheRock characterizes native Windows support and PyTorch source builds as relatively
new and not yet mature. This is a future compatibility fact, not a reason to block
the first Linux cloud spike:

- <https://github.com/ROCm/TheRock/blob/main/docs/development/windows_support.md>

## Candidate Matrix

| Candidate | ROCm status | Decision |
| --- | --- | --- |
| EasyOCR on captured PyTorch ROCm | PyTorch-based with explicit simplified-Chinese models, but EasyOCR makes no AMD/ROCm support claim | First end-to-end Chinese cloud spike |
| Controlled standard-PyTorch detector + recognizer | PyTorch/HIP is credible; suitable Chinese architectures, weights, and operators still need selection | Most controlled product candidate after platform and quality probes |
| docTR PyTorch detector + recognizer | PyTorch-capable, but neither docTR nor AMD documents this ROCm OCR stack and no built-in Chinese pretrained product path was found | Operator/backend comparator only unless Chinese weights and vocabulary are supplied |
| Paddle Inference with ROCm | Official material is source-built Linux with an old, narrow MI100/CentOS/ROCm matrix; it does not establish the supplied Radeon cell | Do not use as the first ROCm route |
| ONNX Runtime ROCm EP or MIGraphX EP | ROCm EP was removed in ONNX Runtime 1.23; MIGraphX is Linux but exact Radeon/model/operator support still needs a captured cell | Defer behind the simpler PyTorch probe |
| Paddle/ONNX through DirectML | Can use AMD hardware through DirectX 12 on Windows | Future compatibility experiment only; never label ROCm |
| VLM OCR through vLLM | AMD's OCR tutorial is Linux/Instinct; output is generated text rather than the accepted deterministic region contract | Defer as a separate multimodal product decision |
| VLM OCR through PyTorch Transformers | The framework might execute through ROCm, but OCR quality/VRAM/latency and result semantics differ | Defer as a separate multimodal product decision |

## Source Notes

Paddle Inference:

- AMD/DCU support is documented as source compilation with Linux ROCm wheels and a
  narrow MI100/CentOS/ROCm 4.5.2 cell:
  <https://www.paddlepaddle.org.cn/inference/v3.0/guides/hardware_support/dcu_hygon_cn.html>.
- The official Windows build path documents NVIDIA CUDA for GPU builds and CPU
  otherwise:
  <https://www.paddlepaddle.org.cn/documentation/docs/en/install/compile/windows-compile_en.html>.

PyTorch OCR libraries:

- EasyOCR explicitly documents PyTorch execution and simplified-Chinese use, but
  makes no ROCm support statement:
  <https://github.com/JaidedAI/EasyOCR>.
- docTR documents a two-stage detector/recognizer design and recommends its
  PyTorch backend, but makes no AMD/ROCm support statement. Its published vocabulary
  table must not be assumed to include a Chinese product model:
  <https://mindee.github.io/doctr/v0.12.0/getting_started/installing.html> and
  <https://mindee.github.io/doctr/latest/getting_started/quickstart.html> and
  <https://mindee.github.io/doctr/latest/modules/datasets.html#supported-vocabs>.

ONNX Runtime:

- The removed ROCm EP directs users to MIGraphX:
  <https://onnxruntime.ai/docs/execution-providers/ROCm-ExecutionProvider.html>.
- MIGraphX EP packages and prerequisites are Linux/Ubuntu:
  <https://onnxruntime.ai/docs/execution-providers/MIGraphX-ExecutionProvider.html>.
- DirectML is a Windows DirectX 12 provider for several vendors and is in sustained
  engineering. It is an AMD-GPU option, not ROCm evidence:
  <https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html>.

VLM:

- AMD's vLLM OCR example was validated on Ubuntu and Instinct MI300X:
  <https://rocm.docs.amd.com/projects/ai-developer-hub/en/v5.0/notebooks/inference/ocr_vllm.html>.
- vLLM requires Linux and does not support Windows natively:
  <https://docs.vllm.ai/en/latest/getting_started/installation/gpu/>.

## Recommended Spike Order

1. Capture the assigned Radeon Cloud GPU/gfx, Linux, driver, ROCm, Python, PyTorch,
   and torchvision cell.
2. Verify HIP identity and representative convolution, attention, resize, AMP, and
   dynamic-shape operations without third-party OCR code.
3. Run EasyOCR's simplified-Chinese detector and recognizer, first FP32 and then
   FP16 where safe, to obtain the fastest relevant end-to-end quality signal.
   Override `model_storage_directory` to a spike-owned isolated cache outside the
   repository/task packet, prefetch and hash the detector/recognizer weights, record
   their licenses, and set `download_enabled=False` for the evidence run.
4. Compare fixed Chinese image and scanned-PDF fixtures against the accepted Paddle
   output for text, regions, confidence behavior, latency, and memory.
5. Isolate or select a controlled standard-PyTorch Chinese detector/recognizer pair
   with immutable weights and no custom CUDA/Triton extensions. Use docTR only as an
   additional operator/backend comparator unless a suitable Chinese model is
   supplied.
6. Wrap the candidate behind the locally exercised KServe V2 Binary Tensor
   transport and a PAGE-only, single-image, version-pinned profile; retain ALTO 4.4
   as comparison evidence. Exercise line hierarchy, inverse coordinate mapping,
   quantization error, decoded/XML resource limits, typed process/transport failure,
   local cancellation plus bounded remote work, SSH forwarding, staging, and
   cleanup from both the desktop-local controller and Private SSH boundary.
7. Decide whether the evidence justifies a new OCR ADR. Until then, keep Paddle as
   the accepted compatibility implementation.

## Admission Gate

A ROCm OCR candidate is not eligible for an AMD execution profile until it:

- satisfies an explicit Chinese correctness threshold on product fixtures;
- demonstrates both detector and recognizer model execution on ROCm with no silent
  fallback;
- has compatible licenses and immutable model/runtime provenance;
- preserves the current engine-neutral OCR result contract;
- can be staged or packaged, installed, self-tested, published, repaired through
  forward reconciliation, and removed monotonically on the declared private SSH
  or Local Radeon target with the same rigor as the current bundle;
- passes the standards-first gate in
  [OCR protocol options](ocr-protocol-options.md) without requiring a local
  ROCm-specific adapter;
- receives a durable decision that explicitly amends or supersedes ADR 0009 while
  preserving Paddle as the compatibility profile.
