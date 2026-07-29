# Verification Record

This file records completed evidence rather than treating the earlier plan as a
future gate. It separates implementation proof from the two remaining physical
manual acceptance cells.

## Completed Evidence

| Claim | Evidence | Result |
| --- | --- | --- |
| Manifest admission is real, not declarative | The declared Cloud cell acquired each pinned runtime/model recipe, passed component self-tests, and retired it through exact fenced cleanup. | Passed |
| Private SSH one-click control plane works | Actual `build_amd_composition()` prepared the admitted profile, reached `operational`, exercised the generic Chat, Embedding, and OCR adapter paths, then retired it to `removed`. | Passed |
| No target residue is left by validation | After the product run, the validation root had no generation, runtime, receipt, tombstone, provisioning, listener, or owned-process artifact. | Passed |
| Artifact provenance stays exact | Recipes use the manifest-declared vLLM wheel filename and byte/hash verification; mirror transport cannot change source identity. Hugging Face acquisition excludes irrelevant mirror-blocked `.DS_Store` entries. | Passed |
| OCR uses an industry transport without AMD coupling | The product maps exact managed OCR provenance to an ordinary KServe V2/PAGE spawn descriptor; no generic OCR module imports AMD. | Passed |
| Settings authority prevents stale full-save overwrite | UI and managed registration use capability-owned revisioned commands through one `SettingsStore`; the UI regression now uses that production path. | Passed |
| Retirement is forward-only | Durable desired absence is committed before cancellation/cleanup; exact generation gates, projection commands, and target cleanup only advance toward removal. | Passed |
| Default distributable carries the optional slice | Default `pdm run package` and `pdm run smoke-package` passed after validating the AMD runtime hook. | Passed |
| Hard cut-off is executable | `XENIX_BUILD_AMD_ONE_CLICK=0` produced a package with no AMD slice paths. Its packaged smoke passed even when `XENIX_ENABLE_AMD_ONE_CLICK=1`. | Passed |
| Generic product remains AMD-free | Static source regression rejects direct generic-to-AMD imports; `pdm run test` (44), `pdm run check`, and `pdm run smoke` passed. | Passed |

## Validation Commands

Completed on the implementation workspace:

```text
pdm run pytest --direct -q
pdm run test
pdm run check
pdm run smoke
XENIX_BUILD_AMD_ONE_CLICK=0 pdm run package
XENIX_ENABLE_AMD_ONE_CLICK=1 pdm run smoke-package
pdm run package
pdm run smoke-package
```

The AMD-enabled build initially exposed a malformed generated runtime hook. The
hook writer was corrected, then the complete default package and packaged smoke
were rebuilt successfully. This is recorded because the final pass is a repaired
release-proof, not a first-pass claim.

## Evidence Boundaries

- The completed Private SSH evidence proves the declared captured Cloud cell and
  the Xenix-managed lifecycle. It does not generalize to other GPUs, drivers,
  ROCm versions, target operating systems, or public hosted APIs.
- The cloud target was headless. No GUI-server capability or native Windows ROCm
  claim follows from the validation.
- The task does not claim a production release, contest submission, or offline
  behavior.
- A source/package hard cut does not authorize deleting unknown remote paths.
  Released-feature removal still follows the staged decommission sequence in the
  hard cut-off contract.

## Remaining Manual Acceptance

| Cell | Why it remains manual | Required outcome |
| --- | --- | --- |
| Fresh Private SSH Radeon target | Verify the user-facing guided setup/removal flow and redacted status presentation, not just headless composition. | One visible install, operation, and removal with no manual endpoint entry or fallback. |
| Fresh Local Linux Radeon host | No physical compatible local Radeon host was available during implementation. | One local install, all three services, restart/cleanup, and removal without SSH. |

The original feasibility probes and detailed cell records remain under
[evidence](evidence/) and [spikes](spikes/). They are historical evidence, not
current product authority.
