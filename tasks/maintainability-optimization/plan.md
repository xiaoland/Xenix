# Maintainability Optimization — Implementation Plan

Each slice lands as one verified, separately-reviewable change. No commit without
explicit instruction. Behavior-equivalent by default; any small behavior fix is
called out in the slice and covered by a test.

## Slice 0 — Audit (complete)

- `preflight.md` records the dead-code, size, and function-length findings.

## Slice 1 — Delete confirmed dead code + add missing guides (complete)

- Delete the four unused "compatibility forwarding" functions in `app.py`
  (`_register_agent_skill_tools`, `_agent_skill_activated_skill_names`,
  `_agent_skill_context_messages`, `_agent_skill_tool_scope_names`); verify zero
  references in `src/` and `tests/` first.
- Add `services/llm/AGENTS.md` and `services/AGENTS.md` (owner + seam guidance,
  not product truth).
- Verify: `pdm run check` + `pdm run test`.

## Slice 2 — Structural simplification (conversation.py first) (complete)

- Extracted `_final_message_rows` into three pure row-builders and
  `_provider_messages` into four pure provider-message builders in
  `services/llm/conversation.py`, behavior-equivalent.
- Verify: `pdm run check` + `pdm run test` (197 passed).

## Slice 3 — Largest UI/init hot spots (delegated elsewhere)

- Simplify `app.py::build_main_window` (294 lines) and the oversized widget
  `__init__`/`_build_ui` methods (`settings_dialog`, `main_window`, `chatbot`) by
  extracting construction helpers. Keep translations and signal wiring intact.
- Verify: `pdm run check` + `pdm run test` + `pdm run smoke`.

## Slice 4 — Correct stale docs and comments (complete)

- Marked the Job-layer feed-source wording as superseded in
  `pr1-job-layer-rework/plan.md` and `general-job-layer.md`.
- Audited durable `docs/` for divergence: none found; `job-feed-contract.md`
  already codifies the landed feed design, and the index/unit-design docs are
  consistent. No `docs/30-unit-tdd/` admission was warranted — the extracted
  builders are source/test truth, not a new local seam.

## Slice 5 — Deep splitting of `tools.py` and `text_analysis.py` (approved, complete)

- `text_analysis.py`: extracted 38 module-level helper functions into
  `ml/models/_text_helpers.py`; `text_analysis.py` re-imports them. Behavior
  equivalent; direct `ruff check` on the ML subtree is clean.
- `tools.py`: extracted the model-key normalization block into an
  `agent/_model_keys.py` mixin and made `AgentToolRegistry` inherit it. A full
  split of the remaining registry was not attempted (tightly-coupled god object;
  low value / high regression risk).
- Verify: `pdm run check` + `pdm run test` (197 passed) after each split.

## Slice 6 — Root-anchor ruff exclude (complete)

- `extend-exclude = ["ml", "tasks"]` → `["/ml", "/tasks"]`; native ML subtree now linted.

## Slice 7 — Decompose AgentToolRegistry into domain handlers (complete)

- `tools.py` (2386 → 512) + `_data_tools.py` / `_analysis_tools.py` / `_model_tools.py`.
- Model-key helpers exposed as pure functions in `_model_keys.py`.

## Slice 8 — Move ML waiting into MLService (complete)

- `MLService.wait_for_task` / `wait_for_training_models` own polling + follow-up tracking;
  agent layer no longer waits.

## Slice 9 — Remove agent-side projection (KISS) (complete)

- Delete ML summary projection in `_model_tools.py` (~570 lines) and cleaning
  compaction in `_data_tools.py` (~190 lines); return domain results directly.
- No sanitization/desensitization.

## Slice 10 — Delete low-value tests (complete)

- Remove projection-shape tests and any test that re-asserts data-model shapes or
  static-check responsibilities (types/schema/enums).

## Slice 11 — Evaluate/remove async ML (complete)

- Remove the grace-period wait + `running_background` receipt + `model.task.query`
  polling if ROI confirms low value; make ML tools synchronous.
- Landed as: timeout reports status/logs (notification, not cancel) + `model.task.stop`.

## Slice 12 — Full-result + paginated query (replace truncation) (complete)

- Persist over-long tool output; expose a dedicated query tool (pagination / row
  reading) instead of truncating.
- Landed as: `ToolResultPageStore` (`state/paged_results/`, char-based), invoke-boundary
  paging, generic `result.page` tool, inline threshold 2048 chars.

## Slice 13 — Super-large file slimming (audit → execute)

Scope: everything except the UI cluster. Categories from the 5-agent audit:

- **A. Dead code** (zero risk): remove grep-verified-unreferenced methods/fields across
  `ml/models/base.py`, `ml/models/text_analysis.py`, `knowledge_pipeline.py`,
  `knowledge_import_service.py`, `llm/conversation.py`, `llm/tooling.py`, `llm/providers.py`,
  `ml_task_service.py`, `ml_service.py`, `paddle_ocr_service.py`, `agent/harness_service.py`,
  `analysis_graph.py`, `data_transform.py`, `data_cleaning.py`.
- **B. De-duplicate helpers** (low risk): shared `_slug`/`_records`/`_columns`, sha256-json
  digest, `_role_columns`/`_single_role_column`/`_optional_role_column`, `_tfidf`/`_as_text_series`,
  knowledge canonical-bundle + Windows retry/link helpers, and the duplicated file-authority
  check in `data_transform.py`.
- **C. Boundary fixes** (medium risk, highest value): move dataset provenance persistence
  (`dataset_service.py`) and knowledge import persistence (`knowledge_import_service.py`) into
  repositories; fix `storage/repositories/knowledge.py` storage→services import; fix
  `ml_service.py` request_payload overwrite.
- **D. God-object extraction** (medium risk): `conversation.py` thread-title subsystem,
  `ml_task_service.py` finalize dedup, `analysis_graph.py` SVG/wordcloud block, `app.py` smoke checks.
- **E. Product-gated retirement** (approved): retire the 4 legacy `Tokenized*` services in
  `ml/models/text_analysis.py` (~900 lines) that duplicate `text_discovery.py` math, plus their
  params and registry exports.
