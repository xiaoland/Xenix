# Windows Distribution

Xenix ships as an unsigned per-user Velopack Setup for Windows 10 1809 x64 or later. `pyproject.toml` owns SemVer; `release.toml` owns immutable package identity, channel, runtime, and pinned release tools. `%LOCALAPPDATA%\Xenix` remains user-state authority and is not the Velopack installation root. The optional native Knowledge OCR component is a separate immutable release artifact downloaded only after the user chooses local OCR setup; it is not embedded in Setup.

## Candidate Gate

Create tag `v<version>` on the exact release commit, then manually run `Native Release Candidate` for that tag. The workflow requires the protected `native-candidate` environment and fails unless the complete frozen release configuration is valid. It builds and verifies the pinned native OCR bundle before the app, then runs check, the full test suite, PyInstaller package, packaged smoke, Velopack pack, and uploads every manifest-approved immutable artifact under `candidates/<version>/<manifest-sha256>/` in the private release bucket.

Record the printed `version` and `manifest_sha256`. Setup, Update, `xenix.exe`, and bundled PE files are intentionally unsigned. SHA-256 proves equality to the reviewed manifest, not publisher identity if the OSS/feed writer is compromised.

The app package embeds only the native OCR catalog. The candidate manifest admits
the OCR archive from its approved output root as a typed artifact, and public builds
fail if the catalog or archive identity is absent or inconsistent. The client later
derives that immutable artifact URL from the same configured published origin used
by the release; it never resolves Paddle dependencies from upstream.

Packaged smoke must receive the already built locked OCR archive and golden image.
It installs/verifies that generation offline, imports the image through the spawned
Knowledge worker, derives bounded Units, reaches keyword lookup, and checks that the
canonical pipeline recorded the same runtime generation. Activation or self-test
alone is not sufficient release evidence. Independently, packaged smoke creates a
valid DOCX and PPTX, imports both through the frozen app's spawned Knowledge worker,
derives the presentation, and retrieves its bounded text. A direct parser-helper
exercise or collecting the Word backend alone is not sufficient.

## Production Publication

Run `Native Publish` with the exact candidate version and manifest SHA-256. The protected `native-publish` environment owns the approval boundary. Publish concurrency queues and never cancels. Both workflows intentionally use the same RAM AccessKey; compromise of that identity can mutate both prefixes.

The publication tool:

1. authenticates the approved candidate manifest digest;
2. copies immutable packages into `published/` with overwrite forbidden;
3. verifies the public OSS URL through SHA-256 and HTTP Range requests;
4. snapshots prior feeds under `publication-history/<UTC>/`;
5. writes channel feeds last with `no-cache`;
6. updates and verifies `Xenix-Setup.exe` as the stable website alias.

OSS does not provide destination CAS for feed PutObject. This is a single-writer check-and-publish protocol; prohibit routine writes to `published/` outside the workflow. Bucket versioning must remain disabled because it conflicts with overwrite prevention. The bucket stays private by default; an anonymous-read bucket policy exposes only `published/*`, while `candidates/*` remains private. Public delivery uses the native HTTPS Bucket domain and does not require a custom domain, ICP filing, or CDN.

## Credentials

Use the dedicated RAM AccessKey only in GitHub Environment secrets. Never place it in repository variables, client configuration, artifacts, or logs. Replace the bucket placeholder in `aliyun-ram-policy.example.json`. Rotate on the owner-approved cadence and immediately after suspected disclosure.

Required environment values:

- `ALIYUN_ACCESS_KEY_ID`, `ALIYUN_ACCESS_KEY_SECRET` secrets;
- `OSS_ENDPOINT` and `OSS_BUCKET`;
- `RELEASES_OSS_PUBLIC_URL`, the native HTTPS Bucket URL including `/published`; the client feed URL and stable Setup URL are derived from it;
- `XENIX_TRIAL_LLM_BASE_URL`, `XENIX_TRIAL_LLM_API_KEY`, `XENIX_TRIAL_LLM_MODEL`;
- `XENIX_TRIAL_LOCK_DAYS`, `XENIX_TRIAL_LOCK_STATE_SECRET`, `XENIX_TRIAL_PURCHASE_URL`;
- optional `XENIX_OTEL_*`, `OTEL_SDK_DISABLED`, and `OTEL_EXPORTER_*` values.

These are build-time inputs. The candidate freezes them into one generated release configuration; installed clients do not require these environment variables. Any embedded trial credential or OTLP header is extractable.

## Rollback Boundary

Rollback republishes a verified prior feed snapshot through the same exclusive writer. It does not delete the bad package, downgrade installed clients, or restore SQLite. Before every explicit apply the client creates and independently verifies a database backup under `%LOCALAPPDATA%\Xenix\state\update-backups` and retains the latest three.

## Human Acceptance

Before first public visibility, complete `tasks/distribution-modernization/vm-readiness.md` on clean Windows 10 LTSC 2019 and current Windows 11 guests. Record Unknown Publisher/SmartScreen/Defender behavior honestly. Do not describe any artifact as signed, trusted-publisher, or independently authenticated.

Use `tasks/distribution-modernization/human-release-worksheet.md` as the operator checklist and evidence record.
