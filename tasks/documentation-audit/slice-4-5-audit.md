# Slice `[4,5]` Audit — PRD, ADR, Product TDD

## Status and Scope

- Phase: Confirm. This file records evidence, not a repair design.
- Audited: `docs/10-prd/`, `docs/20-product-tdd/adr/`, and the remaining `docs/20-product-tdd/` corpus.
- Evidence only: source, configuration, tests, Unit TDD, and Deployment docs.
- Excluded: durable mutation, source fixes, Unit TDD/local instruction repair, and Deployment repair.
- Priority: P0 is a direct falsehood or unresolved authority conflict that can misdirect implementation; P1 is material drift or owner ambiguity; P2 is retrieval cost, duplication, or historical residue.
- Confirmed calibration: the target users are non-technical business users, primarily business and marketing staff; current source and tests, not dormant or aspirational documentation, define implemented behavior for this cleanup.

## Product Truth and Vocabulary

### P0

1. **`analysis.lambda` is presented as a current product capability but is intentionally absent from the Agent registry.** `docs/10-prd/product-scope.md:21,64` claims it; `src/xenix/services/agent/tools.py:129-136` does not register it, and `tests/test_analysis_lambda.py:233-238` protects that absence.
2. **The claimed bounded Markdown profiling capability is not exposed.** `product-scope.md:19,62` presents it as a current Agent/tool behavior; `tests/test_analysis_profile.py:145-150,212-220` proves that neither `analysis.profile` nor `data.peek` is exposed and `data.query` has no profile controls. The Agent can compose queries, but that is not the specialized capability described.
3. **The glossary's Turn termination rule is false.** `docs/10-prd/glossary.md:13` says a zero-tool response ends the Turn; `src/xenix/services/agent/harness_service.py:764-774` can continue through the completion guard, covered by `tests/test_agent_harness_streaming.py:1503-1570`.
4. **“Native app” and “same process” conflict with spawned workers.** `glossary.md:7` and `product-scope.md:48` describe a single local process; preprocessing and ML execution spawn child processes in `src/xenix/services/preprocessing_worker.py:39-41` and `src/xenix/services/ml/execution.py:27-37`.

### P1

5. **“Model” has two unresolved meanings.** `product-scope.md:23` and `glossary.md:22` use it for a reusable ML analyzer, while `product-scope.md:30,52` and current UI copy use it for an LLM provider model. No canonical vocabulary distinguishes them.
6. **The target user is inconsistent.** `product-scope.md:9` says teachers and students; root/product prompts and tests describe non-technical business users. Sir confirmed business and marketing staff as the primary audience. `product-scope.md:3-5` records document history rather than a clear product purpose and audience.
7. **Stable locale behavior has no product owner.** English/Simplified Chinese selection, persistence, and fallback exist in `src/xenix/ui/settings_dialog.py:342-343,386-407` and `tests/test_i18n.py:54-71`, but no PRD claim owns the behavior.
8. **PRD and glossary contain implementation-owned facts.** Source paths, provider payload persistence, Parquet, tool schemas, and worker placement appear in `product-scope.md:48-58,64` and `glossary.md:10-18,21-30`. The Turn and process drift above demonstrate the maintenance failure.
9. **The intake-format list is another implementation snapshot.** `product-scope.md:14` says CSV/XLSX, while the Composer currently accepts CSV/XLS/XLSX in `src/xenix/ui/main_window.py:418`. A stable product claim can describe supported tabular files without duplicating the extension registry.

### P2

- “Retained Concepts” and “Design Implications” repeat Chatbot, tool, and worker claims inside `product-scope.md`.
- Milestone/history labels such as retained, removed, first-slice, compatibility, and legacy work item are mixed into current product truth.
- `glossary.md` packs business meaning and implementation contracts into long compound lines, reducing scanability and owner clarity.

## Accepted Decisions

### P0 — Reality defects exposed by the audit

1. **Fresh SSH workers do not receive all runtime dependencies.** ADR 0005 says setup installs and validates remote dependencies (`docs/20-product-tdd/adr/0005-ssh-ml-worker-pool.md:20-21`). `pyproject.toml:16` requires `duckdb`; the remote worker import chain reaches `src/xenix/services/ml/dataset_loader.py:5`, but `src/xenix/services/ml/ssh_worker_setup.py:21-41,113-130` omits it from remote validation and installation. This is an implementation defect, not a reason to weaken the ADR.
2. **The remote worker bundle marker is not versioned by content.** ADR 0005 promises a versioned bundle. `src/xenix/services/ml/execution.py:18` fixes `WORKER_BUNDLE_VERSION` to `source-v1`, while `execution.py:260-270` skips upload whenever that marker exists. Subsequent worker-source changes can therefore leave a stale remote bundle. This also requires a Reality slice.

### P1 — Decision scope requiring confirmation

3. **ADR 0002's SQLite boundary is narrower than current durable state.** `0002-sqlite-for-local-state.md:12` limits SQLite to metadata and coordination; `src/xenix/services/storage/models.py:294-348` persists Thread system prompts/model selection and Message content/provider payload. The accepted decision must either evolve explicitly or identify an implementation violation.
4. **ADR 0004's remote-API prohibition is ambiguous against current LLM providers.** `0004-native-architecture-separate-from-web.md:19` requires a new ADR before remote APIs return; `runtime-boundaries.md:126-132` documents OpenAI-compatible, DeepSeek, and AIMock HTTP. The likely intended ban is an Xenix-owned remote backend, but the ADR does not say that.

### P2

- The ADR index is a bare filename list without links, dates, status, or supersession signals.
- ADRs 0001, 0004, and 0005 mention issues or other ADRs without navigable provenance.
- ADRs 0001, 0003, and most of 0005 otherwise match current implementation.

## Cross-Unit Technical Contracts

### P0

1. **The schema-version snapshot is stale.** `docs/20-product-tdd/storage-ownership.md:19` says version 12; `src/xenix/services/storage/migrations.py:12` and tests define 14. Product TDD is competing with the source owner.
2. **Composer attachment ownership is contradictory.** `storage-ownership.md:62` says attachments enter through dataset registration, while `runtime-boundaries.md:80` says source artifacts come first. `src/xenix/ui/main_window.py:391-410` registers `ArtifactKind.FILE` through ArtifactService before Harness import; tests agree with the latter path.
3. **The worker-placement claim is too broad and false for current tools.** `runtime-boundaries.md:78` dispatches large cleaning, tokenization, and transform-style execution to a preprocessing worker. `src/xenix/services/agent/tools.py:1052-1073` tokenizes synchronously; `tools.py:827-838` performs integration and `pd.concat` in process. Only later registration/export paths use the worker.

### P1

4. **Artifact `view` hints describe a renderer contract that does not exist.** `artifact-links.md:15` says Chatbot normalizes hints away, yet `artifact-links.md:76-87` assigns durable meanings and fallback behavior. `src/xenix/ui/markdown_renderer.py:17-29` always strips `view`; no renderer consumes those meanings.
5. **Artifact path authority is scoped inconsistently.** `artifact-links.md:31,41` says UI does not resolve/open local paths directly; `runtime-boundaries.md:40` allows opening a service-resolved path, and `src/xenix/ui/tool_call_detail_view.py:203` does so. The documents fail to distinguish artifact-URI activation from a trusted service result.
6. **Dataset export is called both lazy and eager.** `storage-ownership.md:39` says lazy; `runtime-boundaries.md:78,81` requires eager materialization before return; `src/xenix/services/dataset_export_service.py:37` writes and registers synchronously.
7. **The ML logging contract is false.** `ml-task-lifecycle.md:88-98` says each task writes user logs to the application log and per-task logs are future work. `src/xenix/services/storage/layout.py:58-59`, `src/xenix/services/ml/worker_pool.py:133-134`, `src/xenix/services/ml/execution.py:352-353`, and `src/xenix/services/ml_task_service.py:286-293` already write/read `artifacts/ml-tasks/<id>/logs.jsonl`.
8. **The application log is not append-only.** The contract says it is; `src/xenix/logging.py:30` uses `RotatingFileHandler`.
9. **The required ML result fields do not match current contracts.** `ml-task-lifecycle.md:102-108` requires result kind, artifact kind, absolute path, preview kind, and readiness. `src/xenix/services/storage/models.py:274-291` and `src/xenix/services/ml/contracts.py:136-182` do not define that combined shape. The document does not distinguish a conceptual cross-unit requirement from a concrete payload or row contract.

### P2

- `runtime-boundaries.md` is a 2,844-word second snapshot of Agent Harness, tool schemas, persistence, follow-up behavior, ML, storage, and artifact rules already owned elsewhere.
- Other Product TDD files retain fast-changing field lists, table/migration names, enum lists, and library choices. The stale schema version proves this projection is not sustainable.
- `ml-task-lifecycle.md` mixes current contracts with migration history and retired fallbacks; `storage-ownership.md` gives an incomplete runtime layout.
- The Product TDD index contains no concern routing or admission rule, and its filenames are not links.
- Artifact and storage flows repeat the same authority sequence across multiple files.

## Corpus-Level Diagnosis

1. **Owner overlap is systematic.** Product scope duplicates runtime boundaries; glossary duplicates runtime, storage, and ML contracts; runtime boundaries duplicates Unit TDD Agent Harness plus the narrower artifact/storage/ML documents.
2. **Current truth and historical evidence are mixed.** Milestone language, retired fallbacks, schema snapshots, and migration details remain in live contracts without status markers.
3. **Retrieval cost is disproportionate.** The Product TDD corpus exceeds 5,800 words before PRD and ADRs; its largest file alone is 2,844 words and contains very long compound lines. A reader cannot know which duplicate is authoritative.

## SVC Conformance and Structural Audit

### Baseline

The repaired SVC kernel requires selective memory: source, configuration, schemas, tests, assertions, and runtime checks own mechanically enforceable truth; PRD owns product what/why; Product TDD admits only cross-unit authority, topology, or compatibility contracts that another unit must rely on. PRD and Product TDD start as one document and split only for distinct consumers or cadence. Every durable claim must have one owner, and duplication is removed before compression (`F:/CODING/svc/src/index.md:3-9,45-64`; `src/sections/prd.md`; `src/sections/product-tdd.md`; `src/sections/working-protocol.md:75-80`).

### PRD Misalignment

1. **The kernel entry is a router, not current product truth.** `docs/10-prd/README.md` does not state the product purpose, beneficiary, current pressure, claims, observable success, workflows, rules, or scope. Cold start requires opening two more files.
2. **The structure is migration-led rather than product-led.** `product-scope.md` is organized as Retained, Removed, and Design Implications. It does not preserve the SVC reasoning direction `drivers -> product behavior and claims -> derived domain structure`, and material claims have no rationale, success dimension, or expected evidence.
3. **The glossary is mainly implementation ontology.** Agent Harness records, provider requests, Parquet, persistence representation, model taxonomy, worker placement, and remote cache state dominate `glossary.md:10-31`. These belong to Unit/Product TDD, source/tests, Deployment, or migration history. True business language and the LLM-model versus trained-analyzer distinction are missing.
4. **The split is not justified at its entry.** A separate business glossary may have a real consumer, but the current README states neither consumer nor cadence. `product-scope.md` changed with `runtime-boundaries.md` in 18 of its 20 commits, demonstrating implementation-shadow cadence rather than independent product cadence.

### Product TDD Misalignment

1. **Admission is asserted, not demonstrated.** The README and four main documents do not identify dependent units, failure if the contract is lost, why source/schema/tests are insufficient, or concrete verification. The README is a bare filename list and gives no concern routing.
2. **All four documents contain plausible cross-unit seams, but their current boundaries are not clean.** Runtime topology, storage authority, artifact activation, and ML lifecycle each have real participating units. Audit therefore does not decide to merge or retain them; Design must test every retained section and split against SVC admission.
3. **`runtime-boundaries.md` is the primary god document.** Only the topology and dependency skeleton at lines 7-64 is clearly in scope. Lines 65-91 duplicate tool/service schemas and numeric limits; 96-145 duplicate Agent Harness Unit TDD; 146-161 duplicate ML/worker owners; 169-183 duplicate contribution and test policy.
4. **Mechanically owned facts are copied throughout the layer.** Schema versions, table/field/enum representations, exact tool inventory and JSON shapes, numerical render limits, library choices, runtime paths, and migration names belong to code, schema, tests, configuration, or Deployment. The version, placement, and logging drift are direct evidence that these projections fail.
5. **Verification and realization links are absent.** Product TDD does not connect admitted contracts to PRD claims or to the tests/schemas that enforce them. Its documents also do not link one another at overlap points, so readers cannot identify the canonical claim owner.
6. **The existing Unit TDD entry misroutes cross-unit truth.** `docs/30-unit-tdd/README.md:5` assigns cross-submodule constraints and architectural boundaries to Unit TDD, conflicting with SVC. This is recorded as an incoming dependency for slice `[6,3]`, not repaired here.

### Repeated Claim Clusters

| Claim cluster | Parallel owners now | Structural failure |
| --- | --- | --- |
| Artifact identity, export, activation, and preview | PRD, glossary, runtime, storage, artifact links, ML lifecycle, both Unit TDDs | One flow is restated with different scope and incompatible `view`/path claims |
| Agent Harness records, provider loop, tools, and results | PRD, glossary, runtime, storage, Agent Harness Unit TDD, source/tests | Product and cross-unit docs copy a unit-internal state machine and registry |
| SSH worker placement, authority, staging, and failure | PRD, glossary, ADR 0005, runtime, storage, ML lifecycle, Deployment, local instructions | Decision history, current contract, operations, and mechanics are interleaved |
| Dataset/storage authority and lineage | PRD, glossary, runtime, storage, artifact links, ML lifecycle, Agent Harness Unit TDD | Identity and medium rules have several competing canonical statements |
| Tool inventory, schemas, limits, and placement | PRD, runtime, Agent Harness Unit TDD, source/tests | Fast-changing mechanical truth is maintained three or more times |

### Split and Retrieval Evidence

- Current size: PRD 3 files / 1,460 words; Product TDD main layer 5 files / 5,851 words; ADR index plus records 6 files / 846 words.
- Co-change history contradicts distinct cadence: product scope/runtime share 18 commits; runtime/storage 14; storage/ML lifecycle 9; storage/artifact links 6.
- Outside their indexes, only `CONTRIBUTING.md` directly routes to runtime and storage. Artifact and ML lifecycle have real semantic consumers in code, but the documentation topology does not declare them.
- `runtime-boundaries.md` alone is 2,844 words and has 40 historical commits, making it the default dumping ground for every implementation slice.

### ADR Alignment

- ADRs generally pass the durable decision-and-rationale admission test, and their central location remains navigable beside the Product TDD owner.
- SVC requires accepted history to be superseded rather than rewritten. ADR 0002/0004 drift must therefore be handled by explicit clarification, amendment, or supersession during Design, not silent wording calibration.
- ADR 0005 adds an exception to ADR 0004 but does not expose that relationship in the index. The index omits links, dates, status, and supersession state.
- Current implementation mechanics and the two SSH defects must not be copied into ADR prose as another snapshot.

## Confirmation State

- Confirmed: the audience is non-technical business users, primarily business and marketing staff.
- Confirmed: current code/tests calibrate implemented behavior. `analysis.lambda` and a specialized profiling tool are not current product capabilities; dormant service code is not a product promise.
- Awaiting confirmation: the expanded redundancy, owner, admission, and structure problem set above is complete enough to enter Design.
- Awaiting Design decision: ADR 0002 and 0004 require clarification/amendment/supersession rather than rewriting accepted history.
- Awaiting scope decision: whether the two SSH-worker defects become a separate Diagnose/Execute slice before durable documentation repair.

No repair plan is implied until Sir confirms or adjusts this problem set.
