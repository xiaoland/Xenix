# Xenix Knowledge OCR runtime

This subtree builds Xenix's optional Windows x64 OCR component over the pinned
official PaddleOCR C++ pipeline and Paddle Inference runtime. It is a release input,
not part of the desktop application's Python environment.

Run `pdm run build-knowledge-ocr` from a Developer PowerShell with the pinned MSVC
toolchain available. The build verifies every downloaded byte, applies the reviewed
compatibility patch, executes the real stdio protocol checks, and writes the
deterministic archive plus `runtime_catalog.json` under `dist/knowledge-ocr/`.

The application downloads only that Xenix-built archive from its configured release
origin. It never installs Python, pip, Paddle packages, or models on an end-user
machine.
