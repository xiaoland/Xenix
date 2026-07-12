# Distribution Modernization Preflight Rehearsal

## Purpose

This is a paper execution of `implementation-steps.md`, performed before product code or release infrastructure is changed. It identifies branch points, missing authority, long-lead external work, and assumptions that need an explicit proof.

The architecture remains viable. The rehearsal found that the critical path is not simply packaging followed by publication:

```text
identity/version decisions
  -> reproducible unsigned build
  -> Velopack lifecycle without automatic apply
  -> application activity/shutdown/backup boundary
  -> local installed-update proof
  -> explicit unsigned-release gate
  -> OSS AccessKey/public endpoint proof
  -> OSS single-writer feed publication
  -> first public release
```

## Highest-Impact Findings

1. Velopack startup auto-apply must be disabled. Otherwise a downloaded update may be installed by the early lifecycle hook before Xenix can check active work or back up SQLite.
2. Xenix has no application-wide activity or shutdown owner today. Main-window flags cannot account for daemon Agent/ML threads, spawned processes, analysis children, or SSH execution. This is a real prerequisite for safe apply, not UI polish.
3. Multiple GUI instances are not currently excluded. Another instance or frozen child can keep the Velopack `current` directory locked after the applying process exits.
4. The private personal GitHub repository may not have the artifact allowance or Environment approval rules assumed by the first plan. Candidate transfer and publication authority need explicit designs.
5. Signing is deferred, so the first release has no independent publisher identity. Hashes protect bytes only relative to the feed; compromise of the OSS/feed writer can replace both feed and unsigned package.
6. Alibaba Cloud OSS is compatible with Velopack's static HTTPS source. The first release uses the native Bucket HTTPS domain and avoids custom-domain ICP/TLS and CDN dependencies; publish still needs a deliberate single-writer protocol because OSS PutObject lacks destination CAS.
7. Current size remains operationally important: about 935 MiB installed and 386.6 MiB compressed. GitHub artifact allowances, cross-border upload time, OSS bandwidth, and local update disk space all need measured gates.

## Decision Register

The `Blocking point` column is the latest safe time to decide; it does not mean all decisions must block Step 1.

| ID | Decision or required information | Recommended default | Blocking point |
| --- | --- | --- | --- |
| D01 | Exact immutable `packId` | Reverse a controlled domain, for example `dev.example.xenix` for `example.dev`; never use `Xenix` | Before Step 2 |
| D02 | Product/display identity | Decided: product/brand `Xenix`, Chinese name `择析`; author/publisher display text still needs confirmation | Before Step 2 |
| D03 | First public SemVer | Decided: `1.0.0`; make `pyproject.toml` authoritative and tag `v1.0.0` an immutable command | Step 1 input |
| D04 | Official build Python patch | Decided process: compare supported candidates with full package/smoke, then pin one exact patch; do not inherit runner latest | During Step 1 |
| D05 | Minimum Windows version | Decided: Windows 10 1809/build 17763 x64; verify on fully patched Enterprise LTSC 2019 and current Windows 11 | Before public release |
| D06 | Existing ZIP users | Treat Setup as a new installation mechanism that reuses `%LOCALAPPDATA%\Xenix`; no automatic migration from a running portable executable is assumed | Before website switch |
| D07 | Automatic download policy | Auto-check, but require download approval initially; revisit after measuring full/delta sizes and disk use | Before Step 3 UX |
| D08 | Apply with active work | Refuse and offer “later”; do not cancel ML/Agent/SSH work just to update in the first release | Before Step 4 |
| D09 | Stale/remote task reconciliation | Only live runtime leases block apply. On next startup, reconcile unrecoverable local work as interrupted/failed; retain remote evidence without sending an implicit kill | Before Step 4 |
| D10 | Backup frequency and retention | Backup SQLite before every explicit apply, verify it, retain the latest three successful backups, and never auto-run an old binary against a migrated DB | Before Step 4 |
| D11 | Native N-1 fixture | Use two unsigned internal versions for rehearsal; freeze the first verified installed release as the durable N-1 fixture | Step 2 |
| D12 | Authenticode | Decided: deferred outside this task; preserve the integration seam and record unsigned risk | Follow-up task |
| D13 | Unsigned user experience | Record Unknown Publisher/SmartScreen/Defender behavior and acceptable support guidance on clean VMs | Step 5 |
| D14 | Independent update authenticity | No Authenticode or signed manifest exists in this task. Decide whether OSS writer security alone is an accepted first-release risk | Before public publication |
| D15 | GitHub plan and approval semantics | Verify private-repo Environment rules. If peer approval is unavailable, use two explicit invocations bound to version/commit/digest and describe the weaker authority honestly | Before Step 6 |
| D16 | Candidate byte transfer | Decided: one private OSS bucket; immutable `candidates/<version>/<manifest-sha256>/` objects are copied after approval into `published/` | Before CI/CD split |
| D17 | Release operator and second approver | Name both if real separation of duties is desired. If only one person exists, do not claim a two-person gate | Before publish workflow |
| D18 | OSS authority | Decided: one dedicated least-privilege long-lived RAM AccessKey spans both prefixes in one bucket; separate identities and OIDC/STS are rejected. Anonymous read is restricted to `published/*`; public delivery uses the native Bucket HTTPS domain | Before Step 6 |
| D19 | OSS network gate | Define GitHub-runner upload and China three-network download throughput/success thresholds, Range behavior, resumable upload, and cost alerts | Before OSS becomes authoritative |
| D20 | Stable website Setup URL | Use the stable public OSS Setup alias with `no-cache`, updated after feed publication | Before Step 7 |
| D21 | Package retention | Retain all full/delta packages initially; define pruning only after skipped-version and rollback behavior is measured | Before first deletion policy |
| D22 | Feed publication conflict model | OSS has no destination CAS. Use exclusive writer/concurrency, re-read old hash, atomic PutObject, immutable feed snapshots, and no routine console writes; strict CAS would require another control plane | Step 6 |
| D23 | Trial behavior in public Setup | Decided: keep the current embedded trial LLM and trial-lock implementation; explicitly accept API-key theft and trial-lock bypass risk. Treat both secrets as extractable and maintain rotation/revocation procedures | Accepted for first public release |
| D24 | Frozen release configuration | Implemented: `RELEASES_OSS_PUBLIC_URL`, `XENIX_TRIAL_*`, `XENIX_OTEL_*`, `OTEL_SDK_DISABLED`, and `OTEL_EXPORTER_*` settings are build inputs projected through one Pydantic model into one generated frozen config. `XENIX_TRIAL_PURCHASE_URL` replaces `TRIAL_PURCHASE_URL`; feed/Setup URLs derive from the release URL | Verify before next candidate |

## Step-by-Step Simulation

### Step 0 — Identity and external readiness

Known repository values are not yet durable release identity:

- Application organization is currently `xiaoland`.
- The website example uses `r2.lanzhijiang.dev`.
- Versions currently disagree between `1.0.0`, `0.1.0`, and tag `v0.1.0`.

Do not infer the legal publisher, durable domain, or first public version from those strings. Gather:

- controlled domain and intended release hostname;
- Alibaba Cloud account legal subject and RAM administrator; `Xenix`/`择析` are product names unless they exactly match the registered entity;
- OSS activation, Bucket endpoint, prefix policy, and traffic-budget ownership;
- GitHub plan/budget and the identities allowed to create tags, publish, and roll back;
- primary user geography and expected release frequency.

Long-lead work can start in parallel with Steps 1–4: OSS setup, least-privilege RAM policy and AccessKey rotation design, GitHub plan confirmation, and clean Windows VM preparation.

### Step 1 — Reproducible baseline

Branch: “reproducible” can mean byte-identical or controlled/traceable. Authenticode timestamps, PE timestamps, and hosted-runner image changes make byte-identical output an expensive and unnecessary promise. Use controlled inputs plus a complete manifest.

Required proofs:

- exact Python/PDM/PyInstaller versions and runner image version are recorded;
- the PDM lock is used without re-resolution;
- SemVer, Windows numeric file version, diagnostics, `vpk` version, tag, and commit are consistent;
- actions are pinned to immutable revisions before signing authority is introduced;
- release mode proves the required trial configuration is present without logging values, keeps the trial-lock HMAC secret stable across compatible releases, and records rotation/revocation plus the fact that both embedded secrets are extractable;
- build-generated secret modules live outside the checkout or are removed even when generation fails before the current `try/finally` begins.

Cost branch: run the official Python on PRs; run the wider supported-Python matrix on main/nightly unless the GitHub budget supports every PR. Do not upload the 935 MiB raw onedir tree as a routine CI artifact.

### Step 2 — Velopack lifecycle and install

The lifecycle hook must be the first meaningful packaged operation and run exactly once in GUI, smoke, analysis-child, and multiprocessing modes. Disable startup auto-apply on day one.

Step 2 does not yet contain `UpdateManager`, so its proof should be:

- clean Setup install/uninstall and stable shortcut;
- runtime state remains outside the installation and survives uninstall;
- low-level full-package apply works;
- a delta reconstructs exactly the new full package;
- every frozen process mode starts without recursive lifecycle handling.

Feed discovery and download belong to Step 3. Generate two honest internal builds rather than relabeling identical bytes with two `vpk` versions. Suppress/discard portable output. Fetch the previous full package before later release builds or no real delta will be generated.

Measure at this step:

- Setup/full/delta bytes and build time with/without UPX;
- cold/warm startup;
- disk required during download, delta reconstruction, extraction, and rollback cleanup;
- number of PE files and signature state;
- Defender result on unsigned internal packages, recognizing that unsigned warnings are expected.

### Step 3 — Check and download

The Python SDK is synchronous, so one update executor must own each check/download session and publish state to Qt through signals. Concurrent manual and automatic checks must coalesce or reject cleanly.

Recommended first behavior:

- check after the main window is usable;
- throttle checks with a persisted last-check time;
- never block startup or show a modal error for ordinary network failure;
- ask before the first download until actual delta/full size is known;
- persist ready-to-restart state;
- never rely on next-start automatic apply.

Unknowns to prove include proxy/TLS behavior, HTTP `Range` support, disk-full handling, download resume semantics, and the user-visible location of Velopack logs.

### Step 4 — Admission, shutdown, backup, and apply

Current runtime reality makes this the largest structural slice:

- `MainWindow` has no application shutdown contract;
- Agent and ML work uses daemon threads;
- local work spawns child processes whose ownership is not exposed centrally;
- SSH execution can remain blocked remotely;
- the storage engine is not disposed on normal GUI exit;
- persisted task rows can be stale after a crash.

Create one admission/activity coordinator. Normal work acquires leases; update apply atomically acquires an exclusive lease that also stops new work. Only live current-process leases block apply. Persisted rows are recovery evidence, not live locks.

Recommended handoff sequence:

```text
acquire exclusive update admission
  -> create and independently verify SQLite backup
  -> record target update state
  -> successfully launch the updater waiting for this PID
  -> stop UI admission and release owned children/threads
  -> dispose storage, flush/shutdown telemetry and logging
  -> quit within Velopack's wait window
  -> next launch reconciles actual installed version with target state
```

If updater launch fails, the visible application must remain usable; therefore do not tear down resources first. Initial behavior for any active lease is refusal/defer, not automatic cancellation. A single-instance gate must exclude internal worker modes while preventing a second GUI from locking `current`.

Backup scope is SQLite, not the entire potentially large runtime home. Record DB hash/schema/from/to versions and keep the partially migrated DB, backup, and logs on failure. Decide separately whether a manual restore UI is in this task; automatic restore is not recommended.

### Step 5 — Unsigned release posture

Authenticode is deliberately deferred. The release gate must therefore prove the expected Windows warning path and communicate its limitations:

- `Setup.exe`, `Update.exe`, `xenix.exe`, and application PE files do not carry a Xenix publisher signature;
- Windows may show Unknown Publisher, SmartScreen, or Defender warnings even when SHA-256 matches release evidence;
- hashes protect transfer integrity only relative to the downloaded feed/manifest;
- compromise of the sole OSS/feed writer can replace both feed and unsigned package, so RAM least privilege, AccessKey hygiene/rotation, and publication isolation are the primary release security controls;
- the Velopack signing seam and PE inventory remain recorded for a later task.

Do not use wording such as “trusted installer”, “verified publisher”, or “signed update” in the product/site/runbook until Authenticode is actually present.

### Step 6 — Candidate transfer and OSS publication

This private repository and package size make cross-job transfer a first-class decision. The selected path is one private OSS bucket: upload the exact candidate under an immutable digest-bound `candidates/` key, then copy approved bytes into `published/`. GitHub artifacts and protected rebuilds are not the selected transfer authority.

Do not reuse the website's Cloudflare token. Use the explicitly approved single long-lived RAM AccessKey, scoped to the exact bucket, both prefixes, and required operations. Store it only in the protected `native-candidate` and `native-publish` GitHub Environments and define rotation/revocation ownership. This intentionally does not isolate candidate authority from publish authority: compromise of the credential can modify `published/`, including the unsigned feed.

Publication transaction:

```text
upload candidate to private candidates/ prefix and record SHA-256
  -> same-bucket copy versioned assets to published/
  -> reject conflicting same-name assets
  -> verify public OSS GET/HEAD/Range/hash
  -> snapshot old feed bytes/hash to immutable history
  -> re-read live feed and compare old hash
  -> atomic PutObject new feed with Content-MD5
  -> fetch feed through the public OSS URL and compare bytes/hash
  -> update stable Setup alias
  -> verify alias and emit release evidence
```

OSS PutObject does not support destination `If-Match`, so this is intentionally single-writer check-then-put rather than CAS. GitHub publish concurrency must queue rather than cancel, the `native-publish` Environment is the approval gate, and routine console writes are forbidden. Versioned packages are long-cached; feeds and the Setup alias use `no-cache`. Anonymous policy must refuse `candidates/`.

Rollback verifies the current bad-feed hash, restores an immutable previous feed snapshot under the same single-writer rule, then restores the Setup alias. It does not delete the bad package immediately, downgrade installed clients, or roll back SQLite.

### Step 7 — Website

The current site tells users to download a ZIP, extract it, and run `xenix.exe`; this must change with the first Setup release.

The Worker receives `XENIX_DOWNLOAD_URL` at deployment, so merely changing a GitHub variable does not update the live Worker. Re-deploying the website Worker for every desktop release would couple desktop publishing to website/D1 authority. Prefer a stable Setup alias so the existing configured URL remains stable.

If feed publication succeeds and alias update fails, existing installs may update while new visitors still receive the previous Setup. This is safe because the old Setup can update after launch, but it requires an alert/retry and must not be reported as “website points to latest” until repaired.

### Step 8 — Rehearsal and rollout

GitHub-hosted Windows runners are insufficient for every acceptance case. Assign an owner for a clean interactive Windows VM to test:

- Windows 10 1809+ and Windows 11 if both are promised;
- ordinary non-admin user and Chinese profile path;
- Defender/SmartScreen, shortcuts, Apps & Features, uninstall, locked files, hard-killed updater, and second instance;
- multiple Mainland China ISPs/regions for Setup/full/delta downloads;
- representative conversations, settings, install id, datasets, app-owned files, models, artifacts, ML worker settings, and trial state across update;
- N-to-N+1 and skipped-version update, corrupt download, no disk space, interrupted apply, migration failure, and feed/alias rollback.

Velopack channels are embedded in packages. A rehearsal-channel package is not necessarily the exact stable-channel package; use rehearsal to validate mechanics, then perform the unsigned stable candidate install/update test before publication.

## External Readiness Checklist

Gather these items now because they can delay implementation even though they do not block early local work:

- [x] Alibaba Cloud OSS activation and Hangzhou Bucket creation.
- [x] Native OSS Bucket HTTPS domain selected; custom domain, ICP, and CDN are not release dependencies.
- [ ] GitHub plan, Actions artifact quota/budget, Environment protection capability, release operator, and real approver count.
- [x] Candidate transfer decision: one private OSS bucket with immutable `candidates/` and public-origin `published/` prefixes.
- [x] OSS region/bucket, anonymous-read `published/` policy, private `candidates/`, single RAM identity, Environment secret names, and native public URL configured.
- [ ] GitHub upload and China three-network download test locations, throughput/success thresholds, Range/206, and fallback owner.
- [x] First public SemVer `1.0.0`, display identity `Xenix`/`择析`, and minimum Windows 10 1809/build 17763 x64.
- [ ] Immutable pack identity, author/publisher display text, official Python patch chosen by Step 1, and stable OSS hostname.
- [x] Explicitly accept publishing the current embedded trial LLM/trial-lock implementation with extractable secrets, API-key theft risk, and bypassable client-side locking.
- [ ] Clean interactive Windows VM and, if SSH worker execution is in the release gate, a disposable Linux SSH worker.

## Recommended Next Move

Signing procurement and D23 are no longer on this task's critical path. Step 1 is approved and begins with the Python candidate comparison and release-baseline implementation. Resolve D01, remaining D02 display text, and OSS identity inputs before their Step 2/6 boundaries. In parallel, prepare the RAM AccessKey policy/rotation process, OSS upload/download benchmarking, GitHub plan confirmation, and test VMs.

Before Step 2, resolve pack identity. Before Step 4, approve the activity/single-instance/backup boundary as its own cross-owner design. Before Step 5, explicitly accept the unsigned installer warning posture. Before Step 6, settle the exact single-identity RAM policy/AccessKey rotation, anonymous prefix restriction, and actual approval semantics. Before the next candidate, implement and verify D24.

## Evidence Consulted

Repository evidence:

- `xenix.spec`, `scripts/package_app.py`, `scripts/run_packaged.py`, and the current `dist/xenix` output;
- application construction and process ownership in `src/xenix/app.py`, `src/xenix/ui/main_window.py`, `src/xenix/services/ml_task_service.py`, and `src/xenix/services/ml/execution.py`;
- storage migration/recovery contracts in `docs/40-deployment/` and `src/xenix/services/storage/`;
- website download configuration and current GitHub workflows;
- connected GitHub repository metadata confirming `xiaoland/Xenix` is a private personal repository.

Volatile upstream facts were checked during the rehearsal and must be rechecked when their step begins:

- [Velopack integration lifecycle](https://docs.velopack.io/integrating/overview), [Python getting started](https://docs.velopack.io/getting-started/python), [packaging output](https://docs.velopack.io/packaging/overview), and [delta generation](https://docs.velopack.io/packaging/deltas);
- [GitHub Actions limits](https://docs.github.com/en/actions/reference/limits) and [deployment environments](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments);
- [OSS atomicity and strong consistency](https://help.aliyun.com/en/oss/user-guide/what-is-oss), [PutObject/create-only behavior](https://help.aliyun.com/zh/oss/developer-reference/putobject), [custom domains and ICP](https://help.aliyun.com/en/icp-filing/basic-icp-service/product-overview/use-oss), and [OSS acceleration](https://help.aliyun.com/en/oss/user-guide/transfer-acceleration);
- [Qt 6.11 supported Windows platforms](https://doc.qt.io/qt-6/supported-platforms.html);
- [Python 3.12 Windows support](https://docs.python.org/3.12/using/windows.html), which explicitly directs Windows 7 users to Python 3.8.
