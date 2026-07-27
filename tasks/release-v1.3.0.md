# v1.3.0 Release Packet

## Status

Release execution is blocked after the first immutable-tag attempt failed before
build or publication. The source/test-topology correction can be promoted, but
the already-pushed `v1.3.0` tag cannot receive it without an explicit release
policy decision.

## Objective

Publish Xenix Native v1.3.0 from the completed promotion containing product commit
`931450fad236ea84cc191b116cfe02cd2d24bae1`, including visible application-version
information and software-update download progress, while using the simplified
promotion and tag-triggered release path as its first production rehearsal.

## Guardrails

- Preserve the identities of the existing product and CI/CD commits; join histories
  without rebasing or force-pushing.
- Promote only through the same-repository `develop -> main` PR and require its
  stable `Native CI Gate`.
- Tag only the completed promotion result on `main`; run the
  mandatory local release-identity preflight before pushing the immutable tag.
- Keep `pyproject.toml`, `release.toml`, CI, and release workflows on the same
  exact Python runtime; release identity must reject configuration drift.
- Release secrets remain confined to the tag-bound `native-release` Environment.
- Preserve the unrelated uncommitted files in the primary develop worktree.

## Verification

- `pyproject.toml` declares `1.3.0`.
- `origin/develop` contains `931450f` and the CI/CD simplification commits.
- The promotion PR has the required topology: same-repository `develop` head and
  `main` base.
- All four Python 3.14.2 semantic shards and the stable `Native CI Gate` pass on
  the final promotion head.
- Local release identity accepts the exact `v1.3.0` tag, main first-parent
  membership, and promotion PR before the tag is pushed.
- The tag-bound Native Release workflow succeeds and publishes the canonical
  v1.3.0 feed and release evidence.
- The CI timing report records controlled, queue, and calendar durations; this
  first run is evidence but does not by itself satisfy the five-run acceptance
  sample.

## Current Truth

- Promotion PR #111 merged `develop` into `main` as `6fcbb001`, after all four
  Python 3.14.2 semantic shards and `Native CI Gate` succeeded.
- The promoted source declares project/runtime Python `3.14.2`, but
  `release.toml` still recorded `3.14.6`; publishing from that state would make
  the immutable release manifest false.
- `v1.3.0` remains unused locally and remotely, and no release workflow has run.
- PR #112's first Native CI attempt exposed three release-identity behavior
  fixtures that omitted the newly required Python fields. The validator remained
  fail-closed; the fixtures now share one complete configuration writer, and the
  full 144-test `platform-release` shard passes locally.
- PR #112 then passed all four Native CI shards and merged to `main` as
  `5cba2ba8`.
- GitHub now requires PR plus `Native CI Gate` for `main`, protects `v*` tags from
  deletion and movement, and exposes release secrets only through a
  `native-release` Environment admitting `v*` tags. Superseded release
  Environments were removed.
- GitHub reports administrator bypass as enabled but does not expose that switch
  for this private repository plan. It is not a release authority: the tag-only
  workflow, immutable tag ruleset, and promotion identity remain the enforced
  authorization path.
- PR #113 run `30233380523` passed `analysis-data`, `knowledge`, and
  `platform-release`. `agent-llm-ui` received an attachment-import FAILED event
  before the Harness terminal error reached the UI, so the test could fail while
  its daemon submission thread was still crossing the following MainWindow test
  boundary; the job then reached its 30-minute limit.
- The attachment-failure test now waits for both the FAILED presentation and the
  terminal submission boundary. Native CI also prints each executing test name,
  so a future hard timeout identifies the active contract without replacing the
  existing four-shard topology.
- The first repaired local shard run then exposed three artifact-link tests that
  asserted immediately after dispatching the intentionally asynchronous link
  activation. They now drive the Qt event loop until the observable open result,
  using one bounded completion helper instead of fixed sleeps.
- PR #113 then passed all four shards and `Native CI Gate` in run `30235296953`
  and merged as `8b7dd79a`; `v1.3.0` identity preflight bound that commit to PR
  #113 and the tag was pushed.
- Native Release run `30235807406` passed identity and controls, then failed in
  the duplicated full pytest run. A low-value test asserted private OpenAI
  defaults while the valid packaged DeepSeek trial configuration was active.
  OCR, packaging, OSS mutation, and canonical-feed publication never started.
- The correction deletes that negative/default-mirroring test and comparable
  high-confidence schema/helper/default repetitions. Native Release no longer
  serially reruns Promotion pytest; exact-tag checks, OCR self-test, package and
  packaged smoke, manifest, immutable publication, and public verification remain.
- Local correction verification passes: repository checks, 18 focused retained
  boundaries, the `agent-llm-ui` shard (`154 + 62`), the `platform-release` shard
  (143), workflow YAML parsing, and diff validation.

## Next Step

Promote the test/proof-topology correction through a new `develop -> main` PR.
Then choose explicitly between preserving tag immutability and releasing a bumped
version, or authorizing a one-time delete/recreate exception for the unpublished
`v1.3.0` tag. Do not mutate the existing tag before that decision.
