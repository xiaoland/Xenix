# Promote Native Agent-First Mainline

## Objective

Make the native, AI Agent-driven product line the repository's sole default mainline while preserving earlier product-line tips as immutable archives.

## Guardrails

- Do not rewrite commit history.
- Do not stage or commit unrelated working-tree changes.
- Keep the current website as part of the native product mainline.
- Preserve the exact remote tips of `web`, `native`, and `develop` before removing active branch names.
- Do not invent an archive for the absent historical `master` ref.
- Do not commit or publish task-local control state without explicit approval.

## Verification

- Remote `main` resolves to the approved `native-ai-first` tip.
- GitHub reports `main` as the default branch.
- Website workflows trigger on `main` rather than `native-ai-first`.
- Archive branches and annotated tags resolve to the recorded legacy tips.
- Active protection covers `main` and the archive namespace against deletion and force-push.
- Old active remote names are removed only after archive and default-branch verification.
- Local worktrees remain intact and have intentional upstream configuration.

## Current Truth

- Promoted `main` tip: `db241bebc60c9676131b218fdd8c5c7b63a49f42`.
- Candidate commits through `a6521f89ad47ba2d9b1117315a84907eb990c681` were pushed before promotion.
- Legacy tips: `web` = `42ce1d3c8cb823999191e3cf5fd245ac02c375cb`; `native` = `d1e04c91041f49890fa065d24fb393fde9abe6a8`; `develop` = `649951a8f537c3a514ea2a6b59c833fc65df5587`.
- `web`, `native`, and `develop` are all ancestors of the candidate tip.
- GitHub default branch is `main`; no remote `master` exists.
- Website workflows trigger on `main`.
- Archive branches and annotated tags preserve all three recorded legacy tips.
- The active ruleset prevents deletion and non-fast-forward updates of `main` and `archive/*`.
- Old remote names `web`, `native`, `develop`, and `native-ai-first` have been removed.
- Unrelated task-local changes are present and must remain untouched.

## Next Step

None. Migration is verified complete; retain this task-local packet under the repository retention policy.
