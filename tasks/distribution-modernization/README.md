# Distribution Modernization

## Objective

Deliver a Windows distribution path covering a one-click installer, in-application updates, continuous delivery, and Alibaba Cloud OSS publication.

## Guardrails

- Task-packet authoring is approved. Do not change product code, packaging, CI, or external infrastructure without a later slice-specific Impact Handshake and explicit start.
- Preserve `%LOCALAPPDATA%\Xenix` user state independently from installed application files.
- Preserve packaged ML workers, native libraries, runtime diagnostics, and the existing packaged smoke gate.
- Code protection, worker-source concealment, and algorithm protection are explicitly out of scope for this task; retain the discovered risks as follow-up evidence.
- Packaged trial LLM and trial-lock features must remain enabled. Their embedded credentials are extractable and cannot be described as a secure client trust root. The product owner explicitly accepts API-key theft and trial-lock bypass risk for this release; rotation/revocation remains an operational requirement.
- Do not commit, publish, release, upload, or provision external resources.

## Approved Decisions

- The consumer installer is Velopack's one-click `Setup.exe`; a guided MSI and portable ZIP are not required in this task.
- Authenticode signing is deferred outside this task. The first Setup is knowingly unsigned; SmartScreen/Defender reputation and independent publisher authentication are not provided by this release path.
- SSH worker algorithm/source exposure is accepted for this task. The worker bundle must keep working, but reducing or protecting its source is not part of the implementation.
- Keep PyInstaller `onedir`, add the Velopack Python SDK and version-matched `vpk` CLI, build and publish through GitHub Actions, and serve update assets from Alibaba Cloud OSS.
- The first public native version is `1.0.0`. Step 1 will compare supported Python patches through the full package/smoke path before fixing the official build interpreter.
- Product and brand name are `Xenix`; the Chinese name is `择析`.
- The minimum supported platform is Windows 10 version 1809 (build 17763) x64. Windows 7 is rejected because it conflicts with the repository's Python 3.12+ and Qt 6.11 runtime baseline.
- GitHub Actions will use a dedicated, least-privilege long-lived Alibaba Cloud RAM AccessKey. OIDC/temporary STS credentials are rejected for this task as disproportionate operational complexity. The key must be isolated to protected GitHub secrets, scoped separately from unrelated workloads, masked from logs/artifacts, and rotated on a defined schedule or immediately after suspected exposure.
- Use one OSS bucket with `candidates/` and `published/` prefixes. GitHub Environments and workflows are named `native-candidate` and `native-publish`; these are approval/authority boundaries, not long-lived application environments. An anonymous-read bucket policy exposes only `published/*`; `candidates/*` remains private.
- Use one RAM identity and long-lived AccessKey for both prefixes. The product owner accepts that this credential can mutate both candidate and published objects, so GitHub workflow/environment controls, single-writer concurrency, exact-prefix policy, feed history, and rotation are the remaining controls; the candidate credential is not an isolation boundary from publication.
- `RELEASES_OSS_PUBLIC_URL` is the single public download-location input. The frozen update-feed URL is derived from it, and the stable Setup URL is `<url>/Xenix-Setup.exe`; do not maintain a separate feed URL authority.
- Trial and telemetry settings are build inputs, not end-user runtime setup. One build-time configuration owner validates the `XENIX_TRIAL_*`, `XENIX_OTEL_*`, and supported standard `OTEL_*` inputs and generates one frozen release-config projection. Rename `TRIAL_PURCHASE_URL` to `XENIX_TRIAL_PURCHASE_URL`; retain standard OpenTelemetry names rather than adding duplicate `XENIX_` aliases. Embedded credentials and telemetry headers are extractable from the client.
- The product owner explicitly accepts that the embedded trial LLM API key can be stolen and the client-side trial lock can be bypassed. Neither mechanism is a public-release security boundary.

## Verification

- Recommendations cite current repository evidence and current upstream tool capabilities.
- The proposed release sequence includes reproducibility, unsigned-release risk controls, update publication, staged verification, rollback, and explicit secret boundaries.
- Implementation is split into independently approvable slices with explicit acceptance criteria.

## Current Truth

- Step 1 implementation has started. `pyproject.toml` version `1.0.0` now projects into source runtime and generated frozen build information; observability includes the application version. Formal builds fail unless the trial LLM key, positive trial-lock duration, and stable trial-lock state secret are all supplied. Generated credential modules are cleaned even when generation or packaging fails.
- The first measured baseline is Python 3.14.0 + PyInstaller 6.21.0 on Windows 10 22H2: package completed in 263.12 seconds, produced a 980,735,978-byte onedir tree, and passed packaged smoke. The full suite passed 320 tests with three pre-existing library/model warnings. Python 3.12/3.13 package results and Windows 10 1809 remain unproven rather than rejected.
- Upstream patch selection needs a Windows-binary rule, not a naive “latest source release” rule. As of 2026-07-11, Python 3.12.13 is source-only and 3.12.10 is the last 3.12 patch with an official Windows installer; Python 3.13.14 and 3.14.6 are the current maintenance releases. Local PDM 2.26.6's standalone catalog lags at 3.13.9/3.14.2, so it cannot be the authority for the official comparison. PDM-managed 3.12.10 and 3.12.11 interpreters were prepared, but no project environment or package result has yet been accepted from them.
- The current release gate is `pdm run package`, `pdm run smoke-package`, then `pdm run dist`.
- PyInstaller already builds an `onedir` bundle. The existing output is about 935 MiB unpacked and 386.6 MiB zipped, so first-install size and release upload time are material.
- The frozen bundle deliberately includes more than one hundred plain `.py` files under `xenix_worker_source` for SSH ML execution. This bypasses ordinary PyInstaller bytecode concealment and includes generated trial configuration in release builds.
- SQLite and other mutable state live outside the installation bundle; risky release transitions require backup because startup migrations are forward-only and do not create a pre-migration backup.
- The default runtime home `%LOCALAPPDATA%\Xenix` would collide with Velopack if `packId` were `Xenix`; the installer must use a distinct stable application id/root.
- Native desktop CI/CD does not exist. Current Actions workflows cover only the website and Cloudflare deployment.
- Desktop version truth is split across `pyproject.toml` (`1.0.0`), `src/xenix/__init__.py` (`0.1.0`), the Git tag (`v0.1.0`), and the embedded build commit.
- Velopack is compatible with the existing `onedir` shape. Its lifecycle hook belongs at the start of `scripts/run_packaged.py`, subject to packaged tests for the GUI process, analysis worker mode, and spawned ML workers.
- OSS object operations are atomic and strongly consistent. Versioned-name packages must be uploaded and publicly verified before the mutable `releases.<channel>.json` publication point.
- OSS PutObject has no destination `If-Match` compare-and-swap equivalent for the live feed, and bucket versioning conflicts with create-only overwrite protection. Publication therefore needs one release writer, GitHub concurrency, a least-privilege RAM AccessKey, create-only package writes, and immutable snapshots of every prior feed rather than claiming R2-style CAS.
- Public delivery uses `https://xenix.oss-cn-hangzhou.aliyuncs.com/published`, the native OSS Bucket HTTPS domain plus prefix. A custom domain, ICP filing, CDN, and URL rewrite are not used for the first release.
- The current trial lock needs one stable secret across updates or an installed trial state will fail HMAC validation after a release. The trial LLM key and trial-lock secret are both directly extractable from the client, including the plain worker-source bundle.
- Frozen release configuration is now centralized in `xenix.release_config.ReleaseConfig`. Pydantic validates build inputs; one generated module projects release URL, trial LLM/lock/purchase, and telemetry into the package. Packaged OTEL setup replaces ambient runtime values with the frozen mapping, while source runs use the same model against the development environment.
- The current host is suitable for Hyper-V release VMs, but the active session is not elevated and no ISO is available. `vm-readiness.md` owns the host evidence, guest matrix, required inputs, and mutation gates.
- The user approved the distribution architecture and requested an implementation sequence; detailed slices and gates are owned by `implementation-steps.md` in this task packet.
- `human-release-worksheet.md` is the operator-facing checklist for all remaining identity, GitHub, Alibaba Cloud, VM, network, candidate, publish, and rollback evidence.
- A paper execution found additional critical gates: startup auto-apply must be disabled, safe apply needs an application-wide activity/shutdown owner and a single-instance boundary, candidate artifacts may exceed GitHub plan allowances, the unsigned feed has no independent publisher-authentication layer, and OSS delivery must be proven from the supported Windows VM matrix. `preflight-rehearsal.md` owns the task-local decision register and readiness checklist.

## Next Step

Complete automated verification, then follow `human-release-worksheet.md` for the remaining identity, GitHub, VM, Alibaba Cloud, and public acceptance work. No local placeholder-secret candidate may be published.
