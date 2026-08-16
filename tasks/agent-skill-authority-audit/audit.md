# Prose→Wall Audit

Classification key:

- **W** — already hard-walled by tool/service/tool-scope; prose is redundant.
  Proposed action: delete (direct token + cognitive-load savings).
- **G** — gated by skill activation / tool scope / fail-closed service, but
  the model still must make the correct choice. Proposed action: keep one
  positive routing line, measure with route probes.
- **B** — behavioral/economy: the model's choice affects tokens/latency, not
  correctness. Proposed action: keep minimal positive guidance, measure with
  consumption probes.
- **S** — semantic final-answer honesty: only judgeable by rubric. Proposed
  action: compress to one positive standard, defer to the Judge (per B0-GR /
  O4-E3).
- **UX** — user-facing affordance (ask/export/publish). Per D2 no wall; keep
  minimal or move to the product layer.

## Enforcement map (the walls this audit relies on)

| Wall | Location | What it rejects |
| --- | --- | --- |
| SQL statement whitelist | src/xenix/services/data_transform.py:58-81, 189-219 | ALTER/ATTACH/CALL/CHECKPOINT/COPY/CREATE/DELETE/DETACH/DROP/EXPORT/FORCE/IMPORT/INSERT/INSTALL/LOAD/MERGE/PRAGMA/RESET/SET/TRUNCATE/UPDATE/VACUUM; query must start SELECT/WITH and be single-statement |
| File-authority ban | data_transform.py:102-122, 309-316 | DuckDB file-scan functions (read_csv, read_parquet, …) and direct file paths after FROM/JOIN |
| Query row bound | tool_inputs.py:384-387; data_transform.py:411,426-427 | limit is ge=1, le=200 (default 50); result wrapped in SELECT * ... LIMIT {limit} |
| Value-safe profile | dataset_inspection.py:94-137 | analysis.profile returns column kind/name/nullability only — no sample rows/categories/identifiers |
| Derived-only writes | data_transform.py:459-487; data_cleaning.py:770-779 | All SQL runs in duckdb.connect(":memory:"); outputs are new parquet files under derived/cleaned/export dirs — source never mutated |
| Tool registry | tools.py:156-160, 269 | Unknown tool names are not registered / not callable |
| Provider schema subset | tooling.py:244, 318, 466-480 | Provider schema is projected from registered tools only; non-portable keywords rejected |
| Model key validation | tools.py:2363-2408, 2491 | Unsupported model keys rejected |
| Model param validation | types.py:269-274 + per-path validate_params / validate_param_grid | Params outside the model's param_schema rejected |
| Leakage / group-overlap fail-closed | preparation.py:76; text_analysis.py:1996 | Overlapping groups / leaked splits rejected before training |
| Index/name mutual exclusion | tool_inputs.py:322 | Mixing index and name selector forms rejected |
| Stale index rejection | data_cleaning.py:760-768 | Post-op index reuse rejected rather than guessed |
| Skill activation gate | composition.py:35-46, 292; harness_service.py:703-705 | Inactive skills expose only agent.skill.activate + knowledge.lookup; a skill's tools appear only after activation |

## xenix-data-analysis

| Ref | Rule (condensed) | Class | Evidence | Action |
| --- | --- | --- | --- | --- |
| L26, L40 | "no script execution; do not invent tools/scripts/packages/jobs" | **W** | Tool registry + provider-schema projection: an unregistered tool cannot be called | Delete the "do not rely on Python/shell…" clause; keep at most a one-line factual "tool-only runtime" note |
| L39 | "do not send full raw datasets to the model" | **W** | limit ≤ 200; profile is value-safe | Delete the prohibition; the bound is architectural |
| L39 | "start from the value-safe profile; disclose exact values only when materially needed" | **B** | Not walled — data.query can still SELECT * up to 200 rows (improve-260809 O4-A3 observed broad SELECT *) | Keep as one positive economy line; measure via consumption probe |
| L41 | "read-only SQL only; no DROP/DELETE/UPDATE/INSERT/CREATE/ALTER" | **W** | DuckDbSqlValidator keyword + statement whitelist | Delete; the validator already rejects each named keyword |
| L42, L104 | "prefer simplest analysis; do not escalate to modeling to appear sophisticated" / "avoid algorithm showroom" | **S** | Judge-only | Compress to one positive standard; defer to Judge |
| L43 | "do not infer numeric results tools did not return" | **S** | Judge (the retired free-prose grounding regex — B0-GR / O4-E3) | Already deferred to Judge; remove the negative prose |
| L44 | "never interpret correlation as causality" | **S** | Judge | Compress to one line; defer to Judge |
| L45, L55, L56 | "activate the narrower skill when the task shifts" | **G** | Activation gate; data.tokenize / model.* tools are out of scope until the right skill is active | Keep positive routing line; measure with route probe |
| L46 | "Knowledge excerpt is a source claim, not truth" | **S** | Judge | Compress; defer to Judge |
| L53 | "do not fall back to a broad preview" | **B** | Not walled (the limit bound exists but broad queries still cost) | Keep minimal economy line; measure consumption |
| L59, L88 | "ask before overwrite/delete/export/publish" | **UX** | Per D2: overwrite/delete is impossible (derived-only); export/publish is a product affordance | Drop the "destructive" half (already walled); keep at most the export/publish affordance as product guidance |

## xenix-data-modeling

| Ref | Rule (condensed) | Class | Evidence | Action |
| --- | --- | --- | --- | --- |
| L47-48 | "do not train before target/roles/leakage/sensitive fields are identified; no identifiers/post-outcome as features" | **G** | Leakage/group-overlap fail-closed; but role binding is still a model choice | Keep positive "bind roles first" line; measure via route/behavior probe |
| L49, L85 | "baseline first; tune only when needed" | **B** | Not walled | Keep minimal positive guidance; measure consumption |
| L50 | "do not claim causality from coefficients/importance" | **S** | Judge | Compress; defer to Judge |
| L51 | "do not claim automatic-decision suitability unless thresholds/compliance explicit" | **S** | Judge | Compress; defer to Judge |
| L52, L53 | "activate preprocessing/analysis when the task is cleaning/descriptive" | **G** | Activation gate | Keep positive routing line; route probe |
| L54 | "Knowledge excerpt is a source claim, not label truth/performance/causal evidence" | **S** | Judge | Compress; defer to Judge |
| L55, L33 | "whole-Dataset clean ≠ holdout-safe model prep; fit inside the pipeline" | **W** | preparation.py / text_analysis.py reject leaked splits; data.clean scope is documented as whole-dataset | Delete the prohibition; keep the factual split-fit statement |
| L56 | "bind repeated entities as group; never group-as-feature" | **G** | Group-overlap fail-closed; binding is a model choice | Keep positive "bind group" line; probe |
| L57 | "use the Evaluate task as authority, not metadata/algorithm names" | **G** | Evaluate task is the only source of split/metric facts; model metadata is schema-only | Keep positive "query Evaluate task" line; probe |
| L58-63 | forecast bindings / cadence / fold identity / no invented SARIMA orders | **G/W** | validate_params + SARIMA fail-closed (forecasting.py:253-289); cadence/fold semantics are model choices | Delete the "never invent orders" clause (schema-walled); keep positive forecast workflow |
| L64-72 | per-domain model-key selection, resource Dataset IDs, retrieval mode gating | **G/W** | Unsupported model keys rejected; index_diagnostic returns no ranking metrics (mode-gated) | Keep positive key-selection lines; probe; delete the "never" clauses the schema already rejects |
| L62, L69 | "never invent params / inline word dumps / local paths" | **W** | validate_params; resource inputs require registered Dataset IDs (tools.py:841-852); file authority banned | Delete; walled |

## xenix-data-preprocessing

| Ref | Rule (condensed) | Class | Evidence | Action |
| --- | --- | --- | --- | --- |
| L24, L28 | "only advertised tools; no script/filesystem runtime; never invent an operation" | **W** | Tool registry + provider schema | Delete the negative clause; keep factual "tool-only" note |
| L29 | "clean/transform/integrate create derived data; never overwrite source" | **W** | Derived-only in-memory architecture | Delete; architectural |
| L30 | "do not drop meaningful rows/columns, merge categories, change grain, or choose an ambiguous target without asking" | **UX/B** | Per D2 no wall; but these change business meaning (not reversibility) | Keep as ask-versus-act guidance, not a "do not" wall |
| L31 | "keep role binding explicit" | **B** | Not walled | Keep positive |
| L32 | "hand off reporting to analysis, training to modeling" | **G** | Activation gate | Keep positive routing line; route probe |
| L33 | "whole-Dataset clean ≠ holdout-safe prep" | **W** | Leakage fail-closed | Delete the prohibition; keep the factual statement |
| L37-42 | "Knowledge excerpt cannot authorize dropping/merging/changing grain" | **S** | Judge | Compress; defer to Judge |
| L48 | "operations execute strictly left-to-right" | **W** | data_cleaning.py ordered operation application | Keep as factual workflow note |
| L50, L65-69 | "validation is the cleaning-filter owner; do not reimplement in transform" | **W** | data.clean atomic validation ops; O4-A3 already made this the authority | Already the authority; prose can be compressed |
| L51 | "authoritative result; do not re-read rows to re-verify" | **W/B** | O4-A4 removed the verification-inviting guidance (route 3/3) | Already addressed; keep the positive finalization line |
| L73-106 | column-reference/index rules (never mix index/name; stale indexes rejected) | **W** | tool_inputs.py:322; data_cleaning.py:760-768 | Delete the "never" clauses; keep the factual rules |
