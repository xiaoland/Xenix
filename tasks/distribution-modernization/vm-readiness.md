# Windows Release VM Readiness

## Status

Read-only host audit completed. No Windows feature, VM, switch, disk, checkpoint, or external file was created or modified. VM creation requires a later explicit start and one elevated administrator session.

## Host Evidence

- Host OS: Windows 10 Pro N 22H2, build 19045, x64.
- CPU: AMD Ryzen 5 3600, 6 cores / 12 threads.
- Memory: 32 GB; about 13 GB was free during the audit.
- Firmware virtualization is enabled and Windows reports `HypervisorPresent=True`.
- Hyper-V PowerShell modules are installed; `vmms`, `vmcompute`, and `hvhost` are running; a Hyper-V Default Switch/vEthernet interface exists.
- Recommended storage root: `E:\Hyper-V`; E: had about 1.75 TB free during the audit.
- Current process is not elevated. Its UAC-filtered token cannot enumerate or mutate Hyper-V resources, so an administrator re-check is mandatory before choosing names/paths.
- No suitable Windows ISO was found in common local locations.

## Guest Matrix

| Priority | Guest | Purpose |
| --- | --- | --- |
| P0 every release | Windows 10 Enterprise LTSC 2019, version 1809, build 17763, x64, fully patched | Exact minimum-supported-platform gate |
| P0 every release | Current Windows 11 x64, fully patched | Modern Windows, Secure Boot/vTPM, SmartScreen/Defender gate |
| P1 dependency/release changes | Windows 10 22H2 x64, fully patched/available ESU posture | Common deployed Windows 10 surface |
| Negative only | Windows older than build 17763 | Prove a clear unsupported-OS refusal; no Windows 7 compatibility promise |

Windows 7 is incompatible with the current product baseline. Python 3.12 requires Windows 8.1 or newer and points Windows 7 users to Python 3.8; locked Qt/PySide 6.11 requires Windows 10 1809 or newer. Supporting Windows 7 would require a Python 3.8 + Qt 5/PySide2 legacy line and a separate native-ML dependency set.

## Proposed VM Shape

Windows 10 guests:

- Generation 2, 4 vCPU, 6–8 GB startup memory;
- 100 GB dynamically expanding VHDX;
- Default Switch NAT and Enhanced Session;
- Secure Boot enabled when compatible with the selected ISO.

Windows 11 guest:

- Generation 2, 4 vCPU, 8 GB startup memory;
- 120 GB dynamically expanding VHDX;
- Secure Boot and virtual TPM;
- Default Switch NAT and Enhanced Session.

Run one release VM at a time on this 32 GB host. Do not store activation keys, ISO credentials, local administrator passwords, or VM secrets in the repository.

## Checkpoints

Each supported guest should have:

1. `clean-os`: fully patched OS, no Python/Qt/Xenix, standard Defender state.
2. `nminus1-installed`: verified previous Xenix Setup installed as a non-administrator user.
3. `representative-state`: conversations, settings, dataset/app-owned files, model, artifact, worker settings, install id, and enabled trial state.
4. `update-ready`: update downloaded but not applied, for interruption/lock/restart tests.

Checkpoint names must include guest OS/build and creation date in the release evidence even if the Hyper-V display name stays short.

## Guest Acceptance Work

- Setup install/uninstall, shortcut, Apps & Features, and preserved `%LOCALAPPDATA%\Xenix` state.
- Expected unsigned Unknown Publisher/SmartScreen/Defender path.
- Packaged smoke plus minimum real operations for PySide6, NumPy/SciPy/Pandas/scikit-learn, XGBoost, LightGBM, DuckDB, Polars, and vl-convert.
- Chinese user/profile path and ordinary non-administrator account.
- Public OSS feed, full/delta download, HEAD/GET/Range 206, interruption, corruption, insufficient disk, and offline behavior.
- N-1 to N and skipped-version updates; active-work refusal; second-instance/locked-file behavior; hard-killed updater.
- SQLite backup/migration/failure evidence and representative-state retention.
- Trial LLM availability and trial-lock continuity across N-1 to N using the stable release-wave secret.
- Feed snapshot rollback and stable Setup alias behavior.

## Inputs Required from Sir

- Explicit authorization to create and configure Hyper-V VMs under `E:\Hyper-V`.
- One administrator/UAC-elevated execution window so existing VMs, switches, paths, and Hyper-V settings can be re-audited and mutated.
- A legally obtained Windows 10 Enterprise LTSC 2019/1809 x64 ISO or access path and its expected SHA-256. A Windows 10 22H2 ISO does not prove 1809 compatibility.
- A current Windows 11 x64 ISO or approval to download an official Microsoft evaluation image, plus language/edition selection.
- Activation policy. Short-lived installation testing can run unactivated/evaluation images when licensing permits.
- Confirmation that release tests should use the real public Aliyun OSS Bucket endpoint from inside the guests.

## Proposed Execution Slices

1. Administrator re-audit only: enumerate current VMs/switches/default paths and confirm no naming/path collisions.
2. Generate reviewed PowerShell VM definitions and ISO hash checks; no creation yet.
3. Create one guest, install/update OS, establish `clean-os`, and prove restore automation.
4. Repeat for the other P0 guest; add P1 Windows 10 22H2 only after the P0 workflow is stable.
5. Add release acceptance helpers that copy or download the exact candidate manifest/digest without embedding cloud write credentials.

Each slice needs its own Impact Handshake because it changes host state outside the repository.
