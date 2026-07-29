# TP-22 — Local Linux Radeon Placement

## Outcome

Implement and prove the same product lifecycle when the Xenix controller and
Radeon GPU are on the same supported Linux host, with no SSH or external API.

## Owned Mutation

- add `src/xenix/services/amd/placements/local.py`;
- add local-placement tests and a headless Local acceptance harness;
- register the Local driver only inside the TP-19 AMD composition module;
  `app.py` remains TP-19-owned and receives no new anchor.

A WSL driver, if later admitted, is a separate module/task. Native Windows ROCm
is not implied.

## Behavior

- observe exact local OS/GPU/driver/ROCm/storage/capacity facts;
- use the same TP-08–14 lifecycle, manifests, provider refs, gates, and recipes;
- own process groups/start identity/incarnation, direct loopback binding, reaping,
  device loss, restart, and cleanup;
- work without systemd and without a GUI session;
- use the packaged/self-contained product controller and manifest-owned component
  runtime because the captured cell has only Python 3.12 and no uv/PDM; v1 does not
  repair OS/Python tooling with ambient pip/PDM/uv;
- no SSH, CPU fallback, or Dedicated Model API.

## Acceptance

- fake tests cover unsupported cell, occupied port, process/PID reuse, device loss,
  controller crash, second controller, retire, and adjacent-file sentinel;
- a fresh Radeon Cloud instance may serve as the Local Linux cell by running the
  product headlessly on the GPU host;
- all three services install, authenticate, register, operate, restart, repair,
  and retire through the same public control plane;
- exact Local binding state stays memory-only;
- result is labeled same-host Linux service-path proof, not desktop packaging.

## Verification

- focused Local placement tests;
- authorized fresh-cell headless Local run;
- same capability/device/security proofs as TP-19;
- `pdm run check`.
