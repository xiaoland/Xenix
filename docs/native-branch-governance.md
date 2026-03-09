# Native Branch Governance

This runbook records the repository changes required by issue `#68` before the desktop codebase moves to a long-lived `native` branch.

## Target Branch Model

- `web`: long-lived branch for the existing pnpm monorepo (`packages/frontend`, `packages/backend`, `packages/shared`, `packages/ml-backend`).
- `native`: long-lived branch for the PySide6 desktop codebase.
- Shared changes should be copied intentionally between branches. Only docs, ML assets, or clearly portable utilities should move across without review.

## Current Staging Approach

- The desktop bootstrap lives in `native/` on the current repository state.
- Once the `native` branch is created, promote the contents of `native/` to the branch root and remove web-only files from that branch.
- Keep this staging subtree small and bootstrap-focused. Business features should land after the branch split.

## `master -> web` Rename Checklist

1. Rename the default branch from `master` to `web` in GitHub settings.
2. Recreate branch protection and rulesets for `web`.
3. Update any required status checks to point at the new branch rules.
4. Retarget open pull requests that still reference `master`.
5. Update local clone guidance:
   - `git branch -m master web`
   - `git fetch origin`
   - `git branch -u origin/web web`
   - `git remote set-head origin -a`
6. Confirm GitHub Pages, deployment jobs, and third-party integrations are not pinned to `master`.

## Checked-In Repository Adjustments

- GitHub Actions branch filters should include `web` before the rename happens.
- README and development docs should refer to the web app explicitly when discussing the current monorepo.
- Native desktop bootstrapping should live under `native/` until the branch cut is complete.

## Manual Follow-Up Outside Git

- Update the repository default branch in GitHub.
- Update branch protection rules and required reviewers.
- Update branch-based deployment or environment policies in GitHub and Aliyun.
- Rename any saved local automation, CI badges, or bookmarks that still reference `master`.
