# Self-Contained Native OCR Runtime

## Objective

Replace the provisional external `OCR.yaml` repair with a self-contained
`xenix-ocr.exe` whose fixed Xenix pipeline configuration is compiled into the
worker, and prove that the released runtime neither reads build/source-tree
resources nor exposes the real builder checkout path.

## Guardrails

- Keep the two Paddle inference model directories and their model-owned
  `inference.yml` files external; only the Xenix-owned pipeline composition and
  defaults move into the worker.
- Express the embedded pipeline through PaddleOCR's supported
  `PaddleXConfigVariant` map interface. Do not fork or reimplement inference
  algorithms.
- Preserve the pinned PaddleOCR commit, Paddle Inference/model inputs, runtime
  and model-pack identities, runtime manifest schema 1, and native protocol 2
  unless implementation evidence proves a contract change is unavoidable. Any
  such change returns to an Impact Handshake before mutation.
- The worker must not depend on process CWD, executable location, a companion
  pipeline YAML, environment variables, repository layout, or the PaddleOCR
  source checkout.
- The embedded values must be traceable to the pinned upstream `OCR.yaml`;
  Xenix-specific overrides must remain explicit and covered by behavioral proof.
- Remove the provisional archive-owned `OCR.yaml`, relative-path initialization,
  source-config rename verification, and their obsolete documentation/tests.
- Sanitize third-party `__FILE__` expansion so released binaries contain no real
  local or GitHub Actions checkout path in ASCII or UTF-16LE form. A deterministic
  virtual source label is acceptable for diagnostics.
- Preserve unrelated worktree changes. Do not modify installed application state,
  active OCR generations, branches, commits, or published releases.
- Do not expose imported document contents in diagnostic or verification output.

## Verification

- Focused tests prove the embedded map contains every pipeline key required by
  PaddleOCR for Xenix's enabled detection/recognition topology and preserves the
  intended thresholds, limits, batch sizes, model names, and disabled optional
  sub-pipelines. Compare the effective flattened key/value map after Xenix
  overrides, not the YAML file's textual representation.
- A fresh native build produces an archive with no pipeline `OCR.yaml`; its
  manifest and member hashes remain valid, and the archive contains only
  `runtime.json` plus the worker, model, dependency, notice, and license assets
  required at runtime.
- Extract the fresh archive into an independent consumer directory, make the
  entire builder PaddleOCR checkout unavailable, and launch the real worker with
  a different empty CWD containing a deliberately invalid `OCR.yaml`.
- In that isolated topology, the real worker must pass `version`, `initialize`,
  `self_test`, and golden-image recognition, including the expected Chinese and
  English evidence.
- Scan every released runtime binary for the randomized builder-root nonce and
  its absolute checkout path in both ASCII and UTF-16LE. Any hit blocks release.
- Run cached-output verification and deployment installation from the same
  consumer-isolated artifact, then pass the frozen-package OCR/import/retrieval
  smoke path.
- `pdm run pytest --direct <focused selectors>`, `pdm run check`,
  `pdm run build-knowledge-ocr`, `pdm run build-knowledge-ocr --verify-output`,
  `pdm run test`, `pdm run smoke`, `pdm run package`, and
  `pdm run smoke-package` pass.

## Current Truth

- Installed v1.3.2 downloads and validates its catalog-selected OCR archive, then
  fails native initialization with `knowledge_ocr_response_invalid`.
- The published worker contains
  `D:\a\Xenix\Xenix\build\knowledge-ocr\PaddleOCR\...\utility.cc`.
  PaddleOCR's `Utility::GetDefaultConfig("OCR")` uses that compile-time
  `__FILE__` value to derive a source-tree `OCR.yaml`, so the worker exits when
  the GitHub checkout is absent on the end-user machine.
- The older development generation succeeds only because its embedded local
  repository path happens to exist on this machine. This is environmental
  coupling, not v1.3.0/v1.3.2 recognition incompatibility.
- `_OCRPipeline` always needs a `YamlConfig`, but PaddleOCR supports either a YAML
  path or an `unordered_map<string, string>`. Therefore the external pipeline
  YAML is an upstream convenience, not an inherent Xenix runtime requirement.
- The pipeline YAML supplies orchestration and defaults such as `text_type`,
  module topology, detection thresholds/limits, recognition batch size, and
  optional preprocessing flags. Per-model `inference.yml` files describe model
  inference and cannot replace those pipeline values.
- The provisional repair copies `OCR.yaml` into the archive and passes the
  relative string `"OCR.yaml"` from `main.cpp`. It passes current verification
  only because both the builder and product session launch with the runtime
  directory as CWD.
- That provisional repair is rejected for release: it leaves a companion config
  dependency, retains real `__FILE__` paths in the binary, hides only one source
  config during verification, and does not prove operation from an arbitrary CWD
  after the full source checkout is unavailable.
- The approved direction is to compile the fixed Xenix pipeline map into the
  worker, remove the external pipeline YAML entirely, eliminate the
  `GetDefaultConfig("OCR")` runtime branch, sanitize real build paths, and make
  consumer isolation plus raw-binary scanning release-blocking.
- `xenix-ocr.exe` now supplies PaddleOCR's supported map variant with the 31
  flattened values from the pinned upstream `OCR.yaml`. Existing Xenix overrides
  still disable document orientation, document unwarping, and textline
  orientation; model-owned `inference.yml` files remain package assets.
- The reviewed pinned compatibility patch makes an accidental
  `GetDefaultConfig()` call fail with `FailedPrecondition` instead of deriving a
  path from `__FILE__`. MSVC maps the whole disposable workspace to a stable
  virtual path under deterministic compilation, covering PaddleOCR and SDK
  headers alike.
- Runtime archives no longer contain `OCR.yaml`. The builder uses a randomized
  workspace, handles the OpenCV self-extractor's non-exiting process, clears
  Git's read-only generated pack indexes, deletes the full PaddleOCR checkout,
  and only then validates a consumer-extracted archive from a foreign CWD with a
  deliberately invalid `OCR.yaml`.
- The rebuilt archive is
  `xenix-knowledge-ocr-win-x64-paddle-inference-3.3.0-paddleocr-3.7.0-win-x64-5f661643218c1028e5dc111321ced3e14bc82a9ce9774a31ff60f9e753a5b5ae.zip`.
  It has no pipeline YAML, retains `runtime.json`, and scans clean for its
  randomized workspace nonce and real build-root path in every runtime EXE/DLL
  in ASCII and UTF-16LE.
- Focused tests (9), repository checks, a fresh native build, cached-output
  verification, all 39 repository tests, development smoke, application
  packaging, and frozen-package OCR/import/retrieval smoke pass.

## Next Step

The approved v1.3.3 release is being promoted through the repository release
protocol. Existing installed v1.3.2 state remains untouched until its update is
published through the canonical feed.
