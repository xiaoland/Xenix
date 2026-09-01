# Maintainability Optimization — Control Surface

## Objective

Reduce the codebase's structural debt — delete dead code, simplify oversized
units, correct stale/incorrect docs and comments — and add the missing durable
guides (local `AGENTS.md`, `docs/30-unit-tdd/*`, code comments) so a future
contributor can navigate the seams without archaeology. Do not change product
behavior except where a small, verifiable correction is clearly warranted.

## Guardrails

- Default is behavior-equivalent. A small behavior fix is allowed only when it
  corrects an obvious defect or stale contract, and it must be recorded in the
  slice and covered by an existing or new test.
- Never rewrite or renumber an existing migration edge; migrations are
  historically frozen. See `docs/40-deployment/local-state-evolution.md`.
- `ml/` legacy model scripts are untouched.
- `tasks/` stays volatile; durable truth lands in `docs/`.
- UI text changes stay translatable (`i18n-extract` / `i18n-compile`).
- Each slice lands verified: `pdm run check` plus `pdm run test` (or the smallest
  focused selection that proves the affected contract). Commit only on explicit
  user command.

## Verification

- `pdm run check` green after every slice (Ruff F catches unused imports/vars).
- `pdm run test` (197 passed baseline) stays green; add/trim tests only per the
  Testing Intent in `CONTRIBUTING.md`.
- For deletions: the removed symbol has zero static references in `src/` and
  `tests/` (grep-verified), or is provably unreachable through the dynamic
  `load_module` seam.

## Current Truth

- Slice 0 (audit) recorded in `preflight.md`.
- Slice 1 (dead-code deletion + `services/AGENTS.md` and `services/llm/AGENTS.md`)
  landed and committed.
- Slice 2 (`conversation.py` message-row / provider-message builder extraction)
  landed and committed; `pdm run test` 197 passed.
- Slice 3 (UI/init hot spots) is delegated to another session and out of scope here.
- Slice 4 (correct stale docs) landed.
- Slice 5 (deep splitting) landed.
- Slice 6 (ruff `extend-exclude` root-anchoring) landed; native ML subtree now linted.
- Slice 7 (bold decomposition of `AgentToolRegistry` into domain handlers) landed;
  `tools.py` 2386 → 512 lines + `_data_tools.py` / `_analysis_tools.py` /
  `_model_tools.py`.
- Slice 8 (ML waiting moved from agent layer to `MLService`) landed.

## Refined direction (KISS / minimal)

The earlier work only relocated code. The real debt is **over-implementation**:

- Agent tool layer should be a **thin adapter**: validate input → call the domain
  service → return the domain result. No projection, no compaction, no
  sanitization.
- Domain results already carry bounded summaries (`FitTaskResult.result_summary`,
  `ApplyTaskResult.summary`, `EvaluateTaskResult.evaluation`). The agent-side
  summary projection (~570 lines) and cleaning-report compaction (~190 lines)
  re-assemble what the domain already returns and must be **deleted**.
- **No sanitization** (no local-path/credential desensitization in the agent layer).
- **Async ML** (grace-period wait + `running_background` receipt + `model.task.query`
  polling) is low ROI and complicates lifecycle + harness; **consider deleting it**.
- **Truncation** is the one real concern. Replace truncation with: persist the full
  tool output and let the LLM query it later via a dedicated tool (pagination /
  row reading).
- **Delete low-value tests**: tests that assert old projection/data-model shapes,
  or re-assert static-check responsibilities (types/schema/enums), are removed.

## Next Step

Execute the refined direction:

1. Delete ML summary projection + cleaning compaction; return domain results.
2. Delete projection-shape tests and other shape/static-check tests.
3. Evaluate/delete async ML (`running_background` + `model.task.query` polling).
4. Introduce a full-result + paginated query path for over-long outputs instead of truncation.

## Open follow-up

- `_compact_table` (data.query result) still needs a decision once truncation is
  replaced by the full-result query path.
