# Native CI/CD Simplification

## Objective

Make native delivery routine, observable, and proportionate to the project:
`develop -> main` promotion is reviewed and tested once; an immutable SemVer tag on
an eligible `main` promotion result is the sole Release SHA lock and release
authorization; one tag-triggered workflow builds that exact source and publishes it
directly through an idempotent, feed-last protocol.

## Guardrails

- Task-packet authoring is approved. Do not change contributor documentation,
  workflows, release scripts, GitHub rulesets/Environments, OSS objects, or public
  feeds without a later slice-specific Impact Handshake and explicit start.
- `develop` is the mutable integration line. `main` receives work only through a
  same-repository `develop -> main` GitHub promotion PR; do not locally merge and
  directly push the result to `main`.
- Native CI is promotion evidence. It runs while a `develop -> main` PR exists, not
  for each unaccompanied push to `develop` or ordinary push to `main`.
- A `vX.Y.Z` tag may target any release-capable completed promotion result in
  `main` history, not only current `main` head. It is the sole release authorization
  and is immutable.
- "Completed promotion result" is not ordinary ancestry: the target is the merge
  outcome recorded for a same-repository `develop -> main` PR, appears in
  `origin/main` first-parent history, contains the supported tag-triggered release
  protocol, and declares the matching project version.
- GitHub resolves a tag-push workflow from the tagged ref. A historical commit
  without the supported workflow may create no remote run, so local secretless
  preflight is mandatory and is the rejection boundary for pre-protocol targets.
- There is no Candidate business state, private candidate prefix, Candidate
  Environment, manual manifest-digest handoff, separate Publish dispatch, or second
  human approval. The tag is the human release decision.
- Preserve create-only immutable version artifacts, remote byte verification,
  single-writer publication, an authoritative visibility commit point updated last,
  rollback history, public hash/Range verification, and unsigned-release
  disclosure.
- A product defect after tagging consumes that version and returns through
  `develop -> main` under a new version. A transient infrastructure failure may
  safely rerun the unchanged tag.
- Release secrets are available only to the tag-bound `native-release` Environment;
  PR jobs receive none.
- Directly uploaded version artifacts may be reachable by guessed URL before the
  feed changes. This is an accepted tradeoff because they are intended public
  release files and contain no user/private document data.
- Preserve unrelated changes in the current dirty worktree.

## Approved Direction

- Document and enforce the `develop -> main` promotion path.
- Trigger Native CI for that promotion PR only. Expose one stable aggregate
  required check and reject a PR whose base is not `main` or whose head is not the
  same repository's `develop`.
- Require PR/status checks for `main`; prevent direct pushes. Protect `v*` tags from
  movement and deletion.
- Let `push.tags: [v*]` start the only native release workflow.
- Run a secretless preflight before entering the release Environment. Validate tag,
  version, Release SHA, completed promotion PR, `main` first-parent membership, and
  release-protocol compatibility.
- Do not reuse the Promotion PR check SHA as Release SHA evidence. GitHub tests a
  temporary PR merge ref; rerun release-grade verification on the real Tag SHA.
- In one tag-bound release execution, run check/tests, native OCR materialization,
  frozen packaging, packaged smoke, Velopack/manifest generation, direct immutable
  upload, remote verification, public visibility update, and final verification.
- Keep the manifest as machine-verifiable release evidence, not as a second
  approval identity. It binds version, tag, commit, promotion PR, toolchain/config,
  artifacts, and workflow/run evidence.
- Upload versioned immutable artifacts directly to their final public keys with
  overwrite forbidden. Existing objects are accepted only when size and SHA-256
  match.
- Name one public feed object as the authoritative visibility commit point.
  Reconcile other feed projections and the stable Setup alias around it, then
  change the authority last. Do not claim unsupported multi-object atomicity.
- Use global publication serialization and reject non-monotonic normal releases.
  Rollback remains a separate explicit operation.
- Keep the workflow simple but observable: named steps, bounded timeouts, progress,
  and automatic redacted diagnostics. Do not introduce durable stage state unless
  measured retry cost justifies it.

The approved topology is:

```text
daily work
  -> develop
  -> GitHub promotion PR (develop -> main)
  -> Native CI on that PR
  -> completed, release-eligible main promotion result
  -> create immutable vX.Y.Z tag on a current or historical eligible result
  -> secretless tag/ref/version preflight
  -> exact-Tag-SHA check + test + build + packaged smoke
  -> direct create-only upload of immutable public artifacts
  -> remote verification
  -> authoritative feed/visibility update last
  -> public verification and release evidence
```

## Verification

- `CONTRIBUTING.md` and deployment runbooks describe one non-contradictory route
  from `develop` through promotion PR to tag-triggered public release.
- An unaccompanied `develop` push does not run Native CI. Opening or updating the
  promotion PR does.
- A direct push or feature-branch PR cannot change `main`; the stable Native CI gate
  is required before promotion.
- A tag may select an older completed promotion result after `main` advances, but a
  side-branch ancestor, direct-push commit, partial rebase sequence, version
  mismatch, or pre-protocol commit fails the mandatory local secretless preflight.
  Supported-protocol targets repeat preflight remotely.
- Tag creation is the only release dispatch and locks one Release SHA. No manual
  Candidate or Publish workflow remains.
- Release tests, build metadata, manifest, uploaded artifacts, and publisher code
  all resolve to the exact tag SHA.
- There is no `candidates/<version>/<digest>/` upload or manifest digest copied
  between workflows.
- A failure before the visibility commit point leaves the previous release
  authoritative. Rerunning the same tag either verifies identical existing objects
  and continues or fails on conflict.
- A slow build/upload emits progress or ends through workflow-owned timeout with
  retained diagnostics; operators do not infer hangs from silence.
- Promotion CI, tag-to-public Release, transfer/verification, same-tag retry, final
  visibility commit, and operator hands-on time satisfy the budgets below.
- A safe rehearsal covers current and historical promotion results, tag preflight
  rejection, build failure, interrupted upload, direct-public orphan convergence,
  visibility update, post-publish verification, and rollback.

## Prior P1 Disposition

The five P1 recommendations from the v1.2.0 postmortem remain traceable after
Candidate removal:

1. **Locked native OCR cache — retained.** Cache Paddle/OpenCV downloads and native
   OCR build outputs using compiler/toolchain, dependency lock, source, and build
   configuration digests. Restore is followed by identity/self-test verification;
   cache is never release authority.
2. **OSS transfer — retained.** Large direct-public objects use progress-visible
   multipart/resumable upload with byte/rate/heartbeat reporting. Remote equality
   remains objectively verified; a closer controlled runner is adopted only when
   measurement justifies its security/maintenance cost.
3. **Candidate reuse — superseded, not dropped.** There is no Candidate to reuse.
   Promotion PR evidence cannot replace exact-Tag-SHA verification because GitHub
   tests a temporary merge ref. Same-tag reruns instead reuse only identity-bound
   caches and byte-identical final immutable objects.
4. **UI/runtime lifecycle coverage — retained.** Release Readiness includes
   black-box worker/thread quiescence after window close and cross-order exercises
   for MainWindow, Settings, Knowledge Workspace, and SQLite/runtime disposal.
5. **Operator surface — simplified.** Replace
   `prepare/candidate/status/publish` with one preflight/tag procedure and one
   release-status/evidence surface. Tag remains the only mutating release command;
   commit, tag, promotion PR, workflow run, outcome, and rollback evidence are
   recorded automatically.

## Time and Cost Acceptance

The initial budgets use v1.2.0 evidence rather than an abstract "faster" goal.
Recent successful Native CI runs took about 13–22 minutes. The accepted v1.2.0
Candidate took 110 minutes: approximately 27 minutes of tests, 32 minutes of build,
and 47 minutes of upload/remote verification.

| Metric | Initial acceptance budget |
| --- | --- |
| Promotion PR Native CI controlled execution | median `<= 18 min` and no qualifying run `> 25 min` across at least five successful runs |
| Tag-triggered Release controlled critical path | `<= 90 min` from job start to authoritative visibility update for a cold, current-sized release |
| Direct artifact upload plus remote verification | `<= 30 min` for the current release-sized artifact set |
| Same-tag retry after an interrupted upload | `<= 70 min`; identical final objects and verified caches may be reused |
| Visibility commit plus final public verification | `<= 5 min` after all immutable objects are verified |
| Long-step observability | transfer heartbeat/progress at least every `60 s`; no other active release step is silent for more than `2 min` |
| Operator hands-on time | `<= 5 min`: run preflight, create/push tag, then inspect final status; no copied digest or second dispatch |

Measure two clocks separately:

- **controlled execution**: runner job start to completion; this is the enforceable
  engineering budget;
- **calendar time**: GitHub event to completion, including runner/environment queue;
  record it as operator experience, but do not misclassify external queue delay as
  application regression.

Acceptance needs at least five successful Promotion CI samples plus one cold safe
Release rehearsal and one interrupted-upload same-tag retry. After rollout, retain
a rolling ten-run median/tail view. A budget miss keeps the relevant slice open
unless evidence shows the baseline assumptions changed and the user explicitly
accepts a re-baseline; timeout must not be set equal to the performance budget.

## Current Truth

- The implementation is committed on `codex/cicd-simplification`, published to
  GitHub, and fast-forwarded into `origin/develop`. The local `develop` worktree
  has merge-pulled that state while preserving product commit `931450f`.
- Repository code now defines `develop -> main` promotion CI with stable
  `Native CI Gate`, exact-tag/promotion preflight, and a read-only audit for the
  required main/tag rulesets plus `native-release` Environment policy.
- Candidate and Publish workflow/script surfaces have been replaced locally by
  one `push.tags: [v*]` Native Release workflow. The manifest schema binds tag,
  commit, promotion PR, workflow run/attempt, toolchain, lock, and artifacts.
- The direct publisher uses final public keys, create-only immutable objects,
  resumable multipart upload, public hash/Range verification, rollback snapshots,
  Setup reconciliation, monotonic-version enforcement, and
  `releases.win-x64-stable.json` as the last visibility update.
- Locked OCR input/output caches are keyed from source/config/toolchain evidence;
  restored output must pass catalog/hash validation and the native OCR self-test.
- Release Readiness has targeted coverage for both Settings/Knowledge Workspace
  open orders, UI-owned thread-pool quiescence, application-owned Knowledge worker
  shutdown, and post-close SQLite integrity access.
- Repository verification now passes:
  - final target set: `20 passed`;
  - full non-UI suite: `646 passed, 4 skipped`;
  - full MainWindow suite: `62 passed`;
  - `pdm run check`, `git diff --check`, workflow YAML parse, and actionlint over
    all changed native workflows pass.
- A first full run had one unrelated encrypted-PDF import timeout while Docling
  loaded weights under concurrent suite load; the isolated case passed in `22 s`
  and the final full run passed. No test timeout was changed.
- GitHub production controls are still the old state: current active rulesets do
  not require promotion/status checks; `native-release` is not configured; old
  Environments remain. The workflow now exists on `develop`; its first
  `develop -> main` promotion run will establish the stable check context needed
  before those controls can be activated.
- The accepted v1.2.0 baseline remains about 110 minutes, including about 47
  minutes for upload/remote verification. No new-run timing sample exists yet, so
  none of the execution budgets is accepted.
- `release-timings` now filters qualifying Promotion samples by the new
  `Promotion Contract` and `Native CI Gate` jobs. The current repository has zero
  qualifying samples and no Native Release workflow on the default branch, which
  correctly leaves both timing acceptances open.
- Historical evidence and the simplified final simulation live in
  `evidence/v1.2.0-postmortem.md` and `evidence/final-design-review.md`.

## Open Decisions

- Whether measured public hash verification time justifies replacing full
  re-download with another objectively equivalent integrity proof. The first
  implementation deliberately retains full public SHA-256 verification.
- Whether the first cold/same-tag rehearsal meets the adopted budgets; cache,
  part-size, thread-count, checkpoint, or runner locality changes require that
  evidence rather than prior assumption.
- The exact separately authorized rollback automation remains outside the normal
  Tag release workflow; rehearsal must not mutate the production feed.

## Next Step

Use the v1.3.0 `develop -> main` promotion PR as the first qualifying Native CI
run. Stop after CI evidence is confirmed: do not merge the promotion PR, create
the tag, enter the release Environment, or publish artifacts until the user
resumes. Afterward apply/audit GitHub controls in dependency order; all three
slices remain open until a safe cold release and interrupted same-tag retry
produce timing evidence.
