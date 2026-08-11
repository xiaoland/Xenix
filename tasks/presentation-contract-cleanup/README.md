# Presentation Contract Cleanup

**Status:** Completed and verified on 2026-08-11.
**Opened:** 2026-08-11.

## Objective

Remove presentation and formatting code that lost every production consumer
after Xenix converged Agent Tool results on typed payloads. Preserve one
authority per result and stop tests from manufacturing unsupported Markdown or
re-validating Pydantic's own basic parsing behavior.

This is a deletion/refinement slice. It adds no replacement JSON renderer,
schema snapshot, compatibility adapter, or new output contract.

## Impact Handshake

### Address and Object

- `src/xenix/services/analysis_profile.py`: orphan Dataset-profile Markdown
  renderer and its private escaping helper.
- `tests/test_analysis_profile.py`: the renderer-only assertions/import and one
  redundant direct Pydantic echo assertion.
- `src/xenix/services/agent/tools.py`: the full orphan ML Markdown summary
  closure and receipt parameters that only selected those old summaries.
- `src/xenix/services/artifact_service.py`: unused Artifact Markdown-link
  builder; the authoritative Artifact URI builder remains.
- `src/xenix/datetime_utils.py`: presentation-only module whose legacy UI
  consumers were deleted.
- `src/xenix/services/tabular.py`: unused legacy column-display formatter; the
  canonical tabular schema and active value formatter remain.
- `src/xenix/services/agent/xenix_table_text.py`: unconsumed compatibility
  re-export after the renderer authority moved to `services/llm`.
- `src/xenix/ui/chatbot.py`: unused `render_snapshot` adapter that reconstructs
  presentation instead of consuming Harness-owned `ChatbotEvent` values.
- `src/xenix/ui/widgets/dataset_summary.py` and
  `src/xenix/ui/widgets/json_schema_form.py`: presentation widgets whose legacy
  owning views were removed.
- `src/xenix/translations/*.ts`: remove only translation contexts owned solely
  by the deleted widgets through the normal extraction workflow.
- `pyproject.toml`: remove the deleted datetime module from the explicit mypy
  file manifest.

### State Diff

- **From:** typed service/Tool authorities coexist with dead Markdown/text
  representations, unused formatting helpers, and tests that are their sole
  consumer.
- **To:** only representations with a real product boundary remain. Typed
  results, Provider projection, UI presentation, Artifact rendering, and
  canonical table text keep their current behavior.

### Blast Radius

Static source and test cleanup only. No DTO, Provider schema, Tool payload,
storage row, UI event, Artifact URI, graph output, or business operation changes
shape or behavior.

### Invariants

- `analysis.profile` continues to return the same typed, bounded Tool value.
- ML Tool receipts, completed results, metadata, and task-query payloads remain
  byte-for-byte equivalent at their public value boundary.
- `artifact://` identity remains owned by `build_artifact_uri`.
- the active Xenix Table Text renderer, Chatbot Markdown renderer, canonical
  message-block Markdown fallback, graph SVG renderers, and ephemeral UI Tool
  presentation registry remain intact.
- tests retain business computation, privacy, lineage, persistence, digest,
  migration, tamper, and boundary evidence. No new JSON shape test replaces
  deleted presentation assertions.
- unrelated dirty work under `tasks/improve-260809` is preserved unchanged.
- Xenix is an application (`distribution = false`) and exposes no supported
  external Python import API for the unused Agent compatibility re-export.

## Verification

- source-reference audit proves every deleted helper had no production
  consumer, or belonged exclusively to the deleted closure;
- focused profile and Agent Tool projection tests pass;
- repository type/lint/Skill checks pass;
- full ordinary test manifest and application smoke pass;
- repository search finds no stale imports, calls, or claims for the deleted
  presentation paths, widgets, or compatibility shim;
- `git diff --check` passes and unrelated working-tree changes remain present.

## Current Truth

- `analysis.profile` production returns
  `ToolSuccess(value=result.model_dump(mode="json"))`; its Markdown renderer is
  referenced only by one test.
- commit `8354fed` removed Tool-result Markdown `content_blocks` but left the ML
  receipt/metadata/task-query formatting closure and Artifact Markdown-link
  builder behind.
- the last legacy UI consumers of `datetime_utils.py` were removed earlier; the
  module now has no external references.
- `tabular.format_column` lost its consumers when column resolution moved to the
  canonical tabular schema.
- `ThreadDetailView.render_snapshot` lost its callers when Harness-owned
  `render_events` became the sole Chatbot projection input.
- the two shared widgets and Agent XTT compatibility shim have no source, test,
  script, or benchmark consumer; the active LLM-owned XTT renderer remains
  directly consumed by Agent Tools.
- active Markdown/SVG/table renderers have confirmed production call sites and
  are outside this cleanup.

## Next Step

The cleanup is ready for human review. Do not commit without a separate
explicit instruction.

## Execution Result

All four passes in [the implementation plan](implementation-plan.md) are
complete.

- Deleted the profile Markdown renderer and renderer-only test assertions; no
  JSON-shape replacement test was added.
- Deleted the complete orphan ML Tool Markdown-summary closure without changing
  public Tool value dictionaries.
- Deleted the unused Artifact Markdown-link builder, datetime presentation
  module, tabular column formatter, Agent XTT compatibility re-export,
  `ThreadDetailView.render_snapshot`, and two legacy shared widgets.
- Removed the deleted datetime module from the mypy manifest and synchronized
  translation catalogs through the normal extraction/compile workflow.
- Preserved the active LLM-owned XTT renderer, Chatbot Markdown renderer,
  message-block Markdown fallback, Tool presentation registry, and graph SVG
  renderers after confirming their production consumers.

Exact verification:

- profile tests: `4 passed`;
- six Agent ML projection modules: `6 passed`;
- Agent Harness first slice: `2 passed`;
- `pdm run check`: passed, including Ruff, mypy, Skill/catalog, lock, and
  compile checks;
- `pdm run test -q`: `136 passed` (only pre-existing Joblib/NumPy deprecation
  warnings);
- `pdm run smoke`: passed with exit code `0`;
- translation compile: `381` translations generated per locale;
- deleted-symbol/reference audit and `git diff --check`: passed.

The unrelated, pre-existing `tasks/improve-260809` / O4 working-tree changes
remain untouched and are not part of this packet.
