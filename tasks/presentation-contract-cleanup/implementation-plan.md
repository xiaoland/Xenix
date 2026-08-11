# Implementation Plan

**Status:** Completed and verified on 2026-08-11.

## Pass 1 — Profile and standalone formatting orphans

**Result:** Completed; focused profile tests, Ruff, type checking, reference
search, and diff checks passed.

Ownership:

- `src/xenix/services/analysis_profile.py`
- `tests/test_analysis_profile.py`
- `src/xenix/services/artifact_service.py`
- `src/xenix/datetime_utils.py`
- `src/xenix/services/tabular.py`
- `pyproject.toml`

Actions:

1. Delete `render_dataset_profile_markdown` and its local `_markdown_cell`.
2. Delete only the test import/assertions that consume that renderer.
3. Delete the direct `AnalysisProfileInput.model_validate` echo assertion; the
   same input already crosses the real registry execution boundary.
4. Delete `build_artifact_markdown_link`; keep `build_artifact_uri` unchanged.
5. Delete the unreferenced datetime presentation module.
6. Delete `tabular.format_column`; keep active `format_value` and canonical
   schema resolution unchanged.
7. Remove the deleted datetime module from mypy's explicit file manifest.

Focused proof:

- `pdm run pytest --direct tests/test_analysis_profile.py -q`
- repository search for the deleted names and module.

## Pass 2 — Agent Tool Markdown closure

**Result:** Completed; six Agent ML projection modules passed and the deleted
closure has no remaining reference.

Ownership:

- `src/xenix/services/agent/tools.py`

Actions:

1. Delete the orphan receipt, training, task-query, and model-metadata Markdown
   methods.
2. Delete their exclusively dependent metric-summary formatting methods.
3. Remove the now-unused `tool_name` parameters from `_training_task_receipt`
   and `_single_task_receipt` plus their three call sites.
4. Do not change the payload dictionaries returned by any Tool.

Focused proof:

- ML/Agent Tool projection tests that execute metadata, train, query, and apply;
- static search proving the deleted closure has no remaining reference.

## Pass 3 — Legacy presentation components

**Result:** Completed; translation extraction and compilation succeeded with
the obsolete widget contexts removed.

Ownership:

- `src/xenix/services/agent/xenix_table_text.py`
- `src/xenix/ui/chatbot.py`
- `src/xenix/ui/widgets/dataset_summary.py`
- `src/xenix/ui/widgets/json_schema_form.py`
- `src/xenix/translations/xenix_en_US.ts`
- `src/xenix/translations/xenix_zh_CN.ts`

Actions:

1. Delete the unused Agent-side XTT compatibility re-export; keep the
   LLM-owned renderer and its direct production import unchanged.
2. Delete `ThreadDetailView.render_snapshot`; preserve `render_events` as the
   only UI input for Harness-owned `ChatbotEvent` projection.
3. Delete the two unconsumed legacy shared-widget modules.
4. Run the normal translation extraction so only their obsolete contexts
   disappear, then compile translations.

## Pass 4 — Integration and negative-space review

**Result:** Completed; `pdm run check`, the 136-test ordinary manifest,
application smoke, active-renderer audit, and final diff checks passed.

1. Re-run the presentation-consumer audit and explicitly confirm that active
   table text, UI Markdown, canonical message Markdown, Tool presentation, and
   graph SVG paths still have production consumers.
2. Run `pdm run check`.
3. Run `pdm run test -q`.
4. Run `pdm run smoke`.
5. Run `git diff --check`, inspect the final diff, and verify that unrelated
   pre-existing task-packet changes were neither staged nor edited.

## Stop Conditions

Stop and return to design if a supposedly orphaned function has a dynamic,
external, plugin, migration, persisted-schema, or public compatibility
consumer; if deletion changes a Tool value; or if passing verification would
require a replacement renderer or snapshot contract.

## Acceptance

- every scoped orphan and redundant assertion is gone;
- no replacement JSON/Markdown contract was introduced;
- active presentation boundaries remain intact;
- focused, full, check, smoke, and diff verification pass;
- the packet records the exact final result and any intentionally excluded
  compatibility surface.
