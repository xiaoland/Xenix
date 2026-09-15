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
- Slice 9 (delete agent-side projection/compaction) landed.
- Slice 10 (delete low-value projection/shape tests) landed.
- Slice 11 (remove async ML; timeout = notification + `model.task.stop`) landed.
- Slice 12 (generic `result.page` paged tool results) landed; inline threshold 2048 chars.

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

Slice 13 — super-large file slimming (see `plan.md`). Execute A→B→C→D→E, excluding
the UI cluster. Each category lands as its own verified commit. Approved scope:

- **A.** grep-verified dead-code deletion.
- **B.** shared-helper extraction (slug/records/columns, digest, role-columns, tfidf,
  knowledge bundle/retry helpers, duplicated file-authority check).
- **C.** boundary fixes (repositories for dataset/knowledge persistence, storage→services
  import, ml_service request_payload overwrite).
- **D.** god-object extraction (thread titles, finalize dedup, wordcloud SVG, smoke checks).
- **E.** retire legacy `Tokenized*` services (product approved).

## Slice 13 progress

Landed (committed on `develop`):

- **A (dead code)** `f5b3953`: base/conversation/tooling/providers/harness/knowledge/
  analysis_graph/paddle_ocr. ~116 lines.
- **B (dedup)** `4c87cb5` (SQL file-authority + `_role_columns`), `df03d68`
  (sha256-json → `digests.sha256_json`). Deferred as higher-risk/low-value: digest flag
  unification, base `_build_pipeline` cross-class, knowledge bundle/retry module, `_slug`/`_tfidf`.
- **E (Tokenized retirement)** `4676a2f`: full deletion (product chose "break legacy
  analyzers"); registry/`__init__`/tests/SKILL.md updated. ~861 lines.
- **Compat alias/fallback** `4297387`: removed `paddle_ocr.status()` alias + `getattr` fallbacks.
- **C4 (request_payload)** `f869a19`: `MLTaskService.set_request_payload`; removed dead
  `ml_service._ml_tasks`.
- **C3 (projection relocation)** `a9b1acc`: `knowledge_projection.py` moved into `storage/`,
  removing the storage→services reverse import.
- **D1 (thread titles)** `01212e3`: extracted pure title derivation logic to
  `llm/thread_titles.py`, removing ~100 lines from `conversation.py`.
- **D2 (finalize dedup)** `5bd7a9f`: merged `_finalize_fit_task`/`_finalize_tuning_task`
  into `_finalize_training_task` shared helper, -124 lines in `ml_task_service.py`.
- **D4 (smoke checks)** `0254090`: extracted `_run_smoke_checks` to `smoke_checks.py` module.
- **C1 (dataset→repos)** `c6fae21`: routed dataset import/workbook/derivation/reference
  persistence into `DatasetRepository` (+9 methods).
- **C2 (knowledge→repo)** `76bfd5c`: added `KnowledgeRepository` dependency to
  `KnowledgeImportService`, routing all `session.get`/`session.add`/`select` calls
  through repository methods (+5 new methods).
- **Dependency topology audit**: file-level graph analysis confirmed zero cross-package
  cycles. The only cycle is intra-package `ml/contracts ↔ ml/types` (TYPE_CHECKING only,
  standard Python forward-reference pattern). The earlier "soft cycle" concern was a false
  positive from package-level aggregation — `data_tokenization_contracts` is a pure leaf
  module, so `ml_service → ml/contracts → data_tokenization_contracts` is a DAG, not a cycle.
  The `ml/` package is already correctly organized: ML-exclusive modules (evaluation,
  preparation, digests, types, registry, text_discovery, etc.) are all in `ml/`, and only
  3 genuinely shared leaf modules (`data_tokenization_contracts`, `dataset_inspection`,
  `tabular`) are imported from `services/` root.

## Slice 13 summary

All five categories landed (A–E). 14 commits, 197 passed, `pdm run check` green.
Dependency topology audit confirmed: no storage→services reverse imports, no
cross-package cycles, no remaining direct session operations outside repositories.

Remaining low-value items (deferred by user):
- **B** leftovers: `_build_pipeline` cross-class dedup, knowledge bundle/retry module,
  `_slug`/`_tfidf` consolidation.
- **D3**: `analysis_graph.py` wordcloud SVG extraction (high coupling to
  AnalysisGraphService infrastructure).
- Compat alias cleanup (`providers.py`, `conversation.py`).

## Open follow-up

- `_compact_table` (data.query result) still needs a decision once truncation is
  replaced by the full-result query path.
