# Maintainability Optimization — Preflight / Audit (Slice 0)

Static audit of `src/xenix` on 2026-08-31. Tooling: Ruff (F/B/A/E rules), and an
AST scan for oversized functions and marker counts. Whole-module dead-code
detection via import graphs is unreliable here because the codebase uses relative
imports and a dynamic `load_module` seam; individual dead-code candidates are
grep-verified instead.

## 1. Dead code (high confidence)

- `src/xenix/app.py:344-383` — four "compatibility forwarding for historical
  desktop/test imports" functions are defined but never called anywhere in
  `src/` or `tests/`:
  `_register_agent_skill_tools`, `_agent_skill_activated_skill_names`,
  `_agent_skill_context_messages`, `_agent_skill_tool_scope_names`.
  Each is a thin re-export wrapper around `services.agent.composition`. Candidate
  for deletion in Slice 1.

No other confirmed-dead symbols were found. Ruff `F` (unused imports/variables)
passes clean, so the module-level import surface has no remaining unused imports.

## 2. Largest files (>38 KB, source order)

| File | KB |
|---|---|
| `services/agent/tools.py` | 106 |
| `services/ml/models/text_analysis.py` | 104 |
| `ui/chatbot.py` | 93 |
| `services/storage/migrations.py` | 80 |
| `services/knowledge_pipeline.py` | 68 |
| `services/data_cleaning.py` | 68 |
| `services/llm/conversation.py` | 67 |
| `services/ml/text_discovery.py` | 53 |
| `services/knowledge_import_service.py` | 52 |
| `services/analysis_graph.py` | 52 |
| `ui/settings_dialog.py` | 52 |
| `services/ml/models/base.py` | 51 |
| `services/ml_service.py` | 51 |
| `services/ml/models/forecasting.py` | 50 |
| `services/paddle_ocr_service.py` | 47 |
| `ui/main_window.py` | 46 |
| `ui/knowledge_workspace.py` | 42 |
| `services/ml_task_service.py` | 42 |
| `services/dataset_service.py` | 39 |
| `services/agent/harness_service.py` | 38 |

## 3. Largest functions (>60 lines, top offenders)

Migration and `_packaged_smoke` functions are excluded from "simplify" scope:
migrations are frozen; smoke drivers are self-contained test harnesses.

| Lines | Function | Note |
|---|---|---|
| 294 | `app.py::build_main_window` | top priority |
| 187 | `harness_service::_sample_until_client_frontier` | |
| 174 | `ui/chatbot.py::__init__` (largest of 3) | multiple `__init__` in one file |
| 166 | `ui/settings_dialog.py::__init__` | |
| 158 | `knowledge_task_query::list_tasks` | |
| 151 | `knowledge_import_service::_prepare_source_snapshot` | |
| 140 | `analysis_graph::_prepare_wordcloud_request` | |
| 135 | `ml_task_service::_finalize_tuning_task` | |
| 134 | `agent/composition.py::build_headless_agent_services` | |
| 131 | `ui/main_window.py::__init__` | |
| 130 | `dataset_service::_register_materialized_datasets` | |
| 129 | `ml_task_service::_finalize_fit_task` | |
| 117 | `tools.py::_task_result_summary` / `ml/models/base.py::tune` | |
| 109 | `ui/settings_dialog.py::_build_ui` | |

(~110 functions exceed 60 lines in total; the full list is reproducible with the
audit script noted below.)

## 4. Missing local guides

Local `AGENTS.md` exists for `ui/`, `ui/widgets/`, `services/storage/`,
`services/ml/`, `services/agent/`, and `tests/e2e/agent_harness/`. Notably absent:

- `services/llm/AGENTS.md` — owns `conversation.py`, `providers.py`,
  `messages.py`, `tooling.py`, `service.py`.
- `services/AGENTS.md` — owns the top-level service seam (`job_scheduler.py`,
  `job_service.py`, `ml_task_service.py`, the `knowledge_*` family).

`docs/30-unit-tdd/` has only `README.md` and one benchmark file.

## 5. Marker scan (not a dead-code signal)

`TODO/FIXME/XXX/HACK/legacy/deprecated/obsolete/compatibility/historical` markers
are almost all legitimate backward-compat descriptions (e.g. the retained
`zh_business_v1` profile, legacy `SourceAttachmentBlock` decode, historical
message payloads). No action taken; they are documentation, not debt.

## Audit script

The AST scan was run from a throwaway script (not committed). It is reproducible:
walk `src/xenix/**/*.py`, report `FunctionDef`/`AsyncFunctionDef` bodies > 60
lines and marker counts. No repository file was added for it.
