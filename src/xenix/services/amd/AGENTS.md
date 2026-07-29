# AMD Deployment Slice Guidance

## Scope

Applies only to the removable AMD one-click deployment slice.

## Tripwires

- Keep dependencies inward: this slice may depend on capability-owned ports and
  storage primitives, but generic LLM, Embedding, OCR, Knowledge, Agent,
  SettingsStore, storage bootstrap, diagnostics, and smoke must never import it.
- No import-time factory registration, service locator, ambient plugin discovery,
  startup reconciliation, target-directory creation, network activity, or process
  creation. `app.py` is the single optional composition anchor.
- Persist only durable desired lifecycle in the storage primitives. Live URLs,
  ports, tokens, processes, forwards, health, cache paths, and runtime
  incarnations remain session memory.
- Treat process IDs and paths as observations. Stop or delete only after exact
  owner, generation, manifest, incarnation, process-group/start identity, and
  command-fingerprint verification.
- Never add ROCm, vLLM, RapidOCR, or target runtime dependencies to the desktop
  dependency set. Target acquisition is manifest-governed.
- Keep secrets out of representations, command lines, settings, manifests, logs,
  diagnostic output, and exceptions.

Run AMD-specific verification plus the hard cut-off proof before claiming a
release. The latter must still pass with this directory absent.
