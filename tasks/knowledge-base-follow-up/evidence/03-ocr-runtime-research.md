# Slice 03 Evidence — Local OCR Runtime Research

**State:** backend selected; compatibility spike complete; production integration implemented
**Researched:** 2026-07-22

## Question

How should Xenix provide reliable local Paddle-derived OCR on Windows without
installing Python, pip, PaddlePaddle, and PaddleOCR on the user's machine at runtime?

The desired `llama.cpp` analogy is interpreted as:

```text
one app-controlled native inference worker + independently versioned model files
```

It does not require embedding model weights inside the executable. `llama.cpp`
itself keeps its engine and GGUF model assets separate; OCR benefits from the same
separation because model changes should not require recompiling the engine.

## Required Properties

1. No Python interpreter, pip, wheel resolution, compiler, or user PATH mutation at
   deployment time.
2. One reproducible Windows x64 bundle produced in CI, with a fixed native dependency
   closure and third-party notices.
3. Model packs are explicit, versioned, hashed, and usable after restart without a
   network connection.
4. The OCR executor remains a child process with no SQLite, Artifact, canonical, or
   index publication authority.
5. One engine initialization serves every routed page in an import attempt. The
   current one-process-and-model-load-per-page behavior is not retained.
6. The protocol returns an engine-neutral result—text, confidence, and polygon—not
   PaddleOCR's library-specific nested JSON.
7. General text detection/recognition is the MVP capability. PP-StructureV3, table
   structure, formula, chart, or VLM support is not implied by the engine choice.

## Current Installation Evidence

The installed Python sidecar demonstrates that environment-variable redirection is
not a sufficient deployment contract:

- `%LOCALAPPDATA%\Xenix\cache\knowledge-ocr` contains about 1.01 GB across the
  embedded runtime, packages, downloads, and working directories;
- its configured `models` root contains only empty working directories and no model
  files;
- PaddleX downloaded about 139 MB of `PP-OCRv6_medium_det` and
  `PP-OCRv6_medium_rec` into `%USERPROFILE%\.paddlex\official_models`; and
- the legacy `active.json` still claims model readiness without identifying or
  verifying those external files.

Thus the sidecar was process-isolated but not actually model- or cache-isolated. A
native redesign must pass exact model paths to the engine and must never accept a
library-selected global cache as readiness evidence.

On 2026-07-22, Sir confirmed that this runtime had never shipped and directed that it
be deleted instead of migrated. The verified target
`%LOCALAPPDATA%\Xenix\cache\knowledge-ocr` contained 24,612 files, 3,866 directories,
and 1,011,680,056 bytes before deletion; it no longer exists. The operation did not
touch `%USERPROFILE%\.paddlex` or any SQLite, Artifact, canonical, vector, AI, ML, or
conversation state.

## Primary Sources and Reference Projects

### Official PaddleOCR C++ deployment

PaddleOCR documents a Windows C++ general-OCR pipeline that builds `ppocr.exe` and
supports text detection/recognition plus optional orientation/unwarping. Its Windows
runtime is not one physical file: the official instructions copy Paddle Inference,
`common`, Abseil, polygon clipping, and OpenCV DLLs next to the executable.

- [PaddleOCR C++ local deployment for Windows](https://www.paddleocr.ai/latest/en/version3.x/inference_deployment/local_inference/cpp/OCR_windows.html)
- [PaddleOCR C++ general OCR pipeline](https://www.paddleocr.ai/latest/en/version3.x/inference_deployment/local_inference/cpp/OCR.html)

This is the fidelity reference because it consumes official Paddle inference models
without conversion. Sir selected it as Xenix's target backend. Xenix accepts its
larger native dependency closure in exchange for official model compatibility and
will absorb build/upgrade complexity in CI rather than on the user's machine.

## Executed Native Compatibility Spike

The authorized disposable spike ran on Windows x64 with Visual Studio Build Tools
2022. It used only ignored files under `build/knowledge-ocr-spike`; no product source,
packaging path, database, or active runtime was changed.

Pinned inputs and the observed compatible baseline are:

| Input | Identity | Evidence |
| --- | --- | --- |
| PaddleOCR | `v3.7.0`, commit `b03f46425e8ff4442b268ce449e3eef758146cd4` | Official `deploy/cpp_infer` source built with MSVC x64. |
| Paddle Inference | `3.3.0` CPU AVX/MKL VS2019 package | Official `3.0.0` Windows package could not load the PP-OCRv6 recognition graph; `3.3.0` loaded both exact models. |
| OpenCV | `4.7.0` Windows x64 | Version used by the official Windows C++ instructions. |
| Detection model | `PP-OCRv6_medium_det_infer`, SHA-256 `144d0621e059566e5086e228829171591c144c2deb07b2dad4962214fbabfcf7` | Official 62,279,680-byte model archive. |
| Recognition model | `PP-OCRv6_medium_rec_infer`, SHA-256 `4eecc1c6a4623765042e6fc15446da0da110b7d875b6b72b2d351d2b2dbd4da6` | Official 76,851,200-byte model archive. |

The upstream C++ sample is not usable unchanged with that model pack. The PP-OCRv6
detection `inference.yml` represents `DetResizeForTest` as null, while PaddleOCR
`v3.7.0` unconditionally calls `pre_tfs.at("DetResizeForTest.resize_long")`. The
uncaught `std::out_of_range` terminates as Windows status `0xc0000409`. A disposable
three-line guard that preserves the processor's existing default made the detection
model and full OCR pipeline succeed. Phase B must carry this as an explicit,
reviewable pinned-source patch or implement the equivalent validation in Xenix's
adapter; it must not depend on an undocumented local edit.

The fixed end-to-end run on Paddle Inference `3.3.0`:

- returned 34 Chinese/English text regions from the official boarding-pass image,
  including names, flight/date, gate, ticket number, and the closing-time notice;
- completed a cold detection-only invocation in 8.6 seconds and a cold full OCR
  invocation in 19.1 seconds on the development machine;
- peaked at 621,432,832 bytes working set and 599,519,232 bytes private memory;
- ran offline with explicit model paths and no Python, pip, global Paddle cache, or
  PATH mutation; and
- produced ten complete JSON/image results in one official CLI process, but the
  process did not exit before the 180-second harness deadline. The CLI buffers its
  model-init log, so this is not accepted as the Phase B persistent-protocol test.

The verified runtime closure contains 11 files and is larger than the PE import table
alone suggests. `mklml.dll` is loaded dynamically and is required even when oneDNN is
disabled; omitting it fails at runtime. `vcomp140.dll` must come from the pinned MSVC
OpenMP redistributable rather than being assumed present in `System32`. The observed
sizes are:

| Payload | Uncompressed bytes |
| --- | ---: |
| Native executable and required DLL closure | 349,530,496 |
| Detection and recognition model pack | 139,110,993 |
| Combined | 488,641,489 |

A normal ZIP of that exact spike closure is 206,681,033 bytes. This is sizing
evidence, not the release artifact: the Phase B build must emit its own deterministic
archive, complete file manifest, hashes, licenses, and catalog.

The spike therefore passes the engine/model compatibility gate and confirms the
unpack-and-run archive shape. It also turns four items into explicit Phase B work:

1. pin and hash every CMake dependency instead of allowing PaddleOCR's configure step
   to download floating Abseil, Clipper, nlohmann-json, or `dirent.h` inputs;
2. own the optional-`resize_long` compatibility patch and error normalization;
3. generate the DLL closure from build evidence plus runtime load tests, including
   dynamic dependencies such as MKL and the MSVC OpenMP redistributable; and
4. prove ten requests, one model initialization, bounded cancellation, and clean
   shutdown through Xenix's actual stdio protocol rather than the upstream CLI.

### PaddleOCR-json and Umi-OCR

PaddleOCR-json is the closest mature product-shape reference: an offline executable
is started as a child process or TCP service, receives image requests, and emits JSON.
It is unpack-and-run and is used by Umi-OCR's plugin architecture.

- [PaddleOCR-json](https://github.com/hiroi-sora/PaddleOCR-json)
- [Umi-OCR plugin bundles](https://github.com/hiroi-sora/Umi-OCR_plugins)

Its architecture is worth copying; its binary is not the recommended Xenix
dependency. The current public stable line is based on older PP-OCR/Paddle Inference,
documents a roughly 369 MB deployed footprint and 2 GB memory allowance, requires
AVX, and does not support table recognition. Its own release notes retained Paddle
Inference 2.3.2 after instability encountered with 3.0.

### RapidOCR and native variants

RapidOCR validates converting PaddleOCR models to ONNX and using smaller,
cross-platform inference runtimes. The current main project is Apache-2.0 and supports
ONNX Runtime, OpenVINO, MNN, Paddle, TensorRT, and PyTorch. Its standalone C++ variants
demonstrate executable/DLL builds and separately supplied model folders.

- [RapidOCR](https://github.com/RapidAI/RapidOCR)
- [RapidOcrNcnn](https://github.com/RapidAI/RapidOcrNcnn)
- [RapidOcrCpp](https://github.com/RapidAI/RapidOCRCpp)

The references are not adopted blindly. `RapidOcrNcnn`'s latest public release is
from 2023 and its documented models are PP-OCRv3; `RapidOcrCpp` describes incomplete
Windows/MT support. The active Python project and model catalog are much newer than
those C++ ports.

### ONNX Runtime

Microsoft supplies official CPU C/C++ Windows artifacts, release `.zip` assets, and a
stable C API with the runtime DLL colocated with the application. A reduced custom
build can include only operators required by the selected models. PaddleOCR itself
documents exporting Paddle models to ONNX.

- [ONNX Runtime C++ builds](https://onnxruntime.ai/docs/get-started/with-cpp.html)
- [ONNX Runtime Windows deployment](https://onnxruntime.ai/docs/get-started/with-c.html)
- [PaddleOCR ONNX model export](https://www.paddleocr.ai/v3.5.0/en/version3.x/deployment/obtaining_onnx_models.html)

## Candidate Matrix

| Candidate | Deployment stability | Paddle model fidelity | Runtime footprint potential | Maintenance risk | Decision |
| --- | --- | --- | --- | --- | --- |
| Runtime Python + pip | Low | High | Poor | High, dependency graph resolves on user machine | Reject target design. |
| PyInstaller/Nuitka Python executable | Medium-low | High | Poor | Still embeds the same Python/import graph and opaque model downloads | Reject as final design. |
| Official Paddle Inference C++ | Medium-high after CI build | Highest | Medium-poor; several DLLs/OpenCV | Medium-high native closure | **Selected by Sir.** Xenix owns the thin worker and CI-produced closure. |
| ONNX Runtime C++ | High | Must be measured after conversion | Good; one principal runtime DLL, reducible build | Medium; Xenix owns pre/post-processing | Rejected for this slice; retained only as a research fallback if a new handshake is needed. |
| ncnn C++ | High once built; can be static | Must be measured after conversion | Best; closest to a true single executable | Higher model/operator and stale-reference risk | Conditional fallback if ORT footprint/startup misses target. |
| PaddleOCR-json binary | High unpack-and-run product shape | Older PP-OCR line | Poor-medium | External release/model age | Architecture reference only. |

## Recommended Runtime Design

### Distribution

```text
cache/knowledge-ocr/
├─ bundles/
│  └─ <bundle-id>/
│     ├─ xenix-ocr.exe
│     ├─ paddle_inference.dll
│     ├─ opencv and required Paddle dependency DLLs
│     ├─ runtime.json
│     └─ THIRD_PARTY_NOTICES.txt
├─ model-packs/
│  └─ <model-pack-id>/
│     ├─ PP-OCRv6_medium_det/
│     ├─ PP-OCRv6_medium_rec/
│     ├─ dictionary.txt
│     └─ models.json
├─ staging/
└─ active.json                    # small atomic pointer, not readiness authority
```

Xenix downloads one pinned archive per platform/model pack, verifies the outer digest
and manifest file digests, extracts to staging, runs a self-test, atomically activates
the complete generation, and only then retires the previous generation. The worker
never downloads dependencies or models on demand.

For MVP, the app may distribute one archive containing both runtime and default
Chinese/English mobile models. They remain logically separate identities even when
delivered together.

### Execution lifecycle

```text
spawned Knowledge import worker
  -> starts xenix-ocr.exe --stdio once when the first page needs OCR
  -> initialize(model-pack-id)
  -> recognize(page 1)
  -> recognize(page 4)
  -> recognize(page 7)
  -> shutdown
```

The process stays scoped to one import attempt, so model initialization is amortized
without creating a cross-task daemon or moving publication authority. Cancellation
closes stdin, waits a bounded grace interval, then terminates the native child.

Minimum protocol operations:

```text
version    -> protocol, engine, engine_version, build_id, platform, architecture
self_test  -> bounded pass/fail + safe reason code
initialize -> exact model-pack identity
recognize  -> request_id + regions[{text, confidence, polygon}]
shutdown
```

Transport should be length-delimited JSON over stdin/stdout or bounded request/result
files. Raw diagnostic stderr is never copied to user-visible logs or SQLite.

### Status and repair

- Workspace fast path reads the active manifest and cached last verification only.
- Full executable/model hash verification and `self_test` run after activation, on an
  explicit repair, or asynchronously when a stale/error state requires it—not on
  every Workspace paint.
- `not_installed` means no active bundle. A valid prior bundle with a newer required
  protocol is `repair_required`, not absent.
- The Python sidecar was never released. Sir authorized deleting its complete
  Xenix-private cache before the native spike, so no product adoption or migration
  branch is required. Global `%USERPROFILE%/.paddlex` remains untouched.

## Phase B Follow-through

The subsequent product implementation retained the selected engine and produced the
Xenix worker, persistent protocol, deterministic archive/catalog, verified native
dependency closure, activation state machine, and release integration. Ten requests
through one initialized session, clean shutdown, corrupt/mismatched bundle rejection,
and a real install/activate/offline-recognize path now pass. See
[native runtime implementation evidence](03-native-runtime-implementation.md).

No fallback backend, older model, or third-party binary was substituted.

## Recommendation

Proceed with an **official Paddle Inference C++ Xenix-owned worker**. Preserve the
stable process/JSON plugin shape demonstrated by PaddleOCR-json/Umi-OCR, but build the
worker and its pinned dependency closure in Xenix CI. Deliver one verified archive
containing the executable, required DLLs, default model pack, and notices; never run
Python/pip or download Paddle/model dependencies dynamically on the user's machine.

Do not couple this choice to PP-StructureV3. The current Xenix Paddle worker performs
general OCR only, and official PP-StructureV3 guidance remains centered on the
integrated Python pipeline. A later structured-document backend should be admitted as
a separate capability and may use a different local or remote executor.
