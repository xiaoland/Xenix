# Slice `[6,7]` Design — Unit TDD, Deployment, and Local-Owner Handshake

## Status and Guardrails

- Phase: Approved; Apply and Verify complete.
- Scope: documentation and direct routing references only.
- No source, test, dependency, configuration, `.vscode`, credential, runtime-state,
  packaging-output, or Git-branch mutation.
- Verified `[4,5]` changes were committed as `078d7bc` before this slice was applied.
- Future sub-agents must use `gpt-5.3-codex-spark`. The current collaboration API
  does not expose a model selector, so do not delegate unless that model can be
  guaranteed.

## Target Topology

```text
docs/30-unit-tdd/
└── README.md                         # compact Agent Harness internal memory

docs/40-deployment/
├── README.md                         # trigger-based operational router
├── packaging.md                      # build, acceptance, distribution, rollback
├── runtime-state.md                  # inspect, backup, reset, restore, support
├── observability.md                  # logs, OTLP, verification, degradation
└── local-state-evolution.md          # migration and recovery semantics

src/xenix/ui/AGENTS.md                # Qt/Windows custom-paint tripwire
src/xenix/ui/widgets/AGENTS.md        # widget-only tactical seams
src/xenix/services/agent/AGENTS.md    # Agent result/schema tripwires
src/xenix/services/storage/AGENTS.md  # migration/storage tripwires
src/xenix/services/ml/AGENTS.md       # ML execution tripwires
```

Delete:

- `docs/30-unit-tdd/agent-harness.md`
- `docs/30-unit-tdd/chatbot-ui.md`
- `docs/40-deployment/development.md`
- `docs/40-deployment/branch-governance.md`
- `src/xenix/services/AGENTS.md`

Do not create a Product TDD event document or a replacement branch-history file.

## Unit TDD Design

`docs/30-unit-tdd/README.md` becomes the only Unit TDD document, targeted at no more
than 600 words.

### Admission

State why Agent Harness passes optional Unit admission: one logical orchestration
unit contains expensive causal ordering and convergence behavior spread across a
large service, persistence boundary, and provider/tool loop. Exact records, event
shapes, tool schemas, fields, registries, and method signatures remain source/test
truth.

### Retained internal memory

Retain only refactor-stable causal invariants:

- durable conversation/run facts are established before dependent provider or tool
  side effects are projected as complete;
- one canonical tool result drives persistence and provider replay; no parallel
  human/LLM result truth is maintained;
- completion guarding occurs only at the proposed zero-tool boundary, is bounded,
  and fails closed to normal completion when guard evaluation is unavailable;
- streaming, step-budget pause/resume, cancellation, failure, and final snapshot
  converge persisted run/turn/message state rather than leaving a UI-only state;
- domain services retain data, artifact, and ML authority; LLM Service retains
  provider-adapter mechanics.

Use short source/test verification pointers. Do not include tool lists, schemas,
payload examples, table/field names, telemetry attributes, product prompt copy,
event inventories, or test checklists.

### Removed Unit projection

ChatbotEvent enums, pairing, activity/connection behavior, and UI reducers remain
owned by typed source plus Harness/UI integration tests. The Product TDD authority
entry is sufficient routing; no third prose projection is admitted.

Delete `chatbot-ui.md`. Move only the proven Windows/Qt custom-paint hazard into
`src/xenix/ui/AGENTS.md` as a concise local tripwire with its required UI test. All
other UI layout, control, streaming, artifact, worker, and test inventory returns to
product, Product TDD, source, or tests.

## Local `AGENTS.md` Owner Handshake

The Unit/Deployment cleanup cannot leave their rejected claims duplicated in local
instructions. Include only the local-owner changes required to close those moves;
this is not a general expansion of documentation.

### Delete broad service guidance

Delete `src/xenix/services/AGENTS.md`. Its current Agent, storage, dataset/artifact,
ML binding, migration, and retired WorkItem claims are already owned by Product TDD,
Unit TDD, Deployment, source/tests, or narrower seams. A broad service instruction
would remain a parallel architecture document rather than a physical tripwire.

### Add `src/xenix/services/agent/AGENTS.md`

Create a short tactical owner for repeated Agent implementation hazards:

- persist and replay one canonical tool result; do not create a second provider-
  facing result truth;
- keep provider schemas within the conservative portable subset and enforce complex
  mutual-exclusion/priority rules in execution validation;
- keep raw paths, credentials, debug/observability dumps, and unbounded evidence out
  of provider-facing schemas/results;
- preserve typed ChatbotEvent projection rather than making UI parse storage rows or
  tool payloads;
- route causal provider-loop/guard reasoning to Unit TDD and exact mechanics to
  source/tests.

Name focused Harness/tool-schema verification paths without copying a test checklist.

### Add `src/xenix/services/storage/AGENTS.md`

Move migration-author tripwires to the physical storage seam:

- add forward migration edges; never rewrite a potentially deployed edge;
- increment the source-owned current version and prove fresh bootstrap plus upgrade;
- inspect the ORM's configured enum representation before raw SQL/data migration and
  prove ORM readability afterward;
- repair app-owned bad persisted data through migration, not tolerant model reads;
- keep operational backup, unsupported-state, quarantine, and restore semantics in
  Deployment.

Do not copy the current numeric version, table/field inventories, or SQLAlchemy
tutorial prose.

### Refine existing ML guidance

Keep `src/xenix/services/ml/AGENTS.md` only for local shortcuts that nearby edits can
prevent:

- within `services/ml/`, worker runners, pools, and adapters remain execution helpers;
  task lifecycle branching and finalization stay outside this subtree and route to
  Product TDD;
- process entrypoints remain `spawn`-compatible and top-level for packaged Windows;
- registry metadata stays typed and provider/UI-facing schema remains shallow;
- evaluation-policy changes stay with the named evaluation owner and focused tests.

Route worker authority, no-failover, local finalization, and artifact/storage meaning
to Product TDD instead of restating them. Remove issue/milestone and legacy history.

### Refine UI guidance

Keep `src/xenix/ui/AGENTS.md` for UI-local hazards: translation lifecycle, timer
shutdown, service-driven boundaries as a short Product TDD reference, focused widget
composition, and the approved Windows custom-paint tripwire. Product identity,
Chatbot default behavior, Agent/Artifact authority, commands, and full translation
workflow stay in PRD, Product TDD, root/CONTRIBUTING, source, and tests.

Make `src/xenix/ui/AGENTS.md` apply to the whole UI subtree. Then keep
`src/xenix/ui/widgets/AGENTS.md` additive and widget-specific: policy-light shared
widgets, deterministic returned ordering, and moving view-specific workflow back to
the parent/service. Remove repeated translation policy now inherited from the parent.

Target at most 1,200 words across all retained local `AGENTS.md` files added or
changed by this handshake.

## Deployment Design

### `README.md` — operational router

Target at most 200 words. Route by trigger, not filename inventory:

| Trigger | Owner |
| --- | --- |
| Build, packaged acceptance, distribution, packaged-only failure, rollback | `packaging.md` |
| Locate active state, inspect evidence, back up, reset, restore, create a support bundle | `runtime-state.md` |
| Configure or diagnose logs, traces, metrics, and OTLP export | `observability.md` |
| Understand automatic migration, unsupported state, or migration failure recovery | `local-state-evolution.md` |

State that source/config/scripts/tests own exact paths, manifests, versions, fields,
and automation behavior.

### `packaging.md` — build and release artifact operations

Replace `development.md`; target at most 550 words.

Retain:

- admission, consumer, trigger, and failure impact;
- the operator sequence `package -> smoke-package -> dist` without copying ordinary
  install/test/translation workflow;
- build-time trial/provider/build-commit inputs and their sensitivity/consistency
  implications, while scripts own exact parsing;
- packaged acceptance: packaging success is insufficient; the packaged smoke gate
  proves only its current automated exercises, not every dependency;
- native/compiled dependency risk classes and concise evidence locations;
- release blocking, re-verification, and rollback to a previously verified bundle;
- packaged-only troubleshooting that is expensive to rediscover.

Remove dependency lists, product workflow inventory, VS Code, app-directory copies,
translation instructions, exact spec collect lists, and unsupported blanket smoke
guarantees.

### `runtime-state.md` — safe local-state operations

Target at most 600 words.

Retain operational meaning, not an exhaustive generated tree:

- how to determine active runtime home and distinguish config, logs, database,
  app-owned datasets/artifacts, task state, cache, and user-owned source data;
- a symptom-to-evidence inspection matrix;
- safe recovery order: stop/quiesce -> forecast blast radius -> back up -> choose
  isolated home, database quarantine/rebuild, or full reset -> restart -> verify;
- explicit data-loss boundary for each reset level;
- a consistent backup set, restore sequence, and restore verification;
- remote-worker revalidation/cache cleanup safety, with local authority routed to
  Product TDD and known realization gaps routed to ADR 0005;
- diagnostic-bundle generation as local-only sensitive support evidence. Manual
  sharing requires review of logs, task logs, the pseudonymous install id, and
  database summaries, plus recipient/retention/deletion discipline.

Source and tests own exact directory/file inventories and diagnostic archive
manifest.

### `observability.md` — telemetry operations

Create one owner, targeted at no more than 450 words.

Retain:

- local JSON logging and operational rotation/retention behavior;
- persistent pseudonymous install identity and its correlation/sensitivity meaning;
- Xenix-specific trace/metric/log enablement defaults, signal-specific precedence,
  and the fact that remote log export is explicit;
- non-blocking interactive startup when the backend is slow or unavailable;
- how to verify export at the backend and through local failure evidence;
- how to disable/degrade a failing signal and verify recovery;
- sensitivity boundary for local logs and remote log export.

Do not copy telemetry span/metric schemas, standard OTel documentation, code branch
logic, multiple backend-specific tutorials, or diagnostic-bundle manifest.

### `local-state-evolution.md` — migration and recovery

Target at most 400 words.

Retain operator/developer semantics that code alone does not communicate cheaply:

- known supported versions migrate forward in place at startup;
- source/tests own the current version and exact edges; do not copy a version number;
- automatic migration has no automatic pre-migration backup and no rollback;
- backup is required before risky migration or destructive recovery;
- unsupported/corrupt state, migration failure, database quarantine, restore, and
  fresh bootstrap are distinct paths with explicit verification;
- app-owned bad data is repaired by a forward migration, not tolerant model reads.

Move exact edge/function shape, SQLAlchemy enum behavior, field representation,
version snapshots, and contributor test checklists back to source/tests and the
deferred local-instruction slice.

## Direct Routing Changes

- Root `AGENTS.md`: remove VS Code from the Deployment route; point detailed
  operations to packaging, runtime state, observability, and local-state evolution;
  describe Unit TDD as Agent Harness internal memory rather than generic complex UI.
- Root `README.md`: replace the deleted Development Runbook link with the packaging
  and runtime routes.
- `docs/README.md`: route Unit TDD to Agent Harness internal design and Deployment to
  its trigger-based index.
- `CONTRIBUTING.md`: remove `chatbot-ui.md`; UI work uses nearest local instructions,
  cross-unit authority uses Product TDD, packaging uses `packaging.md`, and migration
  recovery uses `local-state-evolution.md`.
- `src/xenix/ui/AGENTS.md`: add only the approved custom-paint hazard and verification
  tripwire while removing wrong-owner duplicates.
- Add narrower Agent and storage instructions, refine ML/widgets guidance, and delete
  broad services guidance as specified above. No other local instruction is added.

## Impact Handshake

- **Address and Object**: three Unit TDD files, five Deployment files plus one new
  observability owner, root/docs/contributor routes, root README, two new narrow local
  instructions, three refined local instructions, and deletion of broad services
  guidance.
- **State Diff**: two implementation-snapshot Unit docs, four mixed/stale operational
  docs, and overlapping broad/local instructions -> one admitted Unit memory, four
  trigger-specific operational owners, narrow physical tripwires, and closed routes.
- **Blast Radius**: documentation cold start, Agent/UI engineering routes, package
  and support operations, migration/reset safety, telemetry setup, and later local
  instruction cleanup. No application, data, package, branch, credential, or runtime
  effect.
- **Invariants**: current behavior and automation are not expanded; Product TDD
  remains canonical for cross-unit authority; typed source/tests retain event truth;
  ignored credentials remain untouched; SSH defects remain unfixed; accepted ADR
  history and `[4,5]` changes remain intact.

## Verification

1. All durable Markdown paths, fragments, and reference labels resolve; deleted
   filenames have zero remaining references.
2. `git diff --check` and trailing-whitespace checks pass.
3. Unit TDD has one file with explicit admission, internal invariant scope,
   mechanical-owner exclusions, and verification pointers; no tool/event/field/test
   inventory remains.
4. Deployment README routes all four operational triggers. Every retained file names
   consumer, trigger, failure impact, operational action, and verification.
5. Packaging includes the package/smoke/distribution acceptance chain, bounded smoke
   guarantee, release blocking, re-verification, and previous-artifact rollback.
6. Runtime recovery orders backup before destructive reset and includes restore and
   post-restore verification; diagnostic sharing is explicitly manual and sensitive.
7. Local-state evolution contains no numeric schema baseline or enum coding tutorial
   and states in-place/forward-only/no automatic backup/no rollback semantics.
8. Observability contains enablement, sensitivity, health verification, safe
   degradation, and recovery; duplicate OTel tutorials are absent elsewhere.
9. No durable Deployment mention of VS Code, branch rename, issue provenance,
   exhaustive dependency inventory, product tool inventory, or current schema
   version remains.
10. Every retained local `AGENTS.md` names a physical scope, local hazard, forbidden
    shortcut, and focused verification. No product promise, cross-unit authority,
    operational runbook, issue history, exact version, or broad root-policy copy
    remains. The deleted broad services file has zero references.
11. Source-alignment spot checks cover PDM scripts, runtime-home resolution, logging
    rotation, migration behavior, database quarantine, diagnostic-bundle contents,
    telemetry defaults, packaged smoke scope, and SSH setup/recovery reality.
12. Word budgets: Unit TDD at most 600 words; Deployment router plus four runbooks at
    most 2,200 words; affected local instructions at most 1,200 words. The Unit plus
    Deployment surface falls from 9,936 to at most 2,800 words.
13. Scope diff contains no source, test, dependency, `.vscode`, credential, branch,
    or generated package mutation. Code tests are not required for a documentation-
    only change; existing tests are read-only evidence.

Sir approved this design; Apply and Verify completed without expanding its durable scope.
