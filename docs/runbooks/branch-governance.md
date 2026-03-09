# Native Branch Governance

This runbook records the repository decisions and follow-up actions for issue `#68` now that the desktop bootstrap lives on the dedicated `native` branch.

## Target Branch Model

- `web`: long-lived branch for the existing pnpm monorepo (`packages/frontend`, `packages/backend`, `packages/shared`, `packages/ml-backend`).
- `native`: long-lived branch for the PySide6 desktop codebase.
- Shared changes should be copied intentionally between branches. Only docs, ML assets, or clearly portable utilities should move across without review.

## Current Native Branch Shape

- The desktop bootstrap now lives at the branch root.
- Web-only workspace files and CI workflows are intentionally absent from this branch.
- `ml/` is kept for future native integration work, but the first native milestone is limited to bootstrap and runtime concerns.

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

- The `native` branch has been reshaped into a desktop-root repository.
- The web monorepo remains on `master` until the default branch rename is executed.
- Documentation on this branch now describes the native application directly instead of a nested subtree.

## Manual Follow-Up Outside Git

- Update the repository default branch in GitHub.
- Update branch protection rules and required reviewers.
- Update branch-based deployment or environment policies in GitHub and any external deployment systems.
- Rename any saved local automation, CI badges, or bookmarks that still reference `master`.
