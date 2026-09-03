# Windows Distribution

Xenix ships as an unsigned per-user Velopack Setup for Windows 10 1809 x64 or
later. `pyproject.toml` owns SemVer; `release.toml` owns release protocol,
immutable package identity, channel, runtime, and pinned release tools.
`%LOCALAPPDATA%\Xenix` remains user-state authority and is not the Velopack
installation root.

The native Knowledge OCR component is a separate immutable release artifact. It
is downloaded only after the user chooses local OCR setup and is not embedded in
Setup.

## Promotion and Release Authority

`develop` is the integration line. Promote it through a same-repository
`develop -> main` pull request. Native CI is scoped to PRs targeting `main`; its
single stable `Native CI` check is required. Do not locally merge and push `main`.
A task-specific `feat/* -> main` draft PR is a documented exception for CI
acceptance against a clean `main` baseline; it never merges. Do not open ordinary
feature-branch PRs directly to `main`.

Merging the promotion PR creates a release-eligible `main` result but publishes
nothing. The only release authorization is a pushed immutable
`v<project-version>` tag on the current or any historical eligible promotion
result. The selected commit must:

- be the recorded merge outcome of exactly one same-repository
  `develop -> main` promotion PR;
- occur in `origin/main` first-parent history;
- contain the supported release protocol;
- declare the same project version as the tag.

Promotion CI is the test authority for the reviewed source. The tag workflow
re-verifies release identity, runs repository checks, and builds and exercises the
packaged application from the exact tag commit; it does not serially repeat the
same semantic pytest shards.

GitHub resolves a push-triggered workflow from the event's tagged commit/ref.
Consequently, a historical promotion is eligible only if that commit already
contains this supported workflow/protocol. The local preflight is mandatory:
tagging a pre-protocol commit can produce no remote workflow run rather than a
remote rejection.

## One-Tag Release Procedure

Start from a clean checkout with current refs and the GitHub CLI authenticated:

```powershell
git fetch origin main:refs/remotes/origin/main --tags
git switch --detach <eligible-promotion-sha>
git tag v<version>
pdm run release-identity --require-tag --require-promotion --repository xiaoland/Xenix
git push origin refs/tags/v<version>
```

If the local preflight fails, correct the source/version through `develop`; an
unpushed local tag may be removed and recreated. Never move or delete a pushed
release tag. A product defect consumes that version and requires another
promotion plus a new version. A transient workflow, runner, or network failure is
retried from the unchanged tag and commit.

The tag starts the only `Native Release` workflow:

1. a secretless job verifies tag, version, commit, promotion PR, `main`
   first-parent membership, and release-protocol identity;
2. the `native-release` Environment admits the verified `v*` ref and supplies
   release configuration and secrets;
3. the Windows job re-verifies the identity and repository checks on the tag SHA;
4. locked OCR inputs/output are restored when available, but the native runtime
   identity and self-test must pass before a cached output is trusted;
5. packaging, packaged smoke, Velopack, and manifest generation bind their
   evidence to the tag commit and promotion PR;
6. the publisher uploads and verifies immutable public objects, reconciles Setup
   projections, updates non-authoritative feeds, and writes
   `releases.win-x64-stable.json` last as the visibility commit point;
7. public SHA-256, HTTP Range, and cache metadata checks complete before success.

There is no private pre-publication prefix, copied manifest digest, second
dispatch, or second release approval.

## Publication Contract

The release manifest records schema/protocol version, SemVer, tag, commit,
promotion PR, workflow run/attempt, toolchain, dependency-lock hash, packaged
smoke result, and every artifact's path, size, type, and SHA-256.

The publisher is a single globally serialized writer. It:

- verifies all local artifacts before the first remote mutation;
- creates versioned package, OCR, and manifest objects with overwrite forbidden;
- accepts an existing immutable object only if the public bytes match;
- uses multipart/resumable upload with progress for large files;
- rejects a normal release older than the live canonical feed;
- snapshots every existing mutable feed and Setup projection under
  `published/publication-history/<tag>/<run-attempt-time>/`;
- updates the generated Setup name and `Xenix-Setup.exe`, then legacy/assets
  feeds, and finally the canonical JSON feed;
- verifies public hashes and Range behavior throughout.

OSS cannot atomically replace all mutable projections. A failure before the
canonical feed update leaves the previous release authoritative, although
intended-public unreferenced files or partially updated projections can exist.
The unchanged-tag retry deterministically converges. A conflicting immutable
object fails closed.

The bucket stays private by default. Anonymous read exposes only `published/*`.
Routine writes to that prefix outside the release/rollback writer are prohibited.
Directly uploaded version files can be guessed before the feed changes; this is
accepted because they are intended public artifacts and contain no user document
data.

## Native OCR Release Gate

The app package embeds only the native OCR catalog. The manifest admits the OCR
archive from its approved output root as a typed artifact and fails if catalog
and archive identity disagree.

The OCR catalog names its archive by runtime ID plus the archive's complete
SHA-256. The public object key is therefore content-addressed: separate build
bytes can coexist safely, while each packaged client remains bound to one exact
catalog hash.

Packaged smoke installs the already-built locked OCR generation offline, runs its
native self-test and golden-image recognition through the spawned Knowledge
worker, imports the image, derives bounded Units, reaches keyword lookup, and
checks the recorded runtime generation. It also imports valid DOCX and PPTX
documents through the frozen worker and retrieves bounded presentation text.
Native runtime verification runs the extracted worker from a foreign working
directory after the builder PaddleOCR checkout has been made unavailable, and scans
released binaries for real builder paths. Activation or a parser-helper exercise
alone is insufficient.

## GitHub Controls

Before enabling the workflow:

- protect `main` with pull-request-only changes, deletion/force-push prevention,
  and required check `Native CI`;
- protect `refs/tags/v*` from deletion and non-fast-forward updates;
- create the `native-release` Environment with a custom deployment policy that
  admits `v*` tags only and has no second required reviewer or wait timer;
- move the release variables/secrets below to `native-release`;
- remove the superseded release Environments after confirming no workflow refers
  to them.

Audit the effective repository controls after any ruleset or Environment change:

```powershell
pdm run release-controls-audit --repository xiaoland/Xenix
```

The audit is read-only and fails if the stable gate, main/tag immutability, ref
policy, Environment, or single-workflow contract drifts.

## Credentials and Configuration

Use the dedicated RAM AccessKey only in `native-release` Environment secrets.
Never place it in repository variables, client configuration, artifacts, or logs.
Replace the bucket placeholder in `aliyun-ram-policy.example.json`. Rotate on the
owner-approved cadence and immediately after suspected disclosure.

Required values:

- secrets: `ALIYUN_ACCESS_KEY_ID`, `ALIYUN_ACCESS_KEY_SECRET`,
  `XENIX_TRIAL_LLM_API_KEY`, `XENIX_TRIAL_LOCK_STATE_SECRET`;
- variables: `OSS_ENDPOINT`, `OSS_BUCKET`, `RELEASES_OSS_PUBLIC_URL`,
  `XENIX_TRIAL_LLM_BASE_URL`, `XENIX_TRIAL_LLM_MODEL`,
  `XENIX_TRIAL_LOCK_DAYS`, and `XENIX_TRIAL_PURCHASE_URL`;
- optional `XENIX_OTEL_*`, `OTEL_SDK_DISABLED`, and `OTEL_EXPORTER_*`
  values/secrets.

`RELEASES_OSS_PUBLIC_URL` is the native HTTPS bucket URL ending in `/published`.
The client feed and stable Setup URLs derive from it. Build-time trial credentials
and OTLP headers embedded in the package are extractable; they are not client-side
secrets.

## Time and Evidence Budget

Measure controlled job execution separately from GitHub event/runner/Environment
queue time.

| Boundary | Acceptance budget |
| --- | --- |
| Promotion Native CI | median `<= 12 min`, no qualifying run `> 15 min`, over at least five successes; queue time reported separately |
| Cold tag release to canonical feed | `<= 90 min` |
| Direct upload plus remote verification | `<= 30 min` |
| Interrupted-upload same-tag retry | `<= 70 min` |
| Mutable projections plus final verification | `<= 5 min` after immutable verification |
| Progress | transfer heartbeat at least every `60 s`; other active steps no more than `2 min` silent |
| Operator hands-on time | `<= 5 min` |

The workflow preserves its non-secret manifest, OCR catalog, and publication timing
evidence for 30 days; Actions logs record named phase/progress output. The
publication timing file records total publisher time and the interval from
verified immutable objects through final visibility verification. Retain the run
URL, tag, commit, promotion PR, run attempt, result, duration, manifest, and
rollback-history key as release evidence.

Generate the rolling controlled/calendar/queue report with:

```powershell
pdm run release-timings --repository xiaoland/Xenix
```

After the minimum samples exist, add `--strict` to fail unless both the Promotion
CI and cold Release controlled-time budgets pass.

## Failure and Rollback Boundary

A normal release never publishes an older version over a newer canonical feed.
Rollback is an exceptional, separately authorized restoration of one verified
publication-history snapshot through the exclusive writer, with the canonical
feed restored last. It does not delete package objects, move tags, downgrade
installed clients, or restore SQLite.

Before every client update apply, Xenix creates and verifies a database backup
under `%LOCALAPPDATA%\Xenix\state\update-backups` and retains the latest three.

Before first public visibility on a materially changed packaging/runtime path,
complete the clean Windows 10 LTSC 2019 and current Windows 11 acceptance in the
distribution modernization worksheet. Record Unknown Publisher, SmartScreen, and
Defender behavior honestly; do not describe unsigned artifacts as authenticated
publisher output.
