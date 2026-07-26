# Final Simplified Design Review and Execution Simulation

## Verdict

Remove Candidate as a business state and delivery boundary. Its private object
prefix, separate Environment, copied digest, and second Publish dispatch cost more
than they protect for the current product. The immutable tag is sufficient release
authorization; the release manifest remains verification evidence.

The simplified authority model is:

| Authority | Meaning |
| --- | --- |
| `develop` | mutable integration work; pushes alone do not run Native CI |
| completed `develop -> main` promotion PR | a release-eligible `main` snapshot |
| immutable `vX.Y.Z` tag | sole Release SHA lock, human authorization, and workflow trigger |
| authoritative public feed | user-visible release commit point |

## Why Candidate Is Removed

- Tag creation already expresses the operator's release decision and locks source.
- Candidate and Publish currently share one OSS identity, so the private/public
  split is not a meaningful credential boundary.
- No independent Candidate acceptance is currently performed; the copied digest is
  an error-prone manual handoff rather than valuable review.
- Versioned packages are intended to become public and contain no user documents.
  A directly uploaded but unreferenced package being guessable before feed update
  is an acceptable low-impact tradeoff.
- The safety properties that matter do not require Candidate: exact Tag SHA,
  create-only version artifacts, byte verification, feed-last visibility,
  single-writer publication, idempotent retry, and rollback history.

Candidate must not return indirectly as a renamed durable staging domain, mandatory
GitHub artifact approval, or private manifest identity. A transient build directory
and ordinary caches are implementation details, not release states.

## Historical Tag Eligibility

A tag may select any prior completed promotion result rather than only current
`main` head:

1. the target equals the completed merge outcome recorded for a same-repository
   PR whose head is `develop` and base is `main`;
2. it appears in `origin/main` first-parent history;
3. it contains the supported tag-triggered workflow/release-protocol version;
4. `vX.Y.Z` matches the project version at that commit.

This excludes a merged side-branch ancestor, direct-push commit, partial rebase
sequence, or pre-protocol historical commit. Because GitHub executes the workflow
definition present at the tag ref, "historical" necessarily means
release-protocol-compatible history.

## Intended Workflow

### Promotion

Native CI exists only for an active same-repository `develop -> main` PR. A stable
aggregate check gates merge. An ordinary push to `develop` or `main` does not run
Native CI or release. Main rules forbid direct push; tag rules forbid moving or
deleting `v*`.

### Release

Pushing one eligible tag starts `Native Release`:

1. secretless identity/promotion/protocol preflight;
2. exact-Tag-SHA check/tests and Release Readiness;
3. native OCR, frozen application, packaged smoke, and Velopack assembly;
4. release manifest generation;
5. direct create-only upload to final versioned public keys;
6. remote size/hash/Range verification;
7. reconciliation of non-authoritative mutable projections;
8. update of the authoritative visibility/feed object last;
9. final public verification and release evidence.

The release job enters one `native-release` Environment restricted to `v*`.
Release secrets never enter Promotion PR jobs. There is no second reviewer by
default because creating the tag is already the explicit human release approval.

## Execution Simulation

| Scenario | Expected transition and invariant |
| --- | --- |
| Normal release | Promotion PR passes and merges; operator tags an eligible result; exact Tag SHA passes build/smoke; immutable objects upload and verify; non-authoritative projections converge; authoritative feed changes last; final verification closes release. |
| `main` advances before release | An older result remains eligible only when promotion outcome, first-parent history, protocol, and version agree. Every release step uses the historical Tag SHA; current `main` code cannot leak in. |
| Promotion PR fails | Required gate blocks merge. There is no release identity or secret-bearing job. |
| Invalid tag target/version | Mandatory local secretless preflight rejects it before push. Supported-protocol targets repeat the check remotely; a pushed invalid supported-protocol tag consumes the version without receiving release secrets. A pre-protocol target may instantiate no remote workflow, which is why local preflight is mandatory. |
| Product or packaged defect after tagging | Release stops. Tag never moves. Fix returns through `develop -> main` and uses a new version. |
| Runner/tool/network transient failure | Rerun the unchanged tag. Reuse is allowed only for outputs objectively bound to the same identity. |
| Direct upload is interrupted | Some intended-public version objects may exist but are not feed-referenced. Rerun accepts only byte-identical objects and continues; conflict stops release. |
| Remote verification fails | Authoritative feed remains old. Repair infrastructure and rerun the same tag; do not create a second release state. |
| Mutable projection update fails before the authority | Previous authoritative feed remains active. Rerun reconciles projections from the same tag/manifest. |
| Failure after authoritative feed update | The workflow fails with its prior-state history retained. Rerun the same tag to verify/reconcile first; explicit rollback uses the recorded snapshot if required. No separate durable release state is introduced. |
| Two tags are close together | Builds may overlap only if resource policy permits. Public publication is globally serialized and normal release rejects version regression. |

## Residual Complexity Worth Keeping

- PR/ref/tag eligibility checks prevent publishing unreviewed source.
- Exact Tag SHA validation prevents PR temporary-merge evidence from being mistaken
  for release evidence.
- Direct immutable upload and remote hash verification prevent silent replacement.
- One authoritative feed commit point is necessary because OSS cannot atomically
  update all feeds and the stable Setup alias.
- Progress, timeout, and diagnostics are necessary because v1.2.0 showed that
  silent long-running work causes destructive operator guesses.

These are safety and observability contracts inside one release workflow, not a
multi-stage Candidate system.

## Performance Acceptance

The simplified topology is not accepted merely because it has fewer workflow
objects. It must demonstrate:

- Promotion CI median `<= 18 min` and no qualifying run over `25 min` across five
  successes;
- cold tag-to-visibility controlled execution `<= 90 min`;
- current-sized direct upload plus remote verification `<= 30 min`;
- interrupted-upload same-tag retry `<= 70 min`;
- final visibility update and public verification `<= 5 min`;
- transfer progress at least every `60 s`, no other active step silent over
  `2 min`, and operator hands-on time `<= 5 min`.

Runner/environment queue time is recorded separately from controlled execution, so
the report shows both engineering performance and the operator's calendar wait.

## Local Implementation Result

- Candidate/Publish repository workflows and scripts are replaced locally by one
  tag-triggered `Native Release`.
- Manifest v3 and the direct-public writer bind version, tag, commit, promotion,
  workflow, toolchain/config, smoke, and artifact evidence.
- `releases.win-x64-stable.json` is the named final visibility update; Setup and
  other feeds converge before it, with rollback snapshots retained.
- Native OCR cache restore is followed by catalog/hash checks and the actual native
  self-test. Release Readiness covers both secondary-window open orders and
  worker/thread/SQLite quiescence.
- Workflow timing evidence plus `release-timings` separate controlled, calendar,
  and queue clocks and refuse to count legacy Native CI runs as qualifying
  Promotion samples.
- Local checks pass. GitHub rules/Environment application, safe rehearsal, and
  measured budget acceptance remain intentionally open until the code is
  committed, pushed, and promoted.
