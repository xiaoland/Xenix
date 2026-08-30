# PR merge evaluation (4 merged PRs)

## Objective

Assess whether the four recently merged PRs — (1) General Job Layer,
(2) Agent Harness observability, (3) Knowledge document intelligence,
(4) Dataset age audit — meet the bar on **functionality** and
**maintainability**, and record evidence-backed verdicts plus any concrete
correction needs.

## Guardrails

- Read-only evaluation. No source mutation without an explicit follow-up
  approval (Impact Handshake).
- Evidence only: code, config, schemas, tests, git history. No claims without a
  file/line or command reference.
- Existing durable owners (docs/20-product-tdd, docs/30-unit-tdd, docs/10-prd,
  docs/40-deployment) remain authoritative; this packet is disposable workspace.
- Do not weaken existing tests or guardrails to make a PR "pass".

## Verification

- One verdict per PR (functional + maintainability), each with concrete evidence
  (diff scope, key files, test status via `pdm run` where runnable).
- Cross-cutting notes on any shared anti-patterns across the four PRs.

## Current Truth

Merges map (first-parent linear chain on develop):
- 6a8d896 (base) -> 32d1c07 merge #121 dataset-age-audit (branch tip 8d7572f)
- 32d1c07 -> 1b048c3 merge #123 knowledge-document-intelligence (tip 9fd11b0)
- 1b048c3 -> e6099c4 merge #120 agent-harness-observability (tip dfd5eb1)
- e6099c4 -> d5a5087 merge #122 general-job-layer (tip 2e9b819) = HEAD develop

Each PR's diff vs its first parent isolates exactly what it introduced.
Environment: Python 3.14.0, PDM 2.28.0, .venv present (Windows).

## Next Step

Gather per-PR evidence: read changed files, run targeted tests, then write
verdicts.

---

## Verdicts (evidence-backed)

### 1. General Job Layer — merge d5a5087 (PR #122)
- **Functional: met.** `JobQueryService` projects ML + Knowledge into one
  read-only feed; `JobCenterDialog` adds global filter/search/refresh/summary/
  details. Focused tests pass (2/2). No schema migration, no duplicate lifecycle
  state — correct projection design.
- **Maintainability: mostly met, minor issues.**
  - `_knowledge_status` silently maps unknown statuses to SUCCEEDED while the ML
    path uses strict `JobStatus(task.status.value)` — inconsistent failure modes
    and a future status would be silently misclassified.
  - `JobSummary.total_count` is the capped returned count (<=500), not a true total.
  - Translation via `.replace("%1", ...)` is more fragile than Qt `.arg()`.
  - `JobItem.target` can be None (both dataset_id and project_id absent), which
    would break the search `.join(...)`.

### 2. Agent Harness observability — merge e6099c4 (PR #120)
- **Functional: met.** Lifecycle spans, trace_id, exception chains, journal
  recovery after timeout; terminal output joins cell -> trace_id + report path;
  production `submit_user_turn_stream` wraps with OTel `start_span`.
  `benchmark-agent-harness-check`: 36 passed.
- **Maintainability: met.** Vocabulary documented (30-unit-tdd + 40-deployment).
  Two trace impls (vendor-neutral benchmark telemetry vs production OTel) is a
  documented, deliberate offline boundary.
- **Scope note:** the premise "ignore all safety/privacy" was NOT fully adopted.
  The PR made a scoped relaxation (trace diagnostics may retain paths/identifiers/
  exception chains for repro) but kept Judge evidence bounded and privacy-safe
  fixtures. This is the right call; recommend keeping the remaining boundary.

### 3. Knowledge document intelligence — merge 1b048c3 (PR #123)
- **Functional: met for tested paths.** AnyDoc Rust parser (firecrawl-anydoc
  0.2.4) for DOC/DOCX/PPT/PPTX/RTF/EPUB/ODT/ODP; bounded package validation
  (zip-bomb/path/symlink/compression); heading hierarchy + bounded sentence-overlap
  chunks. Focused tests pass (31).
- **Maintainability: NOT met.** `pdm run check` fails with 2x F821 undefined
  names in `knowledge_pipeline.py`: `_OoxmlPackageProfile` (L218) and
  `_ooxml_error` (L226). Commit 499c480 renamed these to `_ZipPackageProfile`
  and `_package_error` but left two stale references in
  `_OoxmlOfficeProbeProvider`. Runtime impact: importing a .docx/.pptx that is
  actually legacy OLE (e.g. .doc renamed) raises NameError instead of a clean
  ValidationError. The PR's own "run linting" verification was not satisfied.

### 4. Dataset age audit — merge 32d1c07 (PR #121)
- **Functional: met.** v26 derivation + ordered input edges; transform/clean/
  integrate/tokenize record operation, inputs+aliases, parameters, optional
  agent explanation; generation depth computed; GUI renders audit with
  "not system-verified" notice. Verified via standalone harness run (audit
  resolves, generation=1, correct inputs/params/explanation).
- **Maintainability: test not reproducible on this machine.** Its own test
  `test_multi_input_transform_records_and_projects_dataset_audit` FAILS here
  (repo F:, system temp C:). Root cause is a PRE-EXISTING bug (not from this PR):
  `data_transform.py:485` uses `Path.replace()` to move output from
  `tempfile.TemporaryDirectory()` (C: temp) into `paths.temp` (F:), raising
  `OSError [WinError 17]` cross-drive. Fix: `shutil.move`. The test is not
  hermetic (passes single-fs Linux, fails multi-drive Windows).
- Minor: "dataset age" is implemented as generation depth, not temporal age;
  matches the PRD but the feature name "age" is slightly misleading.

## Cross-cutting
- Two of four PRs left the tree red: PR3 fails `pdm run check`; PR4's test fails
  on multi-drive Windows. Merge did not gate on `pdm run check` + full suite.
- The pre-existing `data_transform` cross-drive bug is now exposed by PR4's test
  — concrete follow-up fix (`Path.replace` -> `shutil.move`).
- Authority/naming discipline is otherwise strong (read-only projections, one
  authority per record, unverified agent explanations marked as such).

## Next Step
Confirm with the human which corrections to apply (PR3 rename fix is trivial and
should be done; PR4 cross-drive fix is pre-existing but worth fixing + a hermetic
test). These require the Impact Handshake before mutation.

---

## Fix applied (approved)

- `knowledge_pipeline.py`: `_OoxmlPackageProfile` -> `_ZipPackageProfile` (L218);
  `_ooxml_error` -> `_package_error` (L226) — resolves the 2x F821.
- `data_transform.py`: added `import shutil`; `temp_output_path.replace(output_path)`
  -> `shutil.move(temp_output_path, output_path)` (L485) — cross-drive-safe move.

Verification: `pdm run check` = 0 (All checks passed); focused pytest = 47 passed
(was 46 passed / 1 failed). Dataset-audit test now passes on multi-drive Windows.

---

## Round 2 — small fixes + PR4 session-audit GUI (in progress)

### Doc typo
- `docs/10-prd/README.md`: fixed lowercase "documents" -> "Documents" + reflow.

### PR4 modeless session audit window (approved design: session-level list)
Service (authority-preserving):
- `DatasetService.resolve_dataset_audits_for_tool_calls(ids)` (plural); single-id
  method delegates to it.
- `LLMConversationService.list_tool_call_message_ids(thread_id)`.
- `AgentHarnessService.resolve_session_dataset_audits(thread_id)` composes the two.

GUI:
- New `src/xenix/ui/dataset_audit_dialog.py` — `DatasetAuditDialog` (NonModal,
  WA_DeleteOnClose False), table (Dataset/Generation/Operation/Inputs/Recorded) +
  detail pane (inputs, parameters, unverified explanation).
- `main_window.py`: header "Datasets" button -> `_open_session_dataset_audit`.

i18n: 20 new strings extracted + completed in en_US/zh_CN (445/445), compiled.

Verification: `pdm run check` = 0; focused pytest = 45 passed (incl. new
session-level assertion in test_agent_dataset_audit.py).

### Remaining PR1 nits (not changed — mostly nits/false-alarm)
- `_knowledge_status` silent SUCCEEDED default (defensible for a projection).
- `JobSummary.total_count` mislabel (test-only API; GUI computes its own).
- `.replace("%1")` vs `.arg()` in job_center (roughly equivalent edge cases).
- `JobItem.target` None: false alarm — MLTaskRow.project_id is non-nullable.
