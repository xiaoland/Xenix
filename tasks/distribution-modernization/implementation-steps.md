# Distribution Modernization Implementation Steps

## Outcome

Ship Xenix 1.0.0 to ordinary Windows users as a one-click `Setup.exe`, let installed copies discover and apply hash-verified updates, and publish releases through a controlled GitHub Actions pipeline to an Alibaba Cloud OSS update feed. Authenticode signing is explicitly deferred.

The target flow is:

```text
vX.Y.Z tag
  -> Windows build and verification
  -> PyInstaller onedir
  -> packaged smoke
  -> Velopack pack (unsigned)
  -> clean-install and N-1-to-N update verification
  -> protected publish approval
  -> upload immutable OSS assets and verify them remotely
  -> publish releases.win-x64-stable.json last
  -> expose the verified Setup URL through the website
```

Each numbered step is an independently approvable implementation slice. Before changing durable files, present the exact files/symbols, `From -> To` state diff, blast radius, invariants, and verification for that slice. Do not treat approval of this plan as approval to execute all steps.

## Fixed Boundaries

- Windows 10 version 1809 (build 17763) x64 or later and the `win-x64-stable` channel are the first supported release target. Windows 7 is not supported.
- PyInstaller remains `onedir`; Velopack consumes a staging copy of the verified `dist/xenix` tree.
- The consumer artifact is Velopack's one-click `Setup.exe`. MSI and portable ZIP distribution are out of scope.
- `%LOCALAPPDATA%\Xenix` remains the runtime-state authority. The Velopack `packId` and installation root must be different and immutable after the first public release.
- Updates may be checked and downloaded in the background, but may not be applied while ML, Agent, analysis, or child-process work is active.
- Application rollback does not imply SQLite rollback. Update verification must cover schema migration and retained user data.
- Authenticode signing is outside this task. Setup, Update, and application binaries are unsigned, so SmartScreen/Defender warnings and the absence of an independent publisher identity are accepted release constraints.
- Publish is a separate, approval-gated job. Building a release candidate does not make it visible to installed clients.
- Release configuration is fixed at build time. Installed clients do not require product-specific trial or telemetry environment variables; one generated frozen projection owns these values for packaged code.
- Code protection and SSH worker source concealment are non-goals. Existing worker behavior must remain functional.

## Step 0 — Close External and Durable Decisions

Resolve these values before implementation because changing them after public installation would create migration work:

1. Select the immutable Velopack `packId`, recommended shape based on a controlled reverse domain; it must not be `Xenix` because that path is already the runtime home.
2. Use `Xenix` as the product/brand title and `择析` as its Chinese name. Confirm the author/publisher text shown by Setup and Apps & Features; it need not be a legal certificate subject while signing is deferred.
3. Confirm `win-x64-stable` as the permanent first channel and select the OSS custom hostname.
4. Use `pyproject.toml` version `1.0.0` as the first public desktop SemVer authority. The release tag is `v1.0.0` and is a release command, not a second version authority.
5. In Step 1, compare the latest official Windows-capable patch of Python 3.12, 3.13, and 3.14 through frozen dependency sync, PyInstaller package, packaged smoke, size, startup, and Windows 1809 compatibility. A newer source-only security release is not a Windows artifact candidate. The current comparison set is 3.12.10, 3.13.14, and 3.14.6; recheck immediately before pinning. Pin one exact winning patch for official artifacts; CI may keep testing the wider supported range.
6. Select the Alibaba Cloud account, OSS region, one release bucket, `candidates/` and `published/` prefixes, native Bucket HTTPS domain, and anonymous-read policy restricted to `published/*`.
7. Use one dedicated, least-privilege long-lived Alibaba Cloud RAM AccessKey stored only in the protected `native-candidate` and `native-publish` GitHub Environments. OIDC/STS and separate candidate/publish identities are intentionally not used in this task. Define rotation/revocation ownership, prevent secret output or artifact persistence, and restrict the identity to the exact bucket, prefixes, and operations. Explicitly accept that it can mutate both candidate and published objects.
8. Name the production operator(s), tag policy, and rollback authority. There is no signing-approval stage in this task.
9. Confirm the initial update policy. The rehearsal recommends automatic checks after usable startup, explicit user approval before downloading until real delta sizes are known, a prompt before restart, and no forced update in the first release.
10. Manufacture two unsigned internal versions for the local install/update rehearsal. Freeze the first verified installed release as the durable N-1 fixture for subsequent unsigned releases.
11. Declare minimum runtime `win10.0.17763-x64`. Use fully patched Windows 10 Enterprise LTSC 2019 as the 1809 compatibility gate and current Windows 11 x64 as the modern gate.
12. Confirm the GitHub plan, Actions budget, and available Environment protection rules for this private personal repository. If native required-reviewer gates are unavailable, use an explicit two-command candidate/publish protocol without describing it as peer approval.

Exit evidence:

- Stable identifier and channel decisions are recorded in their durable technical owner when implementation begins.
- OSS identity, publication, and rollback authority are explicit. Signing remains a documented follow-up and is not a release gate in this task.

## Step 1 — Establish a Reproducible Desktop Release Baseline

Make release identity and build inputs deterministic before adding the updater.

Implementation work:

- Collapse the conflicting desktop versions in `pyproject.toml`, `src/xenix/__init__.py`, runtime diagnostics, and Windows file metadata into one generated projection of the `pyproject.toml` version.
- Validate that a release tag is exactly `v<pyproject version>` and points to the checked-out commit.
- Embed both SemVer and Git commit in diagnostics; keep the commit as provenance rather than using it for update ordering.
- Pin the official Windows runner image expectations, Python version, PDM version, locked dependencies, Velopack Python package, and later the matching `vpk` version.
- Add native Windows CI for `pdm run check` and `pdm run test`. Keep release-only credentials unavailable to pull-request jobs.
- Retain `pdm run package` and `pdm run smoke-package` as release gates and emit a machine-readable build manifest containing version, commit, tool versions, hashes, and smoke result.
- Prevent interrupted builds from leaving generated trial credential modules as untracked files. Because trial features must remain enabled, validate that one stable trial-lock secret is supplied across update-compatible builds and that the trial LLM configuration is present, without printing either secret. Record that both are extractable and require rotation/revocation procedures.
- Define one build-time release-configuration registry and generate one frozen projection consumed by packaged code. It owns `RELEASES_OSS_PUBLIC_URL`, `XENIX_TRIAL_*`, `XENIX_OTEL_*`, `OTEL_SDK_DISABLED`, and `OTEL_EXPORTER_*` settings. Rename `TRIAL_PURCHASE_URL` to `XENIX_TRIAL_PURCHASE_URL`; standard OTEL variables keep their standard names. Derive the update feed from the normalized release URL instead of accepting a second authority.
- Keep development convenient without introducing a second schema: source runs resolve the same registry from their process environment, while frozen builds resolve the generated projection and do not depend on end-user environment variables. Never log embedded values; classify OTLP authentication headers/certificates and client keys as extractable client material.
- The Pydantic model explicitly owns product fields and explicitly recognizes the `XENIX_OTEL_*` and `OTEL_EXPORTER_*` families plus `OTEL_SDK_DISABLED`. Formal candidates require release URL, trial LLM base URL/key/model, positive lock days, stable lock secret, and purchase URL. Telemetry remains optional as a group; supplied exporter values are frozen without renaming. Packaged product consumers do not read trial/release values from `os.getenv`; frozen OTEL values are installed into the process before the standard exporters initialize.

Acceptance:

- One command resolves the same SemVer for the application, EXE metadata, diagnostic output, and future `vpk --packVersion`.
- A mismatched or non-monotonic tag fails before packaging.
- Windows CI passes without access to OSS publication credentials.
- The existing packaged smoke still passes in an isolated `XENIX_APP_HOME`.

## Step 2 — Prove Velopack Lifecycle and Packaging Compatibility

Introduce Velopack without external publication so process behavior can be isolated.

Implementation work:

- Add the pinned Velopack Python SDK and use the exact matching pinned `vpk` CLI version.
- Register the Velopack lifecycle hook at the earliest safe packaged entry seam in `scripts/run_packaged.py`, before startup timing or GUI imports, and explicitly disable Velopack's startup auto-apply. All applies must pass through Xenix's activity and backup gate.
- Ensure source-mode development and a raw PyInstaller smoke remain supported when the application is not installed by Velopack.
- Build the PyInstaller tree first, copy it to a clean Velopack staging directory, and run `vpk pack` with the immutable `packId`, SemVer, `xenix.exe`, icon, title, and `win-x64-stable` channel.
- Keep canonical PyInstaller output free from Velopack-generated metadata so packaged-only diagnostics remain understandable.
- Replace the release role of the ZIP with Setup/full/delta/feed artifacts; suppress or discard the generated portable artifact and do not upload it. Do not delete the old ZIP helper until all consumers are proven migrated.
- Turn off UPX before freezing the first internal N-1 fixture so a later global PE layout change does not create a misleadingly large delta.

Required packaged cases:

- GUI launch and normal exit.
- `--smoke-test`.
- `--analysis-lambda-worker`.
- multiprocessing/frozen local ML worker startup.
- SSH worker source bundle staging and execution contract.
- first install, stable shortcut launch, uninstall, and reinstall.

Acceptance:

- A local Setup can install version N, Velopack's low-level apply path can move it to N+1, and delta reconstruction reproduces the N+1 full package. Feed discovery/download remains Step 3 work.
- All process modes behave as before and do not recursively invoke or mis-handle Velopack lifecycle hooks.
- `%LOCALAPPDATA%\Xenix` is neither installed over nor removed by uninstall.

## Step 3 — Add the In-Application Update Boundary and UX

Keep Velopack mechanics behind an application service rather than coupling Qt widgets directly to its SDK.

Implementation work:

- Add an update service with explicit check, download, ready-to-apply, apply-request, unavailable, and failure states. Keep real apply/restart disabled outside isolated tests until Step 4 installs the activity, backup, and shutdown gate.
- Use the public HTTPS feed URL as build configuration; never embed OSS write credentials in the client.
- Check asynchronously after the main window is usable. Do not block startup on network availability.
- Add a manual “check for updates” surface and display installed SemVer, last check result, download progress, and restart readiness.
- Initially keep the channel fixed and omit forced updates and user-facing beta switching.
- Persist the last-check and ready-to-restart state. Run the synchronous SDK through one background executor and marshal progress/state changes back to the Qt thread.
- Measure full and delta sizes before enabling automatic downloads by default; the current package size makes metered connections and free disk space material product constraints.
- Log structured update events without credentials or sensitive query parameters.
- Define a no-op/unavailable behavior for development runs and packages not installed through Velopack.

Acceptance:

- Offline startup is unaffected.
- No update, update available, download failure, corrupted download, ready to restart, and apply failure are observable and testable states.
- UI work remains responsive during checks and downloads.
- A production UI cannot hand control to the updater before Step 4 is complete.

## Step 4 — Make Update Application Safe for Runtime Work and Local State

Downloading can be opportunistic; applying an update is a coordinated shutdown operation.

Implementation work:

- Introduce an application-level admission/activity coordinator using runtime leases, covering ML, Agent, analysis, and child-process work. Do not use UI flags or stale persisted `PENDING`/`RUNNING` rows as the activity authority.
- Refuse or defer apply/restart while work is active; clearly tell the user why.
- Add a single-GUI-instance boundary, or an equivalently race-free other-instance gate, while allowing internal frozen worker modes to bypass it.
- On approved apply, stop accepting new work, quiesce or cancel supported local work, close spawned processes, flush observability, and close storage resources before handing control to Velopack.
- Do not silently terminate remote SSH work. Define how an update reports and later reconciles remote work that outlives the desktop process.
- Before every explicit apply, create a consistent pre-update SQLite backup using the SQLite backup API, validate it through an independent connection, record source/target versions and a hash, and retain a small bounded history. Do not guess from feed metadata whether a release may migrate storage.
- Preserve migration failure evidence. Do not automatically launch an older binary against a newly migrated database unless compatibility is proven.

Acceptance:

- Update application is blocked while representative work is active.
- A clean apply exits without orphaning local child processes or locking the Velopack `current` directory.
- N-1 representative state survives update to N, including settings, conversations, datasets, registered models, artifacts, and worker configuration.
- Migration failure retains the original/backup database and usable logs.

## Step 5 — Establish the Unsigned Release Boundary

Signing is deferred, but the release must make the resulting limitations explicit rather than simulating a signed trust boundary.

Implementation work:

- Preserve the Velopack signing seam so a future task can add `--signTemplate`/`--signParams` without redesigning publication.
- Record that Setup, Update, `xenix.exe`, and bundled PE files are unsigned; SHA-256 and Velopack package hashes prove transfer integrity against the feed, not publisher identity if the feed authority is compromised.
- Test and document actual SmartScreen and Defender behavior on clean supported VMs. Do not promise suppression of “Unknown publisher” or reputation warnings.
- Keep UPX disabled for the official release unless measurements prove a material benefit without degrading Defender, startup, or delta behavior.
- Prevent an unsigned candidate from gaining production visibility without the same build, test, operator, and OSS publication gates used for every release.

Acceptance:

- Release evidence labels every artifact unsigned and contains no “trusted publisher” claim.
- A clean VM can install the unsigned Setup after the expected Windows warning path and all packaged smoke/update tests pass.
- The future Authenticode seam and PE inventory are recorded as follow-up work.

## Step 6 — Build the OSS Publication Boundary

Treat versioned-name packages as immutable data and the channel feed as the publication command.

Infrastructure and pipeline work:

- Use one OSS bucket in Hangzhou. Candidate objects live privately under `candidates/<version>/<manifest-sha256>/`; anonymous-read packages, mutable feeds, stable Setup alias, and feed history live under `published/`.
- Use the native HTTPS Bucket domain with `/published` as the public release URL. Do not introduce a custom domain, ICP dependency, CDN, or URL rewrite for the first release.
- Create one dedicated least-privilege RAM authorization for the release writer and store its long-lived AccessKey only in the protected `native-candidate` and `native-publish` GitHub Environments. The accepted single identity spans both prefixes; GitHub approval and workflow separation reduce accidental publication but do not create credential isolation.
- Pin ossutil or the selected OSS SDK to a reviewed version. Map AccessKey values only into the publication step, mask them, and never print or persist them in logs or artifacts. Record rotation/revocation ownership and cadence.
- Upload the candidate once under its immutable `candidates/` key, record SHA-256, and after authorization use same-bucket server-side copy into `published/`. The RAM identity has no routine delete authority.
- Do not rely on `vpk upload s3` for publication. Use `vpk download http` and `vpk pack`, then ossutil/OSS SDK operations that can express metadata, create-only assets, feed-last order, and verification.
- Store Setup/full/delta packages under versioned immutable names within `published/`. Use `x-oss-forbid-overwrite=true`; an existing name is success only when its remote SHA-256 equals the candidate, otherwise fail. Keep bucket versioning disabled because versioning would disable create-only enforcement.
- Before replacing the live feed, read and record its current bytes/hash, write those bytes to an immutable `publication-history/` key, then re-read and compare the live hash. Write the new feed as one atomic PutObject with Content-MD5 only if the single-writer check still holds.
- OSS does not provide destination `If-Match` CAS for PutObject. Enforce one publish writer through GitHub concurrency (`cancel-in-progress: false`), the protected `native-publish` Environment, and no routine console writes. Describe this accurately as single-writer check-then-put, not atomic CAS.
- Verify every package through the public OSS URL using GET, HEAD, Content-Length, SHA-256, and HTTP Range/206 before publishing the feed. Verify the feed again after the write.
- Configure object metadata so versioned packages are long-lived immutable objects, while feeds and the stable Setup alias use `no-cache`; verify the public response metadata after publication.
- Download the currently published feed/full package before packing N+1 so Velopack creates a real delta. Retain full/delta packages until skipped-version behavior supports a deliberate pruning policy.
- Set bandwidth/traffic/cost alerts. Do not use browser Referer restrictions or interactive URL authentication that would reject Velopack desktop requests.

Acceptance:

- PR and unapproved jobs cannot access protected AccessKey secrets; wrong-ref publication attempts fail at workflow policy and production-environment gates.
- Resumable upload covers the measured GitHub-runner-to-OSS transfer, and credential scanning confirms the AccessKey does not appear in logs or artifacts.
- Candidate and published bytes are identical; same-name conflicting assets are rejected.
- An installed N client cannot observe N+1 until all referenced assets are reachable and verified.
- Concurrent publish workflows queue; an unexpected live-feed hash change aborts publication.
- Feed snapshot rollback is proven and does not claim to downgrade installed clients or restore SQLite.
- OSS credentials never enter application artifacts, caches, or downloadable workflow artifacts.

## Step 7 — Connect the Website and Release Evidence

Implementation work:

- Point the existing website `XENIX_DOWNLOAD_URL` contract at the stable, verified public OSS Setup alias only after feed publication succeeds. Keep the URL stable so every desktop release does not redeploy the website Worker; define retry behavior when feed publication succeeds but alias publication fails.
- Optionally create a GitHub Release containing the unsigned Setup, checksums, manifest, and release notes; OSS remains the update-feed authority.
- Generate operator-facing release evidence: version, commit, build environment, dependency lock identity, smoke/E2E results, artifact hashes, explicit unsigned status, public OSS verification, feed publication time, and rollback reference.
- Update deployment documentation so the canonical release gate reflects Velopack, unsigned-release limitations, OSS publication, update failure handling, and the distinction between binary and data rollback.

Acceptance:

- The website never points to an unverified candidate.
- Support can map an installed SemVer and commit to its manifest, hashes, unsigned status, and published feed.
- The documented release and rollback commands match automation rather than duplicating hidden manual steps.

## Step 8 — Rehearse Before the First Public Release

Run the complete release path with a non-production channel or isolated bucket prefix, then run one approval-gated production rehearsal without announcing it to users.

Verification matrix:

- Clean Windows user profile, ordinary user permissions, Chinese characters in the user profile path.
- Clean install, launch from stable shortcut, uninstall, and reinstall.
- N to N+1, skipped-version update, update while app is running, and restart-to-apply.
- Offline check, timeout, corrupt/truncated package, interrupted download, interrupted apply, locked file, and Defender scan.
- Active ML/Agent/analysis task prevents apply; clean shutdown releases local worker processes and files.
- Representative SQLite migration, pre-update backup, retained artifacts, and migration failure recovery.
- Windows 10 Enterprise LTSC 2019 (1809/build 17763) and current Windows 11 x64 both complete the package/install/update gate; Windows 7 receives a clear unsupported-OS refusal.
- Expected Unknown Publisher, SmartScreen, and Defender behavior is recorded for the unsigned Setup.
- Public OSS package caching and Range/206 work; feed metadata does not remain stale; feed publication occurs last.
- Website download returns the currently approved unsigned Setup.

Exit criteria:

- All release gates are automated or have an explicitly owned approval step.
- The previous verified release and its feed evidence remain available.
- A release operator can build a candidate, inspect evidence, approve publication, and exercise rollback without editing artifacts by hand.

## Recorded Follow-up: Code and Secret Exposure

This section preserves evidence but authorizes no implementation in this task.

- `xenix.spec` currently copies a broad plain-Python tree into `xenix_worker_source` for SSH workers. Protecting or minimizing that bundle is explicitly deferred because worker algorithm exposure is accepted here.
- PyInstaller bytecode, PyArmor, Cython, and Nuitka can only raise reverse-engineering cost on a user-controlled machine; none makes embedded secrets unextractable.
- Generated trial provider credentials and trial-lock secrets must be treated as extractable. Public distribution must not rely on them as an authorization or anti-tamper root.
- A future security task may move trial access behind a server-controlled quota/token boundary and evaluate a minimal worker bundle or compiled crown-jewel modules. That work must not be silently folded into the distribution slices above.
