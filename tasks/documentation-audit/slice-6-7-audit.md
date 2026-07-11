# Slice `[6,7]` Audit — Unit TDD and Deployment

## Status and Scope

- Phase: Confirm. This file records evidence, not a repair design.
- Audited: `docs/30-unit-tdd/` and `docs/40-deployment/`.
- Evidence only: current source, tests, scripts, configuration, root/CONTRIBUTING,
  Product TDD, local `AGENTS.md`, Git topology/history, and canonical SVC rules.
- Excluded: local `AGENTS.md` repair, source/runtime repair, credential mutation,
  `[4,5]` changes, and commit.
- Size: Unit TDD is 3 files / 5,984 words; Deployment is 5 files / 3,952
  words. Combined retrieval surface is 9,936 words.

## P0 — Safety and Data-Loss Risk

### 1. Documented VS Code entry points are absent from a clean checkout, while local ignored copies contain credential literals

`docs/40-deployment/development.md:229-235` presents named VS Code launch profiles
and tasks as standard project entry points. `.gitignore:36-37` ignores `.vscode/*`
except example files; Git tracks only `.vscode/settings.json`, and commit `b4ea308`
removed the tracked launch/tasks files. A clean checkout therefore cannot use the
documented profiles.

A sanitized scan of the current ignored `.vscode/launch.json` and
`.vscode/tasks.json` found non-placeholder literal assignments for telemetry auth
headers, a trial LLM API key, and a trial-lock signing secret, including Bearer
content. No value was printed, recorded, or tested. The current audit found no
evidence that these literals entered Git history; this is a local credential-hygiene
risk, not a proven repository leak.

### 2. Migration guidance can direct deletion of a database the code supports upgrading

- `docs/40-deployment/local-state-evolution.md:43` claims schema baseline 12;
  `runtime-state.md:87`, `src/xenix/services/storage/migrations.py:12`, and tests
  define 14.
- `local-state-evolution.md:45` directs deletion of older development databases.
  `migrations.py:741-775` implements continuous v1 through v14 migration, and
  `tests/test_storage_bootstrap.py` covers those upgrade paths. Only unknown or
  unsupported versions reach the obsolete-baseline error.

The two Deployment owners contradict each other and the destructive instruction can
discard state that current code can migrate.

## Unit TDD Findings

### P1

1. **The Unit TDD entry misroutes claims.** `docs/30-unit-tdd/README.md:5` assigns
   cross-submodule constraints, architectural boundaries, and technology choices to
   Unit TDD. SVC admits only expensive internal truth of one logical unit that can
   change without forcing another unit to update, survives physical refactors, and
   is not cheaply preserved by code/types/schema/tests. Cross-unit contracts belong
   in Product TDD.
2. **Agent Harness contains a false turn-end statement.** `agent-harness.md:52-53`
   correctly includes the completion guard, but line 61 again says a zero-tool
   provider response ends the turn. Current Harness can persist a guard reminder and
   continue the provider loop; `tests/test_agent_harness_streaming.py:1503-1621`
   covers continuation and the retry limit.
3. **Agent Harness is a parallel implementation registry.** Records and table
   fields, guard persistence, token-usage fields, exact tool inventory, skill catalog
   mechanics, complete tool schemas, model taxonomy, placement details, provider
   method signatures, and a test checklist occupy `agent-harness.md:26-271`. Line
   210 alone is about 7,594 characters and combines dozens of independently changing
   facts already owned by source/schemas/tests.
4. **Agent/UI compatibility has two Unit owners.** ChatbotEvent projection,
   request/result pairing, `ACTIVITY`, `CONNECTION`, streaming convergence, system
   message visibility, artifact activation, and cancellation appear in
   `agent-harness.md:85-137` and `chatbot-ui.md:31-50,75-94`. At least two units depend
   on these claims; they cannot remain two private Unit truths.
5. **Agent Harness includes other owners.** The exact business-analysis prompt at
   line 145 is product/source truth; observability at 163-174 crosses Harness, LLM
   Service, and telemetry; provider boundaries at 235-250 are cross-unit; artifact,
   storage, and ML details repeat current Product TDD.
6. **Chatbot UI is largely a widget/test snapshot.** Lines 9-29, 36-47, and 60-73
   list widgets, 20 px padding, width ratios, QtAwesome, controls, and exact layout.
   Source and `tests/test_main.py` already preserve these mechanics.
7. **UI inventories have already drifted.** `chatbot-ui.md:11` omits Generate title
   and Copy thread ID history actions; lines 13-14 omit language, default/guard/title
   model, and retry settings. `agent-harness.md:11` likewise omits title generation
   while line 239 later mentions title-model calls.

### P2

- `agent-harness.md` is 4,299 words across records, provider loop, guard, timeline,
  tool results, streaming, prompt, usage, observability, cancellation, tool catalog,
  provider boundary, and tests. It has 44 commits and changes with ordinary feature
  work rather than slow-moving internal invariants.
- `chatbot-ui.md` is 1,611 words and changed with Agent Harness in 13 commits. This
  shared cadence supports the duplicate cross-unit-owner diagnosis.
- Test obligations in both files repeat CONTRIBUTING and existing test suites.
- Historical terms such as “first-slice” remain in current contracts.
- The Windows Qt custom-paint/repaint hazard in `chatbot-ui.md:52-58` may be valuable
  expensive memory, but its correct owner may be Unit TDD or the deferred local UI
  `AGENTS.md`; audit does not decide that placement.

## Deployment Findings

### P1

1. **Branch governance is stale and in the wrong owner.** `branch-governance.md` is
   an issue `#68` migration checklist that still treats `master -> web` as pending
   and the native branch as a bootstrap milestone. Current Git has
   `origin/HEAD -> origin/web`, `web`, `native`, and `native-ai-first`; the current
   branch is `native-ai-first`. Repository/branch workflow belongs in root,
   CONTRIBUTING, or Git configuration, not Deployment.
2. **Runtime-path inventory is false and internally inconsistent.**
   `runtime-state.md:23-37` lists `artifacts/datasets/transformed/` although the
   transform workspace is `temp/datasets/transformed`; lists `artifacts/reports/`
   without a source consumer; and omits canonical `state/datasets/imported|derived`,
   `artifacts/datasets/exports`, and `artifacts/training`. Lines 50 and 129 then use
   paths absent from the initial inventory.
3. **SSH setup overpromises current behavior.** `development.md:45` says setup
   installs required ML dependencies. ADR 0005 now records that fresh-worker setup
   omits required DuckDB. The runbook cannot claim successful dependency closure.
4. **Packaged-smoke coverage is overstated.** `development.md:197,209-227` says
   first-party ML/data-science runtimes are exercised, but
   `src/xenix/app.py:572-679` directly exercises DuckDB, Polars CSV/XLSX,
   Vega-Lite, word cloud, and XGBoost only. Other direct first-party dependencies
   are packaged without equivalent runtime exercises.
5. **The Deployment entry does not route operators.** Its README contains four bare
   filenames with no links, consumers, triggers, failure risk, or statement that
   code/config/automation retain mechanical authority.
6. **`development.md` mixes unrelated owners.** Install/run/test, dependency lists,
   product capability inventory, provider/worker semantics, observability,
   translation workflow, packaging, VS Code, paths, and troubleshooting have
   distinct consumers and cadence. Repository workflow belongs to root,
   CONTRIBUTING, and executable config; product capabilities belong to PRD.
7. **`runtime-state.md` becomes a schema/architecture snapshot after its runbook.**
   Lines 85-125 copy dataset tools, schema version, enum encodings, tables/columns,
   prompt persistence, model fallback, packaging secrets, ML migrations, guard
   records, worker authority, and issue-numbered history. Most are mechanically
   owned or already routed elsewhere.

### P2

- Development and runtime state duplicate OTLP variables, signal enablement,
  exporter flush behavior, diagnostic-bundle content, runtime directories, worker
  configuration, and database/log fast paths. They changed together in 19 commits.
- Runtime state and local-state evolution changed together in all 10 changes to the
  latter, yet still drifted on schema version.
- Agent Harness and Development changed together in 14 commits, evidence that
  runtime and implementation snapshots are coupled rather than independently
  admitted durable knowledge.
- `development.md` copies a partial dependency inventory from `pyproject.toml` and
  exact VS Code/PDM entry names already owned by configuration.
- `local-state-evolution.md` duplicates forward-migration and enum rules in
  `src/xenix/services/AGENTS.md`; local guidance is evidence only in this slice and
  remains for number 3.
- The diagnostic bundle contains the persistent install id, local application logs,
  ML task logs, and SQLite schema/table-count summaries. The docs say it omits the
  raw database but do not state the sensitivity or sharing boundary of the retained
  data.

## SVC Conformance Diagnosis

1. Both indexes list files rather than routing a consumer by trigger and admission.
2. Unit TDD stores cross-unit contracts and mechanics that fail one-unit admission.
3. Deployment stores repository workflow, product behavior, and source-owned
   snapshots beyond packaging, runtime, migration, observability, and recovery.
4. One-claim ownership is violated across Product TDD, both Unit documents, two
   Deployment runbooks, CONTRIBUTING, and deferred local instructions.
5. Content that still plausibly passes admission is narrow: Harness guard/result
   invariants, the Qt/Windows repaint hazard, package-native smoke and recovery,
   OTLP operator configuration, runtime inspect/reset/backup, and migration recovery.

## Expanded Admission Audit

### Unit surfaces

| Surface | SVC admission judgment | Structural reason |
| --- | --- | --- |
| Unit TDD README | Fails | Its admission rule selects cross-unit architecture and does not test independence, refactor survival, mechanical ownership, consumer, or loss cost. |
| Agent Harness Unit TDD | Surface passes; most current content fails | The 2,000-line orchestration unit has expensive causal state, guard, and result-authority reasoning. Exact records, schemas, registry, provider interfaces, events, telemetry, and tests remain wrong-owner snapshots. |
| Chatbot UI Unit TDD | Fails after the Qt seam moves | Observable UI behavior, Agent/UI compatibility, artifact/ML rules, layout, and tests already have product, Product TDD, source, and test owners. No remaining expensive private invariant proves a separate surface. |

Agent Harness therefore has real Unit pressure, but the current file does not
distinguish expensive causal invariants from mechanically recoverable implementation.
Chatbot UI does not pass admission merely because the UI is large.

### Deployment surfaces

| Surface | SVC admission judgment | Valid operational pressure | Structural failure |
| --- | --- | --- | --- |
| Deployment README | Passes only as a router | Runtime, package, telemetry, migration, and recovery have real consumers | No links, triggers, symptoms, loss risk, or mechanical-owner boundary |
| Development: install/run/test/translation | Fails | None beyond ordinary contribution | Third command owner beside root, CONTRIBUTING, PDM, and scripts |
| Development: dependency/product inventory | Fails | None | Copies `pyproject.toml`, PRD, Product TDD, and source |
| Observability | Partially passes | Configure export, diagnose backend failure, preserve non-blocking startup | Duplicate configuration truth; no success check, evidence path, degradation, or recovery loop |
| Diagnostic bundle | Passes as an operational contract | Escalate local evidence safely | Describes archive content but not sensitivity, review, recipient, transfer, retention, deletion, or failure handling |
| Package/smoke/troubleshooting | Passes | Release builder and packaged-only native failures | Mixes automation manifests with prose; lacks an explicit acceptance gate, release blocker, containment/rollback, and re-verification shape |
| Runtime state | Passes for inspect/reset/backup/recovery | Locate active state and recover a broken local app | Exhaustive path/schema snapshots replace symptom-to-evidence routing; reset and backup are incomplete |
| Local state evolution | Passes for operator migration/recovery semantics | Forward migration and failed-start recovery | Mostly contributor coding rules and schema mechanics; operator contract is incomplete |
| Branch governance | Fails | Consumer and trigger have ended | Completed repository migration in the wrong owner |

## Single-Owner Decisions from the Audit

1. **Agent ↔ Chatbot events remain source/test truth.** `chatbot_events.py`, typed
   event models, Harness projection tests, streaming integration tests, and UI tests
   make exact shape and convergence cheap to recover. Existing Product TDD already
   owns the high-level authority direction. A new Product TDD event document would
   add a third projection rather than preserve otherwise-lost truth.
2. **Agent Harness may retain only internal causal memory.** Persistence-before-side
   effect ordering, provider-loop convergence, completion-guard failure behavior,
   canonical tool-result authority, and cancellation/step-budget convergence are
   the candidate expensive concerns. Current field lists and method flows are not
   evidence that every candidate must remain prose.
3. **Artifact, storage, and ML authority remain Product TDD truth.** Unit and
   Deployment documents need only route to those contracts when an operational
   action depends on them.
4. **Migration recovery belongs to Deployment; mechanics do not.** Source,
   migrations, ORM models, and tests own version edges, enum representation, and the
   current version. Deferred services `AGENTS.md` may keep only a short local
   tripwire/reference.
5. **Telemetry operation belongs to Deployment; span schemas do not.** Source/tests
   own attributes, exporters, and redaction mechanics. Deployment owns enablement,
   sensitivity, failure evidence, safe degradation, and verification.
6. **Repository workflow stays outside Deployment.** Root, CONTRIBUTING, PDM/scripts,
   and checked-in configuration own daily commands, translations, dependency setup,
   VS Code, and release workflow entry points.

## Completeness Gaps

### Unit TDD

- Neither document states its real consumer, loss cost, why source/tests are
  insufficient, refactor-stable invariant set, or verification route.
- Agent Harness is broad but incomplete in the wrong way: it inventories current
  features while failing to separate causal ordering, failure convergence, and
  authority rationale from mechanics.
- Chatbot UI lacks independent Unit content once cross-unit contracts, product
  behavior, geometry, tests, and the local Qt seam are removed.

### Deployment

- The executable distribution command `pdm run dist` has no durable operator route;
  packaging stops before distribution, rollout, or rollback semantics.
- Reset guidance appears before backup guidance and does not distinguish database
  quarantine, database-only rebuild, isolated runtime home, and full runtime reset.
  It lacks a data-loss forecast and post-recovery verification.
- Backup guidance has no quiesce/consistency precondition, restore sequence, restore
  verification, retention, or cleanup rule.
- Migration prose does not state the realized operational contract clearly: known
  versions migrate forward in place, no automatic pre-migration backup or rollback
  exists, and unsupported-state recovery is a separate path.
- Observability has configuration examples but no exporter health proof, failure
  evidence, disable/degrade procedure, or verification after recovery.
- Log documentation omits rotation/retention behavior relevant to diagnosis.
- Remote-worker operations describe setup but not revalidation, cleanup, cache
  recovery, or how a failed setup returns to a known state.
- Packaged smoke has no machine-readable manifest tied to prose guarantees; current
  wording overstates exercised dependencies.
- Both layer indexes fail progressive loading. Root claims `docs/README.md` reaches
  the exact owner, but the Unit and Deployment indexes cannot route by trigger.

## Settled Audit Judgments

- Deployment will not own VS Code instructions.
- The current ignored credential literals are excluded from action by Sir; do not
  rotate, delete, print, validate, or otherwise process them in this task.
- The Qt/Windows custom-paint hazard belongs in the deferred
  `src/xenix/ui/AGENTS.md` slice, not Unit TDD.
- `branch-governance.md` has no retained admission and may be deleted without a
  replacement durable document.
- Agent ↔ Chatbot event details remain mechanically owned by typed source and
  integration tests; do not add a Product TDD event surface.
- Diagnostic bundle generation is local-only by current implementation. Deployment
  must treat it as a sensitive support artifact: external sharing is manual and
  requires review of logs, task logs, the persistent pseudonymous install id, and
  database summaries. Source/tests continue to own the exact archive manifest.

## Confirmation Gate

Awaiting Sir's confirmation that this expanded admission, redundancy, structure,
completeness, and SVC-conformance problem set is sufficient to enter Design.

No repair topology or durable mutation is implied until Sir confirms or adjusts
this problem set.
