# Slice `[4,5]` Design — PRD, ADR, Product TDD

## Status

- Phase: Verify complete; Sir approved Apply, the design is implemented, and all
  settled checks pass. Awaiting an explicit commit command.
- Scope: documentation and direct routing references only.
- Reality exclusions: do not change SSH setup dependencies, bundle invalidation, source, schemas, tests, configuration, or runtime behavior.
- Calibration: current source/tests define implemented behavior; product intent defines audience and why.

## Target Topology

```text
docs/10-prd/
└── README.md

docs/20-product-tdd/
├── README.md
├── storage-ownership.md
├── artifact-links.md
├── ml-task-lifecycle.md
└── adr/
    ├── README.md
    ├── 0001-...md through 0005-...md
    ├── 0006-bounded-sqlite-application-state.md
    └── 0007-remote-integrations-remain-adapters.md
```

Delete `docs/10-prd/product-scope.md`, `docs/10-prd/glossary.md`, and `docs/20-product-tdd/runtime-boundaries.md` after their admitted claims have one destination. Do not create replacement route, glossary, or runtime files.

## PRD Design

`docs/10-prd/README.md` becomes the complete product-truth cold start, targeted at at most 800 words.

1. **Purpose and Pressure**: Xenix helps non-technical business users, primarily business and marketing staff, turn local tabular data into decision-ready analysis without operating a data/ML stack or choosing algorithms directly.
2. **Claims and Evaluation**: a compact table owns each current product promise, its rationale, observable success, and evidence class. Claims cover conversation-led intake and analysis, safe derived-data work, business-readable results, reusable analyzers, local product authority with optional remote compute, and English/Simplified Chinese operation.
3. **Capabilities and Workflows**: describe user-observable paths, not tool names or schemas: attach supported tabular data; inspect, clean, combine, transform, and visualize it; train/tune/apply reusable analyzers; review outputs through conversation and artifacts; configure the LLM used by a thread.
4. **Rules and Scope**: single local operator; source inputs remain intact; user-openable results are locally authoritative and reviewable; SSH workers provide compute/cache only; no accounts, tenancy, Xenix-owned remote backend, or browser-first workflow. Trial-build expiry remains one product-visible rule; configuration and recovery details stay in Deployment/source.
5. **Business Language**: keep only the few distinctions users and product discussion need, including dataset, artifact, LLM model, trained analyzer/model, and ML worker.

After technical ontology is removed, the remaining vocabulary has the same consumer and cadence as product truth. A separate glossary and migration-era retained/removed ledger therefore fail SVC split admission.

## Product TDD Design

### `README.md` — System Authority and Routing

Target at most 450 words. It owns:

- Product TDD admission and the dependent-unit routing table.
- The stable dependency direction `UI -> services -> adapters/persistence`.
- Global authority: UI collects/renders; services own workflow semantics and orchestration; adapters own provider/ML mechanics; SQLite/filesystem remain behind service-owned boundaries; remote execution is never product authority.
- Short links to the three admitted seam contracts and to Unit TDD/Deployment rather than copies.
- Verification entry points and the rule that schemas, fields, tool inventory, limits, paths, and migrations remain mechanically owned.

Delete `runtime-boundaries.md`; do not distribute its paragraphs mechanically. Retain only its admitted topology/authority claims in the README. Tool descriptions, provider loops, numeric limits, worker mechanics, and test policy already have better owners and are deleted from Product TDD.

### `storage-ownership.md` — Storage Medium and Identity

Target at most 450 words. Retain only:

- admission: services, persistence, Agent, data, artifact, and ML units rely on the same authority split;
- SQLite for bounded queryable application state and references;
- filesystem for datasets, models, logs, caches, and user-openable bytes;
- dataset identity versus artifact identity, local canonical authority, provenance, consistency, and deletion invariants;
- source/test/Deployment verification pointers.

Delete schema versions, table and field inventories, enum encoding, concrete runtime-directory snapshots, library choices, migration residue, and duplicated tool behavior.

### `artifact-links.md` — Artifact Identity and Activation

Target at most 400 words. Retain only:

- admission and participating units;
- `artifact://<artifact_id>` as the sole artifact-link authority;
- dataset ids as tool/service identities, never link authorities;
- one concise producer-to-activation flow across services, Agent Harness, Chatbot, LinkRouter, and ArtifactService;
- inline image versus ordinary link semantics, readiness/failure behavior, and local-path/remote-path safety;
- compatibility fact that legacy `view` hints are accepted but ignored, without the fictional hint taxonomy;
- verification pointers.

Delete database field lists, two duplicate flows, UI progress implementation, speculative renderer behavior, and restated storage/ML rules.

### `ml-task-lifecycle.md` — Cross-Unit ML Work

Target at most 500 words. Retain only:

- admission and participating service, persistence, worker, Agent, and UI units;
- stable task identity and the semantic progression from accepted work through execution to one terminal outcome;
- immutable role-binding input, trained-model aggregate, and apply/evaluation relationship required across units;
- service-owned worker placement, no tool-level worker choice, no automatic failover, and local final artifact authority;
- success finalization and actionable failure/log availability;
- verification pointers.

Delete table names, complete field/enum snapshots, migration fallbacks, exact result-row shapes, application-log paths, runtime directories, and artifact/storage statements already owned elsewhere.

## ADR Design

1. Rewrite `adr/README.md` as a linked table with decision, date, status, relationship, and realization state.
2. Preserve ADR 0001 and 0003 as accepted history.
3. Mark ADR 0002 superseded; add ADR 0006 to record the realized decision that SQLite owns bounded local application state, including conversation content and coordination records, while large/binary data remains filesystem-owned.
4. Preserve ADR 0004's rejection of a Xenix-owned web/backend split. Add ADR 0007 to clarify that outbound LLM-provider APIs and SSH execution adapters are allowed while local services, SQLite, and local artifacts remain product authority. Link ADRs 0004, 0005, and 0007.
5. Preserve ADR 0005's accepted decision and add a short **Implementation Status** section. Mark realization incomplete because fresh-worker dependency closure omits DuckDB and the static worker-bundle marker does not invalidate on source changes. Do not weaken the decision, claim a repair, or modify implementation.
6. Keep new ADRs concise: current divergence, decision, relationship, and durable consequences only; no source walk-through or task narrative.

## Direct Routing Changes

- Update `CONTRIBUTING.md` so service-boundary review enters `docs/20-product-tdd/README.md`, storage review stays with `storage-ownership.md`, and ML lifecycle changes link directly to `ml-task-lifecycle.md`.
- `AGENTS.md`, root `README.md`, and `docs/README.md` already route through the retained PRD/Product TDD indexes and require no semantic change.
- Remove every reference to the three deleted documents.

## Impact Handshake

- **Address and Object**: the three PRD files, five Product TDD entry/contract files, ADR index and affected ADR records, two new ADRs, and direct links in `CONTRIBUTING.md`.
- **State Diff**: migration ledger plus duplicated implementation snapshots -> one evaluable product truth, one global authority entry, three admitted seam contracts, and explicit ADR evolution.
- **Blast Radius**: documentation cold start, product vocabulary, architecture routing, contributor review routes, and later Unit TDD/Deployment cleanup. No runtime, schema, test, packaging, or user-data effect.
- **Invariants**: current behavior is neither expanded nor hidden; accepted ADR history remains inspectable; local product authority and source-data preservation remain; SSH gaps remain unfixed and visible; later `[6,3]` and `[7]` scopes are not preempted.

## Verification

1. All local Markdown paths, fragments, and reference labels resolve; deleted filenames have zero remaining references.
2. `git diff --check` and trailing-whitespace checks pass.
3. PRD contains audience, purpose/pressure, evaluable claims, observable workflows, scope, and business-language anchors; it contains no source paths, tool registry, payload shape, process topology, storage format, or migration history.
4. Each retained Product TDD contract names admission, authority, cross-unit invariant, and verification; no exact schema version, table/field/enum inventory, library choice, tool registry list, or runtime-path snapshot remains.
5. Semantic spot checks match current source/tests for locale support, file intake, tool exposure, attachment registration, dataset/artifact identity, storage version ownership, ML task logs, and remote/local authority.
6. ADR index exposes status and relationships; 0002 points to 0006; 0004/0005/0007 are connected; ADR 0005 visibly records both unfixed gaps.
7. Word budgets: PRD at most 800 words; Product TDD entry plus three contracts at most 1,800 words; ADR corpus at most 1,300 words. Root + protocol + PRD remains at most 1,900 words.
8. No code tests are required for behavior change because there is none. Existing tests are evidence; run only focused checks if a retained claim cannot be confirmed statically.

Apply begins only after Sir approves or adjusts this design.
