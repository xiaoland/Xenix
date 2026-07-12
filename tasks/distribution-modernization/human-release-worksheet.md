# Xenix 1.0.0 Human Release Worksheet

Use this sheet in order. Record identifiers and evidence, never secret values. Stop at the first failed gate; do not publish a locally built placeholder candidate.

## A. Permanent identity

- [x] Confirm Velopack `packId`: `dev.lanzhijiang.xenix`
- [x] Confirm unsigned Apps & Features publisher text: `Xenix`
- [x] Confirm channel: `win-x64-stable`
- [x] Confirm minimum OS: Windows 10 1809/build 17763 x64
- Decision owner/date: `2026-07-12 Lan_zhijiang`

These values become expensive or impossible to change after public installation.

## B. Repository and official Python

- [ ] Review the complete task diff; confirm no generated release-config file or real credential is present.
- [ ] Explicitly authorize and create the task commit, then push it.
- Commit SHA: `________________________________________`
- [ ] Run `Native Python Baseline` from the pushed commit.

| Python | Package seconds | Setup bytes | Full package bytes | Smoke | Startup evidence |
| --- | ---: | ---: | ---: | --- | --- |
| 3.12.10 |  |  |  |  |  |
| 3.13.14 |  |  |  |  |  |
| 3.14.6 |  |  |  |  |  |

- [ ] Select and record the official Python patch: `____________`
- Decision reason: `____________________________________________________________`
- [ ] Update the pin if the winner is not the provisional `3.14.6`, then rerun checks/package smoke.

## C. Alibaba Cloud resources

- Alibaba account/subject: `________________________________________`
- OSS region: `____________________`
- Private bucket: `________________________________________`
- OSS endpoint used by GitHub: `________________________________________`
- Public OSS URL including `/published`: `https://xenix.oss-cn-hangzhou.aliyuncs.com/published`
- Delivery domain: native OSS Bucket HTTPS domain; no custom domain, ICP filing, or CDN

- [ ] Bucket public-read is disabled.
- [ ] Bucket versioning is disabled.
- [ ] `candidates/` and `published/` prefixes are reserved for automation.
- [ ] Anonymous read serves only `published/*`.
- [ ] Anonymous access to `candidates/*` returns `403`.
- [ ] Object metadata honors the publication script's cache controls.
- [ ] HTTP GET, HEAD, and Range/206 work through the public URL.
- [ ] Bandwidth/cost alerts are configured; alert owner: `____________________`

## D. RAM AccessKey

- RAM identity name: `________________________________________`
- Policy name: `________________________________________`
- Rotation owner: `________________________________________`
- Rotation cadence/date: `________________________________________`

- [ ] Replace `REPLACE_RELEASE_BUCKET` in `aliyun-ram-policy.example.json`.
- [ ] Limit authorization to the selected bucket, `candidates/*`, `published/*`, and required Get/Put/List/copy behavior.
- [ ] Do not grant routine delete authority.
- [ ] Create one long-lived AccessKey and store it only in protected GitHub Environment secrets.
- [ ] Explicitly acknowledge: this one identity can modify both candidate and published content, including the unsigned feed.
- [ ] Test revocation/rotation without recording the key in this sheet.

## E. GitHub Environments

Create `native-candidate` and `native-publish`. Configure tag/ref restrictions and approval rules supported by the repository plan.

Common values in both Environments:

| Kind | Name | Configured |
| --- | --- | --- |
| secret | `ALIYUN_ACCESS_KEY_ID` | [ ] |
| secret | `ALIYUN_ACCESS_KEY_SECRET` | [ ] |
| variable | `OSS_ENDPOINT` | [ ] |
| variable | `OSS_BUCKET` | [ ] |
| variable | `RELEASES_OSS_PUBLIC_URL` | [ ] |

Additional `native-candidate` frozen product configuration:

| Kind | Name | Required/configured |
| --- | --- | --- |
| variable | `XENIX_TRIAL_LLM_BASE_URL` | [ ] |
| secret | `XENIX_TRIAL_LLM_API_KEY` | [ ] |
| variable | `XENIX_TRIAL_LLM_MODEL` | [ ] |
| variable | `XENIX_TRIAL_LOCK_DAYS` | [ ] |
| secret | `XENIX_TRIAL_LOCK_STATE_SECRET` | [ ] |
| variable | `XENIX_TRIAL_PURCHASE_URL` | [ ] |

Optional frozen telemetry configuration; configure only the signals actually intended for public clients:

| Kind | Name | Configured/not used |
| --- | --- | --- |
| variable | `XENIX_OTEL_EXPORT_TRACES` |  |
| variable | `XENIX_OTEL_EXPORT_METRICS` |  |
| variable | `XENIX_OTEL_EXPORT_LOGS` |  |
| variable | `OTEL_SDK_DISABLED` |  |
| variable | `OTEL_EXPORTER_OTLP_ENDPOINT` |  |
| variable | `OTEL_EXPORTER_OTLP_PROTOCOL` |  |
| secret | `OTEL_EXPORTER_OTLP_HEADERS` |  |
| variable/secret | signal-specific `OTEL_EXPORTER_OTLP_{TRACES,METRICS,LOGS}_*` |  |

- [ ] Privacy/telemetry owner approved which signals are enabled.
- [ ] Embedded OTLP headers/tokens are treated as extractable client credentials.
- [ ] No GitHub log or artifact exposes secret values.

## F. Interactive Windows test machines

Prepare the guests in `vm-readiness.md`:

| Guest | ISO/build | Fully patched | Snapshot name | Ordinary user | Chinese-path test |
| --- | --- | --- | --- | --- | --- |
| Windows 10 LTSC 2019 / build 17763 |  | [ ] |  | [ ] | [ ] |
| Current Windows 11 x64 |  | [ ] |  | [ ] | [ ] |

- [ ] Defender definitions are current.
- [ ] VM time, disk size, network mode, and activation/evaluation posture are recorded.
- [ ] Take clean pre-install snapshots.

## G. Private N-1 → N acceptance

- N-1 version/commit: `________________________________________`
- N version/commit: `________________________________________`
- Candidate manifest SHA-256: `________________________________________`

Run on both guests:

- [ ] One-click install, shortcuts, launch, Apps & Features, and uninstall.
- [ ] Expected Unknown Publisher/SmartScreen/Defender behavior recorded.
- [ ] Normal update and restart.
- [ ] Skipped-version update and real delta behavior.
- [ ] Second GUI instance refusal.
- [ ] Update refusal while ML/Agent/analysis work is active.
- [ ] Interrupted/corrupt download and interrupted apply.
- [ ] Low/no disk space behavior.
- [ ] Representative datasets, settings, conversations, models, artifacts, worker settings, install id, and trial state survive.
- [ ] Pre-apply SQLite backup exists, passes integrity check, and retention keeps the latest three.
- [ ] Migration failure and feed rollback are exercised without claiming database downgrade.

Evidence location: `____________________________________________________________`

## H. Mainland delivery gate

| Test location/network | Setup GET | Full GET | HEAD | Range/206 | Throughput | Result |
| --- | --- | --- | --- | --- | ---: | --- |
|  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |

- [ ] Results meet the chosen success/throughput threshold.
- [ ] Anonymous OSS requests cannot retrieve `candidates/*`.
- [ ] Traffic-abuse and budget alerts were observed or test-triggered.

## I. Public 1.0.0 release

- [ ] Confirm the release commit has passed all gates above.
- [ ] Create and push exact tag `v1.0.0` only after explicit authorization.
- [ ] Run `Native Release Candidate` on that tag.
- Candidate version: `1.0.0`
- Candidate manifest SHA-256: `________________________________________`
- Setup SHA-256: `________________________________________`
- [ ] Review manifest commit, lock hash, Python/tool versions, smoke result, artifact hashes, and `unsigned=true`.
- [ ] Approve exactly that version and manifest digest.
- [ ] Run `Native Publish` with the recorded values.
- [ ] Verify every feed-referenced package through the public OSS URL.
- [ ] Verify public feed hash and Range/206.
- [ ] Verify `<RELEASES_OSS_PUBLIC_URL>/Xenix-Setup.exe` matches the approved Setup hash.
- [ ] Set website `XENIX_DOWNLOAD_URL` to that stable Setup URL and verify the live download action.
- [ ] Record publication time and rollback-history key.

Publication UTC: `____________________`

Rollback history: `____________________________________________________________`

Release operator/approver: `____________________________________________________________`

## J. Stop/rollback triggers

Do not continue publication if any item is true:

- [ ] Version, tag, commit, or manifest digest differs from the approved values.
- [ ] A same-name immutable object has a different hash.
- [ ] Public OSS URL hash, HEAD, or Range verification fails.
- [ ] Candidate content is publicly reachable before approval.
- [ ] Secret values appear in logs/artifacts.
- [ ] VM state/update tests fail or user data integrity is uncertain.

Rollback only republishes a verified prior feed snapshot and Setup alias through `Native Publish` authority. It does not downgrade installed clients or restore SQLite automatically.
