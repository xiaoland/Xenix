# Implementation Status

## Automated implementation complete

- `pyproject.toml` is the SemVer authority; source runtime, diagnostics, frozen build info, Windows PE metadata, tag validation, Velopack version, and release manifest project from it.
- Formal release validation requires explicit trial LLM base URL/key/model, positive trial-lock duration, stable trial-lock secret, purchase URL, and—for public builds—an HTTPS `RELEASES_OSS_PUBLIC_URL`. One Pydantic model freezes release, trial, and supplied OpenTelemetry settings into one generated projection. Embedded-secret theft and trial bypass are explicitly accepted risks.
- Velopack Python SDK and local `vpk` are pinned to 1.2.0. Lifecycle runs before other packaged startup work and disables startup auto-apply. PyInstaller remains onedir and UPX is disabled.
- `dev.lanzhijiang.xenix`, `win-x64-stable`, and `win10.0.17763-x64` are the current immutable package identity proposal. Changing the pack id after public release is not supported.
- The application has asynchronous automatic/manual checks, explicit download and restart approval, persisted state, single-operation serialization, runtime activity leases, single-GUI-instance mutex, verified SQLite backup before every apply, normal storage disposal, and Velopack wait-exit handoff.
- ML queued execution and Agent turns hold runtime leases. Persisted task rows are not used as live update locks.
- Candidate and publish workflows use `native-candidate` and `native-publish`. Publish concurrency queues. The same long-lived RAM AccessKey is intentionally used in both protected GitHub Environments.
- Candidate upload and publication use one `OSS_BUCKET`, with private immutable candidates under `candidates/` and anonymously readable client assets under `published/`. Approved-manifest binding, immutable/create-only objects, same-name hash checks, public-URL hash/Range verification, feed history, feed-last publication, and stable Setup alias verification remain enforced.
- Website examples now point to a stable Setup alias. Deployment/runbook and RAM policy template are present.

## Local evidence

- Static checks passed. Full tests: 322 passed; three existing sklearn warning surfaces.
- Final release-config/trial-lock focus after the full suite: 14 passed.
- Latest packaged candidate: Python 3.14.0, PyInstaller 6.21.0, Velopack 1.2.0; packaged smoke passed.
- Unsigned output: 68 application PE files plus Setup reported unsigned by vpk.
- Setup: 408,284,865 bytes, SHA-256 `149fe896258768dd693e998ffbf775cf8c04ad8ee1150a3de858f162c3e346f8`.
- Full package: 403,804,865 bytes, SHA-256 `1e47b83e81b3202ecc10493a7ba1b8fa337d1b3055f3bdef002eaea298e7464b`.
- The packaged worker projection contains the expected release URL, purchase URL, OTEL endpoint/protocol/toggles, trial configuration, and placeholder secrets; the source tree is clean after packaging. This candidate uses non-production `.invalid` endpoints and placeholder credentials and must not be published.

## Completed implementation follow-up

1. [x] Rename GitHub Environments to `native-candidate` and `native-publish`; retain two explicit workflow invocations and manifest-digest approval.
2. [x] Replace staging/production bucket variables with one `OSS_BUCKET` and use `candidates/` plus `published/` keys.
3. [x] Project the accepted single RAM identity into one-bucket workflow inputs and a one-bucket RAM policy template.
4. [x] Make `RELEASES_OSS_PUBLIC_URL` the only release-location build input and derive the Velopack feed and stable Setup URL.
5. [x] Replace partial generated trial modules with one Pydantic-validated frozen release-config projection.
6. [x] Rename `TRIAL_PURCHASE_URL` to `XENIX_TRIAL_PURCHASE_URL`; preserve standard OTEL names and freeze supplied telemetry settings.
7. [x] Expand candidate workflow inputs and add focused tests for validation, generation, URL derivation, telemetry capture, and frozen runtime precedence.

## Human/external work after the approved follow-up

1. Confirm `dev.lanzhijiang.xenix` as the permanent pack id and `Xenix` as unsigned Apps & Features publisher text.
2. Commit/push the implementation, then run `Native Python Baseline`. Review 3.12.10/3.13.14/3.14.6 package time, size, smoke and startup evidence before keeping the provisional official pin `3.14.6`.
3. Create/prepare the Windows 10 LTSC 2019 and Windows 11 interactive VMs described in `vm-readiness.md`; supply licensed/evaluation ISOs, elevation, and activation posture.
4. Configure one Hangzhou OSS bucket with versioning disabled, anonymous read restricted to `published/*`, native Bucket HTTPS delivery, GitHub `native-candidate`/`native-publish` Environments, the single approved least-privilege RAM AccessKey, rotation owner, budget and traffic alerts.
5. Provide real frozen release configuration through protected secrets/variables: `RELEASES_OSS_PUBLIC_URL`; trial LLM base URL/key/model; duration/state secret/purchase URL; and the intended telemetry toggles/exporter settings. Never publish the local placeholder-secret candidate.
6. Manufacture a private N-1/N pair and run clean install, uninstall, normal update, skipped-version, delta, active-work refusal, second-instance, interrupted/corrupt/no-space, representative-state, migration/backup and feed rollback tests on both VMs.
7. Record actual Unknown Publisher, SmartScreen and Defender behavior and Mainland China OSS GET/HEAD/Range/throughput results.
8. Create `v1.0.0`, run the protected candidate workflow, approve its manifest digest, run publish, verify the stable Setup alias, and set website `XENIX_DOWNLOAD_URL` to that alias.

The explicitly authorized release sequence owns subsequent commit, tag, workflow, OSS, and publication evidence. Use `human-release-worksheet.md` as the single operator checklist for remaining human gates and their evidence.
