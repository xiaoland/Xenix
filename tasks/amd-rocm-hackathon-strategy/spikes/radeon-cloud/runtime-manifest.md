# Radeon Cloud Runtime Manifest

This is the reproducibility record for the 2026-07-28 `gfx1100`, Ubuntu 24.04.4,
ROCm 7.2.1 development cell. It is evidence for one cell, not a generic support
matrix.

## Certified PyTorch Base

AMD's Radeon compatibility cell was preserved in its own environment:

| Component | Runtime version | Wheel SHA-256 |
| --- | --- | --- |
| PyTorch | `2.9.1+rocm7.2.1.gitff65f5bc` | `fb45ace0a27e9f0d0e3c4c6efd8932162743f8376f2aa4752a4d31ef5a1bd3d7` |
| torchvision | `0.24.0+rocm7.2.1.gitb919bd0c` | `d5fca8cda173235a3b7434baeebe04c3ebffec3c6fc191e79aa8aa300633f2c9` |
| torchaudio | `2.9.0+rocm7.2.1.gite3c6ee2b` | `023d1ce5d847b2a0fbebacf52d35b4c7a233ca07b3dbd0f1cbde84362cbcf33d` |
| Triton | `3.5.1+rocm7.2.1.gita272dfa8` | `07787af1d28c273852f897bfeaa7bca29f2fa4a13ca0f28f535832b240ce7016` |

Python is 3.12.3 and NumPy is pinned to 1.26.4. The environment lives at
`/opt/xenix-rocm-lab/envs/torch-rocm721-certified`. It passed FP16 GEMM and
convolution on `gfx1100`.

## vLLM Compatibility Cell

The current stable vLLM ROCm wheel targeted ROCm 7.2.3, not this host. The selected
ROCm 7.2.1 nightly wheel is therefore a separate experimental compatibility cell:

| Component | Version |
| --- | --- |
| vLLM | `0.20.2rc1.dev15+g321fa2d6d.rocm721` |
| bundled PyTorch | `2.10.0+git8514f05` |
| torchvision | `0.24.1+d801a34` |
| torchaudio | `2.9.0+eaa9e4e` |
| Triton | `3.6.0` |
| Transformers | `5.14.1` |
| amd-aiter | `0.1.10.post3` |
| flash-attn | `2.8.3` |

Wheel:

```text
vllm-0.20.2rc1.dev15+g321fa2d6d.rocm721-cp312-cp312-manylinux_2_34_x86_64.whl
sha256=a0834d6dc4244f6f87aa39d8a66f3942377dea8aaa80bdd5e4d71433ba486acf
```

The runtime is isolated at
`/opt/xenix-rocm-lab/envs/vllm-rocm721-nightly`. Both services use:

```text
VLLM_PLUGINS=
VLLM_NO_USAGE_STATS=1
VLLM_DO_NOT_TRACK=1
VLLM_ROCM_USE_AITER=0
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

Each service also owns a distinct `VLLM_CACHE_ROOT` and `VLLM_CONFIG_ROOT`. The
empty plugin allow-list avoids an incompatible auto-discovered AMD Quark plugin.
AITER is not selected on `gfx1100`; observed attention selection was `ROCM_ATTN`.

## Models

| Capability | Repository / revision | Size | License |
| --- | --- | ---: | --- |
| Chat | `ibm-granite/granite-3.1-8b-instruct@4009206d5fc95d2e65a7b7633e159d6e97e25d35` | 16,346,499,089 bytes | Apache-2.0 |
| Embedding | `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181` | about 2.2 GB | MIT |
| OCR | RapidOCR 3.9.2 PP-OCRv6 small Torch assets | about 34 MB | Apache-2.0 |

Granite weight hashes:

| File | SHA-256 |
| --- | --- |
| `model-00001-of-00004.safetensors` | `191c4e9c6263d9cf591104f2d16ab2c39dcc43c1ad0680cc5a34d5c86d61ee41` |
| `model-00002-of-00004.safetensors` | `c7c38b0d5a436775b09d764465ed6e6eb7a8c4e302d05e301e151c96e3076f22` |
| `model-00003-of-00004.safetensors` | `f02784b72391fa04e9b986313c1a1720ce88f0eb40f7ae81fa0daadc93049457` |
| `model-00004-of-00004.safetensors` | `9d86d201ff8e73d8a46e92b543c9dd44f133e60b35ccada4a76439af62f22212` |

BGE-M3 PyTorch weight:

```text
pytorch_model.bin
sha256=b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38
```

RapidOCR assets:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `PP-OCRv6_det_small.pth` | 10,248,727 | `fbdc74c97ea7b770ab22cbdc1bba01a52bdf1975efcf3442057356d622b05d54` |
| `ch_ptocr_mobile_v2.0_cls_mobile.pth` | 588,638 | `bfe13860824b3365c0c7f7ccfcddc8ff11645c60051739ff18bc9913f60c98e1` |
| `PP-OCRv6_rec_small.pth` | 21,326,017 | `0107b2ad694ccc9b1db7cf9ed3ffbc93d1795d9e08d9cf823127243a87bce516` |
| `ppocrv6_dict.txt` | 74,947 | `b5f2bfe2bdd9448429e3e82b51c789775d9b42f2403d082b00662eb77e401c5d` |
| `FZYTK.TTF` | 3,241,748 | `4065a23df6823c8e2b69a0e76d02f02a6470b8774a5e91086609701ad95cc33f` |

The OCR environment pins RapidOCR 3.9.2, certified PyTorch/Triton, NumPy 1.26.4,
OpenCV 4.11.0.86, Pillow 12.3.0, and Shapely 2.1.2. ONNX Runtime, Paddle,
OpenVINO, and TensorRT are intentionally absent.

## Service Parameters

Chat:

```text
dtype=float16
max_model_len=8192
gpu_memory_utilization=0.65
enable_auto_tool_choice=true
tool_call_parser=granite
```

Embedding:

```text
runner=pooling
dtype=float16
max_model_len=8192
gpu_memory_utilization=0.20
served_model_name=bge-m3
dimensions must be omitted
```

OCR:

```text
Det.engine_type=torch
Cls.engine_type=torch
Rec.engine_type=torch
EngineConfig.torch.use_cuda=true
device_id=0
```

All service listeners bind the remote loopback interface only. Model acquisition
used the Hugging Face mirror with Xet disabled and exact revisions, or versioned
ModelScope URLs with recorded hashes. TLS verification was never disabled.
