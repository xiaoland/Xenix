# v1.3.0 Release Packet

## Status

Release preparation is active. The first stopping point is a successful Native CI
run on the `develop -> main` promotion PR. No `v1.3.0` tag exists and no release
workflow or public publication is authorized before the user resumes.

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
- Stop after the promotion CI succeeds. Do not merge the PR or create/push
  `v1.3.0` in this slice.
- After resumption, tag only the completed promotion result on `main`; run the
  mandatory local release-identity preflight before pushing the immutable tag.
- Release secrets remain confined to the tag-bound `native-release` Environment.
- Preserve the unrelated uncommitted files in the primary develop worktree.

## Verification

- `pyproject.toml` declares `1.3.0`.
- `origin/develop` contains `931450f` and the CI/CD simplification commits.
- The promotion PR has the required topology: same-repository `develop` head and
  `main` base.
- All four Python 3.14.2 semantic shards and the stable `Native CI Gate` pass on
  the final promotion head.
- The CI timing report records controlled, queue, and calendar durations; this
  first run is evidence but does not by itself satisfy the five-run acceptance
  sample.

## Current Truth

- `origin/codex/cicd-simplification` was fast-forwarded into `origin/develop`.
- Local `develop` merge-pulled that remote state while preserving product commit
  `931450f`; the resulting source declares version `1.3.0`.
- `v1.3.0` is unused remotely and no existing `develop -> main` PR is open.
- GitHub branch/tag rules and the `native-release` Environment still require the
  separately verified rollout described by the CI/CD task packet.

## Next Step

Commit and push the v1.3.0 release preparation on `develop`, open the promotion PR,
wait for the final Native CI run, record its result, and stop before merge or tag.
