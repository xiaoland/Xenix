# TP-19 — Private SSH Product Vertical Slice

## Outcome

Compose the already proven settings, capability, AMD lifecycle, adapters,
placement, and three recipes into the first real product path. This is the only
task that owns the main application composition root.

## Owned Mutation

- add AMD composition/profile aggregation code and final manifest digests inside
  the AMD slice;
- modify `src/xenix/app.py` at one named build-owned feature gate/helper that
  injects AMD factories, startup/shutdown ownership, and optional UI contribution
  into existing generic ports;
- add `tests/test_amd_private_ssh_journey.py`;
- add task-local redacted real-cell evidence scripts/results.

`src/xenix/services/agent/composition.py` remains unchanged and contains no AMD
symbol/import. UI widgets remain TP-20 ownership. AMD is never added to
`app._load_runtime_imports()` or any import-time/global registry.

## Vertical Sequence

```text
fresh Xenix runtime
  -> create Private SSH InstallationSpec
  -> compatibility/capacity
  -> acquire/install/self-test three exact generations
  -> forward ensure three generation-specific provider instances
  -> prove default/current selections unchanged
  -> explicitly select providers through their capability owners
  -> scanned Knowledge OCR
  -> BGE index/query
  -> Granite Tool loop
  -> local canonical Artifact finalization
```

The remote host contains only managed compute/runtime assets. SQLite, Knowledge,
conversation state, and final Artifact authority remain on the desktop.

## Acceptance

- cold product root is distinct from `/opt/xenix-rocm-lab`;
- one headless public deployment use case installs/registers all three;
- partial-domain crash resumes only missing forward work;
- disconnect fails the current operation; the next rematerializes;
- no provider setting contains dynamic binding state and no selection changes
  automatically;
- app composition with the AMD contribution disabled starts all static
  LLM/Embedding/Paddle/Knowledge/Agent paths and performs no AMD side effect;
- all enabled-build crossings match the cut-off manifest and one app composition
  anchor;
- full rainy-season result remains exact and source-linked;
- real GPU/process/workload evidence is correlated and redacted.

## Verification

- deterministic journey test with fake target;
- authorized real-cell headless Private SSH run;
- focused LLM/Embedding/OCR contracts;
- `pdm run test`, `pdm run check`, and `pdm run smoke`.
