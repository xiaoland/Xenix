# Space Usage Diagnosis

## Objective

Explain why the workspace occupies approximately 38.1 GB and identify evidence-backed, recoverable reclamation candidates.

## Guardrails

- Read-only diagnosis; do not delete, rebuild, or alter tracked or generated artifacts.
- Do not infer that any generated file is disposable until its producer and purpose are established.

## Verification

- Account for the reported workspace total through reproducible directory and file-size measurements.
- Distinguish sources, caches, build outputs, dependencies, and runtime state.

## Current Truth

- Logical file total: 38.182 GiB (40,997,138,548 bytes), consistent with the
  reported 38.1 GB.
- `build/` is 21.17 GiB. `build/knowledge-ocr/` retains five UUID workspaces
  (1.48–4.00 GiB each), and `build/knowledge-ocr-spike/` adds 4.21 GiB.
  The OCR build script creates a fresh workspace for every run and does not
  remove it after a successful build.
- The custom runtime home `.runtime/dev/` is 6.96 GiB: artifacts and state
  may be application-owned data, while its 1.10 GiB OCR cache is rebuildable.
- `dist/` is 4.83 GiB of packaging and OCR output; `.venv/` is 2.83 GiB.
  `temp/ocr-verification-home/` retains 0.94 GiB of OCR cache.
- No cleanup was performed. `build/`, `dist/`, `.runtime/`, `.venv/`, `temp/`,
  and `.tmp/` are Git-ignored local areas; `tasks/` is not Git-ignored.
- At the user's direction, `build/`, `temp/ocr-verification-home/`, and
  `.mypy_cache/` were deleted. `.tmp/` was reduced to an empty `pytest/`
  directory; its ACL denies deletion to the current user. The logical total is
  now 15.662 GiB, a 22.520 GiB reduction.

## Next Step

- Await direction on the empty ACL-protected `.tmp/pytest/` directory, or on a
  proposal to make OCR builds remove their completed workspaces automatically.
