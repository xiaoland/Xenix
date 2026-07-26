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
- `develop` is the mutable integration line. The documented release path promotes
  it through a same-repository `develop -> main` GitHub PR; do not locally merge
  and directly push the result to `main`. Treat the head-branch convention as a
  review/process rule, not a dedicated CI job.
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

- Document the `develop -> main` promotion path. GitHub's PR target filter
  enforces `base=main`; contributor guidance and review own the normal
  `head=develop` convention. Exact release eligibility remains independently
  enforced by tag preflight.
- Trigger Native CI for PRs targeting `main`. Run four semantic test shards in
  parallel and expose one stable aggregate job named `Native CI Gate`; do not add
  separate Promotion Contract or dynamic Test Topology jobs.
- Run all four Windows jobs on the single packaged runtime, Python `3.14.2`.
  Xenix Native is a
  frozen desktop application, not a Python package, and makes no multi-interpreter
  support promise.
- Execute `pdm run check` once, then run each manifest-owned shard on its own
  Windows runner. Keep the five clean-process cohorts, including MainWindow
  isolation. Declare the four stable shard names directly in workflow YAML;
  dynamic matrix generation does not justify a separate Linux job.
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
- A direct push cannot change `main`; every PR targeting `main` must pass the
  stable `Native CI Gate`. Review rejects a non-`develop` release promotion, and
  tag preflight independently prevents such a merge from becoming release
  authority.
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
- Before the test-topology correction, repository verification passed:
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
- `release-timings` now filters qualifying Promotion samples by the stable
  `Native CI Gate`. Runs from the superseded workflow remain historical evidence
  rather than qualifying samples.
- Promotion PR #111 produced the first new-topology run (`30193238273`).
  `Promotion Contract` passed, but all three Python jobs hit the 30-minute job
  timeout and were cancelled; `Native CI Gate` therefore failed. The run took
  about 30 minutes 27 seconds and exceeded the `25 min` single-run budget.
- The failure was cumulative test cost, not an assertion failure or one hung
  case. At audit time the suite collected 718 cases across 74 files and about
  26,000 lines of test code. Per-job installation costs about 3.3-4.0 minutes;
  pytest consumed the remainder. Python 3.12 completed the 650-pass/4-skip
  non-UI cohort in 23 minutes 46 seconds, then only 20 of 64 MainWindow cases
  before cancellation.
- The rejected pseudo-static pass has been replaced locally rather than merely
  renamed. `check_agent_contracts.py`, `check_ml_catalog.py`, and
  `check_knowledge_formats.py` are absent, and `test_suites.py` no longer shells
  out to pytest collection. Moving assertions between runners is no longer
  treated as static analysis.
- A read-only tool spike selected Ruff and Mypy. Ruff covered the repository
  with a small high-signal rule set. A full basic BasedPyright scan reported
  about `1,040` errors and a full Mypy scan about `737`; both were too noisy to
  create an honest all-source gate without a suppression baseline. The adopted
  Mypy gate is instead `strict` over explicit typed boundary modules, uses the
  Pydantic plugin, and contains no baseline or blanket application-code ignore.
- `pdm run check` now names the proof layers truthfully: generated Agent Skill
  consistency, Ruff, strict Mypy, native OCR lock and test-manifest preflights,
  then Python compilation. Translation compilation remains a test/build
  preflight and is no longer described as lint or type analysis.
- Strict Pydantic construction now owns the test topology manifest, Knowledge
  format catalog/provider closure, ML catalog declarations and registry
  invariants, native OCR lock/catalog documents, and all production Agent Tool
  inputs. Provider Tool schemas are derived portable projections of the input
  models; invocation validates into the same model before calling a typed
  handler. Exact schema/census pytest assertions are not a second authority.
- Test deletion was reviewed by proof method, not only by line count. Runtime
  persistence projection, privacy-compatible legacy reads, archive/cache
  integrity, worker lifecycle, migration, and data-loss boundaries remain
  behavioral tests because Ruff, Mypy, and Pydantic construction cannot prove
  those cross-boundary effects.
- `tests/suites.toml` now owns four semantic shards and five clean process cohorts.
  Native CI derives a `3 Python versions x 4 shards` matrix from it; exactly one
  shard per version runs the repository check, MainWindow remains isolated, and
  JUnit reporting no longer changes execution topology.
- The earlier first pass still provides a useful provisional performance
  measurement: all local Python 3.14 shards passed as `682 passed, 3 skipped`.
  Wall times were
  `59.8 s` for analysis/data, `241.8 s` for Knowledge, `44.0 s` for Agent/LLM,
  `72.0 s` for MainWindow, and `152.8 s` for platform/release.
- Corrected local acceptance now passes as `695 passed, 3 skipped` across the
  same four semantic shards and five processes:
  - analysis/data: `110 passed` in `78.26 s`;
  - Knowledge: `213 passed, 3 skipped` in `250.38 s`;
  - Agent/LLM: `165 passed` in `59.78 s`;
  - MainWindow: `63 passed` in `88.92 s`;
  - platform/release: `144 passed` in `183.45 s`.
  The composite repository check completed in about `9 s`; translation compile,
  lock consistency, workflow YAML parsing, and `git diff --check` also passed.
- One deliberately concurrent local four-shard run produced a single missing
  derivation-view assertion after the named 53 MB PPTX import while all other
  Knowledge cases passed. The same case passed alone in `21.99 s`, and the
  complete Knowledge shard then passed alone in `250.38 s`. This is recorded as
  local resource-contention evidence rather than silently discarded; remote
  Promotion jobs use separate runners, and the first new run must confirm it
  does not recur.
- Before the ROI correction, the local critical shard was Knowledge at about
  `4.2 min` and the observed GitHub install baseline suggested a controlled
  critical path of about `7.5-8.5 min`. That estimate remains useful, but the
  associated 12-job multi-version topology is rejected.
- Commit `d715689` was fast-forwarded to `origin/develop` and triggered PR #111
  run `30203158407` using the then-current 12-job topology. Before treating that
  run as acceptance, ROI review rejected the topology itself.
- Python compatibility and release runtime are now one authority: the project is
  to require exactly Python `3.14.2`, matching Native CI and Native Release.
  Supporting 3.12/3.13 has no product value because users receive a frozen runtime.
- The accepted next topology is four parallel Windows shards on Python 3.14.2
  plus one inexpensive stable `Native CI Gate`. The former `Promotion Contract`,
  dynamic `Test Topology`, 3-version axis, and multi-version baseline workflow
  are superseded.
- GitHub Environment rules are not a replacement for the removed jobs:
  Environments protect deployment approval, Secrets, and deployable refs. Native
  CI is a secretless PR proof and must not wait on a deployment authority.
- Exact Python 3.14.6 exposed a local bootstrap distinction. The installed
  PDM 2.26.6 carries `pbs-installer 2025.12.5` and lists standard managed CPython
  only through 3.14.2. An isolated probe of PDM 2.28.0 with the latest available
  `pbs-installer 2026.7.18` still listed only free-threaded
  `cpython@3.14.6t`, not standard `cpython@3.14.6`. Upgrading PDM therefore does
  not by itself make the required standard runtime PDM-downloadable.
- The ad-hoc local workaround was removed completely: the portable interpreter,
  its PDM-created `.venv`, download/archive, Winget temporary directory, and
  failed-install log are absent; the pre-existing system Python remains 3.14.0.
- The temporary recommendation to introduce the official Python Install Manager
  is superseded. The selected exact runtime is standard CPython 3.14.2, the
  highest standard patch in the existing PDM-managed catalog; PDM therefore owns
  interpreter acquisition, project selection, venv, lock, and dependencies.
- The user proposed Python 3.14.0 to keep bootstrap inside the existing PDM path,
  then accepted 3.14.2 because it has the same PDM-managed operational cost and
  includes two maintenance releases. The toolchain decision is closed.
- PDM 2.26.6 successfully installed and selected its managed standard
  `cpython@3.14.2`; it created the project `.venv`, resolved the exact 3.14.2
  lock, and installed 185 frozen packages without an external interpreter
  bootstrap.
- The four-runner workflow, exact Runtime/Release pin, timing filter, manifest
  simplification, and durable documentation are implemented locally. Validation
  passes on Python 3.14.2: `pdm run check`, lock consistency, workflow YAML
  parsing, translation compilation, 17 focused release/workflow tests, 40
  cross-shard representative tests, application smoke, and `git diff --check`.
- Superseded run `30203158407` is cancelled. Before cancellation, all four
  Python 3.14.6 shards had independently passed; the remaining multi-version
  work was discarded. This is supporting topology evidence, not a qualifying
  sample for the final 3.14.2 workflow.
- Detailed deletion rationale, protected proofs, implementation evidence, and
  timing live in `evidence/first-promotion-ci-audit.md`.
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
- Whether the four-runner, single-runtime topology meets the existing median
  `<=18 min` and tail `<=25 min` budgets after the already completed test-value
  reduction. The partial superseded run observed Python 3.14 shard completion in
  roughly 7-10 minutes, but only a new clean run is acceptance evidence.
- Whether further deletion is justified after the first value pass. Migration,
  storage/data-loss, worker termination, publication immutability, OCR
  supply-chain, and Agent/LLM authority boundaries remain explicitly protected
  from performance-driven deletion.

## Next Step

The locally accepted implementation is delivered through `develop`. Observe the
newest PR #111 Native CI run as the first qualifying four-runner, Python 3.14.2
sample and stop after its result is recorded. Do not merge the promotion PR,
create `v1.3.0`, enter the release Environment, or publish artifacts until Native
CI passes and the user resumes.
