# Radeon Cloud ROCm Preflight

**Captured:** 2026-07-28

**Status:** Chat, Embedding, OCR, PAGE, and private-forward contract probes passed;
the manually started services were then stopped

**Scope:** task-local development evidence; no Xenix product source is changed

## Outcome

The assigned `gfx1100`/ROCm 7.2.1 cell successfully ran three loopback-only
development services concurrently:

| Capability | Runtime | Model | Remote listener |
| --- | --- | --- | --- |
| Chat | vLLM ROCm 7.2.1 nightly | Granite 3.1 8B Instruct | `127.0.0.1:8101` |
| Embedding | vLLM ROCm 7.2.1 nightly | BGE-M3 | `127.0.0.1:8102` |
| OCR | RapidOCR 3.9.2 + certified ROCm PyTorch | PP-OCRv6 small | `127.0.0.1:8103` |

All three endpoints passed their real protocol checks through one temporary SSH
local-forward process. The process identity was checked before termination and
all three local ports were released afterward. Before implementation planning, the
three exact remote process groups were identity-checked and stopped, their volatile
PID files were removed, and the three remote listeners were confirmed closed.
Their verified assets, logs, and task evidence remain isolated under the lab paths;
they are not product-managed installations or eligible one-click acceptance input.

The exact runtime and asset choices are in [runtime-manifest](runtime-manifest.md).
Observed results and limitations are in
[Radeon Cloud ROCm runtime evidence](../../evidence/radeon-cloud-rocm-runtime-2026-07-28.md).
Failures and their implementation consequences are in
[preflight failures](../../evidence/radeon-cloud-preflight-failures-2026-07-28.md).

## Files

| File | Role |
| --- | --- |
| `validate_openai_contracts.py` | Black-box Xenix Chat, SSE, Tool, and Embedding wire validation |
| `validate_rapidocr_rocm.py` | Three-stage ROCm/device/no-fallback OCR and accuracy validation |
| `rapidocr_kserve_server.py` | Real RapidOCR KServe V2 Binary Tensor + PAGE-only spike server |
| `validate_kserve_ocr_contract.py` | KServe metadata, inference, PAGE region, and typed-error validation |
| `validate_private_tunnel.ps1` | One-process three-forward validation with identity-guarded cleanup |
| `validate_guided_ui_headed.py` | Production Qt guided-command, typed SSH failure, and log-redaction acceptance helper |

The PAGE XSD validator remains in
[`../ocr-protocol/validate_official_schemas.py`](../ocr-protocol/validate_official_schemas.py).
It now supports `--page-only`, so the product-leading PAGE profile is not blocked
by an unrelated ALTO schema source.

## Remote Layout

```text
/opt/xenix-rocm-lab/
  artifacts/   verified runtime wheels
  cache/       versioned installer, model, and vLLM compile caches
  config/      vLLM-owned configuration roots
  envs/        isolated Python environments
  logs/        append-only development service logs
  models/      pinned model snapshots and OCR assets
  run/         volatile development PID files

/workspace/xenix-rocm-lab/
  evidence/    persistent-candidate fixtures and captured protocol outputs
  manifests/   copies of the task-local validation/server scripts
```

`/opt` had ample overlay space but no persistence guarantee. `/workspace` is only
about 20 GiB. The current Granite model alone is about 16.3 GB, so a product
manifest cannot assume this exact split or claim durable repair until the target's
storage class and capacity are verified.

The persistent-candidate evidence directory currently contains:

```text
openai-contracts.json
rapidocr-rocm.json
kserve-ocr-contract.json
page-schema-validation.json
rapidocr-fixture.png
rapidocr-page.xml
```

These contain only synthetic fixture and runtime/protocol observations.

## Post-Feasibility Teardown

The teardown deliberately removed only the manually started Chat, Embedding, and
OCR process groups and their volatile PID files. It did not remove ROCm, system
Python, SSH configuration, verified model snapshots, wheel artifacts, append-only
logs, or the evidence directory.

The final check found no matching service process or listener on `8101`, `8102`,
or `8103`. Reported GPU memory use fell from the concurrent-service observation of
about 37.2 GB to about 28 MB. Whole-device busy percentage is not used as teardown
authority because the assigned device may have unrelated activity and that metric
is not process-attributed.

This stopped lab is still `manual-preheated/acceptance-ineligible`: its existing
runtime, model, and compile caches may accelerate further engineering probes, but
the product deployment path must use a separate, initially absent product root.
Definitive cold one-click acceptance requires a fresh instance/PVC or an
equivalently attested clean baseline, not selective cleanup of this lab.

## Re-run

On the Radeon target:

```bash
/opt/xenix-rocm-lab/bootstrap/bin/python \
  /workspace/xenix-rocm-lab/manifests/validate_openai_contracts.py

/opt/xenix-rocm-lab/envs/rapidocr-rocm721/bin/python \
  /workspace/xenix-rocm-lab/manifests/validate_rapidocr_rocm.py

/opt/xenix-rocm-lab/bootstrap/bin/python \
  /workspace/xenix-rocm-lab/manifests/validate_kserve_ocr_contract.py
```

From the Xenix workspace, after placing the fixed fixture outside the repository:

```powershell
.\tasks\amd-rocm-hackathon-strategy\spikes\radeon-cloud\validate_private_tunnel.ps1 `
  -FixturePath C:\path\to\rapidocr-fixture.png
```

The scripts contain no cloud endpoint, private-key path, credential, or provider
token. The SSH script uses the operator's configured host alias and binds only
local loopback ports.

## Deliberate Boundaries

- These scripts validate a manually prepared development cell. They are not the
  future `AmdAiDeploymentService`.
- PID files are observations, not process authority. A product controller must
  persist/verify generation, runtime incarnation, process-group identity, and
  start identity before any lifecycle action.
- The OCR server is an executable protocol/backend spike. It has a single-request
  server and incomplete production admission, cancellation, authentication,
  hostile-XML, inverse-transform, and observability policy.
- The private tunnel is a feasibility proof. No listener URL or local port belongs
  in durable provider settings.
- No result here proves Local Radeon setup, native Windows support, packaged
  one-click deployment, repair, upgrade, or removal.
