# Native CI/CD Simplification Implementation Plan

Each slice is independently approvable. Task-packet refinement does not authorize
workflow, script, documentation, GitHub configuration, OSS, or publication changes.

## Slice 01 — Promotion and Ref Authority

Outcome: make `develop -> main` the only promotion boundary and make an eligible
`vX.Y.Z` tag the only release boundary.

Implementation status: repository workflow, contributor contract, exact identity
preflight, tests, and read-only control audit are implemented locally. GitHub
ruleset/Environment application and live acceptance remain pending.

Planned changes:

- Update `CONTRIBUTING.md` and deployment owners with branch roles, the supported
  promotion route, prohibited local merge/direct push, historical promotion-result
  selection, immutable tag behavior, and failure/version semantics.
- Change Native CI to run for PRs targeting `main`, with a contract check requiring
  the same repository's `develop` as head. Do not trigger it for an unaccompanied
  `develop` push or ordinary `main` push.
- Expose one stable aggregate gate over the selected Python/check/test jobs; require
  that gate in the `main` ruleset.
- Require PR changes to `main`, block direct fast-forward push, and protect `v*`
  tags from update/deletion.
- Add a repository-owned, secretless release preflight contract for:
  - exact SemVer/project-version equality;
  - immutable Tag SHA;
  - completed same-repository `develop -> main` PR merge outcome;
  - `origin/main` first-parent membership;
  - supported release-protocol/workflow version.
- Provide a supported pre-push/operator check so an invalid immutable tag does not
  consume a version unnecessarily. The tag-triggered workflow repeats the checks;
  local success is not authority.

Acceptance:

- `develop` push alone creates no Native CI run; opening/updating its promotion PR
  does.
- A feature-branch PR or direct push cannot change `main`.
- The promotion PR cannot merge without the stable gate.
- An older completed promotion result remains eligible after `main` advances.
- A side-branch ancestor, direct-push commit, partial rebase sequence, mismatched
  version, or pre-protocol commit is rejected without release secrets.
- Merging to `main` does not release; creating the eligible immutable tag does.
- Across at least five successful qualifying runs, Promotion CI controlled
  execution has median `<= 18 min` and no run exceeds `25 min`; queue time is
  recorded separately.

## Slice 02 — Single Tag-triggered Direct Release

Outcome: replace Candidate/Publish handoff with one idempotent workflow that builds
the exact tag and publishes it directly.

Implementation status: single Tag workflow, manifest v3, direct OSS publisher,
deterministic feed ordering, tests, and deployment runbook are implemented
locally. Production Environment setup and safe release/retry rehearsal remain
pending.

Planned changes:

- Replace `native-candidate.yml` and `native-publish.yml` with one
  tag-triggered `Native Release` workflow:
  1. secretless preflight;
  2. exact-Tag-SHA identity and repository checks;
  3. native OCR materialization;
  4. frozen package;
  5. packaged smoke;
  6. Velopack and release manifest;
  7. direct immutable public upload;
  8. remote verification;
  9. authoritative visibility update;
  10. final public verification/evidence.
- Keep black-box worker/thread quiescence after closing windows and cross-order
  exercises for MainWindow, Settings, Knowledge Workspace, and SQLite/runtime
  disposal in Promotion CI, where semantic testing is release-eligibility
  evidence.
- Consolidate release configuration/secrets under one `native-release` Environment
  restricted to `v*`. Tag creation is the release approval; no second required
  reviewer or manual Publish dispatch is introduced.
- Remove Candidate-specific vocabulary, environment, private
  `candidates/<version>/<digest>/` upload, manual manifest digest input, and
  candidate-to-publisher handoff.
- Evolve the manifest into release evidence binding version, tag, commit,
  promotion PR, workflow/run attempt, toolchain/configuration identity, smoke
  result, and artifact sizes/hashes.
- Make the direct publisher:
  - upload immutable versioned objects with overwrite forbidden;
  - accept an existing object only when size/hash are identical;
  - verify public object hashes and Range behavior;
  - serialize normal publication globally;
  - reject non-monotonic normal releases;
  - snapshot rollback state;
  - reconcile mutable projections deterministically;
  - update the chosen authoritative feed/visibility object last;
  - verify the final public state.
- Keep rollback as an explicit, separately authorized operation rather than
  publishing an older release tag over a newer feed.

Acceptance:

- Pushing one eligible `vX.Y.Z` tag is the only operator release action.
- Workflow code, build, manifest, artifacts, and publisher all come from the exact
  Tag SHA; semantic tests run once at Promotion.
- No Candidate workflow/state/prefix and no separate Publish dispatch remain.
- A build/smoke failure changes no public state.
- Window-close/runtime lifecycle defects are exercised before public upload rather
  than rediscovered through production-release timing.
- An interrupted immutable upload may leave an unreferenced intended-public object;
  the feed stays unchanged and a same-tag rerun converges or detects conflict.
- A product fix requires a new version; infrastructure failure reruns the unchanged
  tag.
- Failure around mutable projections has an explicit state and deterministic
  convergence; documentation does not claim multi-object atomicity.
- A cold current-sized safe release reaches the authoritative visibility update
  within `90 min` of controlled job start. Direct upload plus remote verification
  is `<= 30 min`, and visibility commit plus final verification is `<= 5 min`.

## Slice 03 — Operability, Performance, and Rehearsal

Outcome: make the single workflow understandable and reliable without rebuilding a
durable release state machine.

Implementation status: named workflow steps, timeouts, non-secret evidence,
publisher timing evidence, a rolling controlled/calendar/queue report, multipart
progress/heartbeat, OCR caches with native verification, and cross-window
lifecycle coverage are implemented locally. Full local validation passes.
Performance sampling, safe-prefix failure rehearsal, and budget acceptance remain
pending.

Planned changes:

- Keep one release execution but expose named step boundaries, elapsed time,
  heartbeats, and bounded workflow-owned timeouts.
- Record both controlled runner execution and event-to-completion calendar time;
  publish per-stage duration and bytes so performance regressions are attributable.
- Preserve automatic `if: always()` redacted diagnostics and non-secret evidence
  for native OCR, frozen runtime, packaged smoke, upload, and public
  verification failures.
- Use OSS multipart/resumable upload for large direct-public objects, with byte,
  rate, part, retry/resume, and heartbeat reporting. Evaluate a closer runner only
  from measured transfer evidence.
- Cache locked Paddle/OpenCV downloads and native OCR build outputs using
  compiler/toolchain, dependency-lock, source, and build-configuration digests.
  Verify restored runtime identity and self-test before use. Do not create a
  Candidate-like authority through caching.
- Provide one release preflight/tag procedure and one status/evidence surface that
  records the selected promotion PR, commit, immutable tag, workflow run/attempt,
  outcome, public verification, and rollback key. It does not recreate separate
  prepare/candidate/publish state transitions.
- Rehearse against a safe prefix/channel:
  - normal current promotion result;
  - historical eligible promotion result;
  - invalid tag rejection;
  - exact-SHA product failure;
  - runner/network retry;
  - interrupted direct upload;
  - mutable projection interruption and convergence;
  - simultaneous tags and non-monotonic rejection;
  - post-publication verification failure and rollback.
- Update workflow comments, deployment runbooks, operator checklist, expected stage
  durations, and concise release evidence together with verified behavior.

Acceptance:

- An operator can identify progress/failure without reading one monolithic log or
  guessing whether a run is hung.
- A same-tag rerun can reuse a verified native OCR cache and byte-identical direct
  public objects without treating either as release authority.
- An interrupted-upload same-tag rehearsal completes within `70 min`; transfer
  emits at least one progress/heartbeat record per `60 s`, and other active release
  steps are never silent for more than `2 min`.
- Operator hands-on release time is `<= 5 min` and contains no copied digest or
  second workflow dispatch.
- The release path needs no local branch surgery, tag movement, copied digest,
  second dispatch, or private Candidate cleanup.
- Representative failures converge safely under the same tag or explicitly require
  a new version.
- Release and rollback invariants are demonstrated without modifying the production
  feed during rehearsal.
