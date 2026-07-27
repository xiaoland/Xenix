# v1.3.0 Release Packet

## Status

Release execution is active. Promotion PR #111 passed Native CI and was merged,
but release preflight found a Python toolchain identity drift that must be promoted
before the immutable `v1.3.0` tag is created.

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
- GitHub branch/tag rules and the `native-release` Environment still require the
  separately verified rollout described by the CI/CD task packet.

## Next Step

Promote the exact Python toolchain correction through `develop -> main`, then tag
that completed promotion result, run local release-identity preflight, push the
tag, and monitor Native Release through canonical publication.
