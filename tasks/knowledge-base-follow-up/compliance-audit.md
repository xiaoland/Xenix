# Knowledge Base Compliance Audit

## Reading Rules

`Confirmed` means the current source contradicts an applicable contract or accepted
implementation design. `Verification gap` means the implementation may work but the
required delivery boundary has not been exercised. `Rejected` means evidence
disproved the claim. Severity describes authority/data/release impact, not repair
priority by itself.

## Remediation Routing

Findings are assigned through [the slice ledger](slices/README.md). A split finding
keeps one ID with explicit phase sub-scope: for example, Phase A removes unsafe
Knowledge Tool projection while the generic exception-normalization seam in KB-F10
remains for a later cross-cutting Phase. A phase is marked verified only for the
sub-scope named in its own acceptance checks. Slice closure and any accepted residual
are recorded in the slice ledger rather than rewriting historical evidence.

## Current Disposition Inside Slice 01

The Findings table below is explicitly the **historical audit-at-open baseline**. It
is retained without rewriting its original evidence. This disposition table is the
current remediation state and prevents repaired source from being described as if it
were still unchanged.

| Finding | Current disposition | Remaining acceptance |
| --- | --- | --- |
| KB-F01 | Locally verified: one canonical `mode/results[{source, location?, excerpt}]` value; no private Knowledge identity crosses the Tool. | None. |
| KB-F02 | Locally verified: Import stops at canonical-ready; only `KnowledgeDerivationService` publishes Units/FTS/retrieval readiness. | None. |
| KB-F03 | Locally verified: enqueue persists before the service-owned worker runs; UI submits and polls DTOs only. Startup reclaims interrupted attempts. | None. |
| KB-F04 | Locally verified: source Artifact/CAS and canonical bundle may precede publication, while generation + document pointer + terminal import state converge in one SQLite transaction; proven orphans are reclaimed. | None. |
| KB-F05 | Locally verified: canonical envelope records application identity, source/probe/pipeline/OCR provenance, IR/assets hashes, warnings, and validation. | None. |
| KB-F06 | Locally verified: deterministic envelope/content IR bytes have independent SHA-256 identities and verified immutable CAS publication. | None. |
| KB-F07 | Locally verified: fixed v15→v20 edges, static historical fixtures, deterministic duplicate repair, FK/FTS/ORM readability, and fresh bootstrap evidence. | None. |
| KB-F08 | Locally verified: frozen smoke exercises Docling/PDFium, pikepdf, Zstandard canonical round-trip, LanceDB write/search, and Paddle worker resource resolution. | None. |
| KB-F09 | Locally verified: readiness rechecks worker protocol/package, active manifest, model markers, and installed content rather than trusting a stale flag. | None. |
| KB-F10 | Locally verified: Tool schema/path/error handling is registry-wide; unsafe exception or locator content cannot enter canonical ToolResult state. | None. |
| KB-F11 | Locally verified: service DTO state and safe error codes are translated for bilingual Workspace/Queue/Embedding UI; visual evidence is retained. | None. |
| KB-F12 | Locally verified: registry execution validates the advertised JSON Schema, including unknown arguments, types, enum, bounds, and required fields. | None. |
| KB-F13 | Locally verified: production Import→Derivation→Tool composition plus persistence, reopen, provider replay, and Chatbot copy preserves one value. | None. |
| KB-F14 | Implementation locally verified: independent Embedding protocol/settings, exact-cosine Lance generations, deterministic RRF hybrid, truthful `auto`, bounds, and multi-library isolation. Two live cells completed with exact Datasets and integrity, but both failed grounded final-answer wording. | Carried to Slice 02 as `KB2-F01`; not retroactively accepted as passing. |
| KB-F15 | Locally verified: Tool/property descriptions are direct, task-oriented, mode-honest, and contain no index plumbing. | None. |
| KB-F16 | Locally verified: Knowledge methodology is integrated into the three data Skills and analysis assets; no standalone Knowledge Skill remains. | None. |
| KB-F17 | Locally verified: one extensible format registry admits TXT, DOC/DOCX, PDF, JPEG, and PNG and rejects PPT/PPTX; UI copy shares that authority. | None. |

## Slice 02 Current Disposition

Sir authorized Slice 02 on 2026-07-22. The table records current implementation and
acceptance state; multimodal retrieval remains a parked capability rather than a
hidden acceptance requirement.

| Finding | State | Evidence and consequence | Owning phase |
| --- | --- | --- | --- |
| KB2-F01 | Locally verified | The oracle now grades bounded equivalent final wording while still requiring the business rule, inventory-gap/non-positive logic, and exact Dataset. The isolated live cell passed semantic, integrity, persistence, and pytest verdicts. | D |
| KB2-F02 | Locally verified | Each heavy import attempt runs in a spawned process without SQLite authority. The parent validates and publishes; bounded content-free JSONL events are readable from the modeless Queue log viewer. Crash/cancel/package seams are exercised. | A |
| KB2-F03 | Locally verified | The Workspace lists service-owned logical document summaries and owns empty/unavailable states; attempts, Units, hashes, and internal IDs remain absent. | B |
| KB2-F04 | Locally verified | Lookup never creates a vector generation. Compatibility-changing saves confirm only with searchable content; persisted/coalesced tasks expose rebuild state, and corpus changes enqueue only when Embedding and searchable Units exist. | C |
| KB2-F05 | Locally verified | Knowledge Base Settings owns Embedding, OCR, and indexes. Workspace opens the shared dialog through a stable tab key; OCR status/install work stays off the UI thread. | B |
| KB2-F06 | Parked by Sir | Canonical image/OCR preservation remains text-searchable only; visual meaning has no multimodal embedding or Agent evidence path. No multimodal UI or contract was added in this slice. | Separate follow-up |
| KB2-F07 | Locally verified | A window-modal sheet selects real keyword and text-vector projections, shows bounded estimates, disables unavailable vector work, and queues observable rebuild tasks. | C |

## Findings

| ID | Severity | Status | Contract and current evidence | Consequence |
| --- | --- | --- | --- | --- |
| KB-F01 | High | Confirmed | [Unit TDD](../../docs/30-unit-tdd/README.md) and [ADR 0008](../../docs/20-product-tdd/adr/0008-canonical-llm-conversation-boundary.md) require one direct canonical ToolResult. Current code follows that topology, but [the Tool](../../src/xenix/services/agent/knowledge_tool.py) returns query/mode plus citation, document, generation, artifact, and unit identities that do not enable the Agent's next operation. `citation_id` is only a second spelling of `unit_id`. | Wastes provider context and projects storage identity into an Agent contract without behavioral return. A proposed hidden result plane would be a direct contract violation and is rejected. |
| KB-F02 | High | Confirmed | The accepted [Import service design](../knowledge-base/workstreams/01-import/service-design.md) ends at immutable `canonical-ready` and forbids indexing. [KnowledgeImportService](../../src/xenix/services/knowledge_import_service.py) derives units and calls `KnowledgeService.index_document()` during import. | Import and retrieval publication no longer have independent readiness or authority boundaries. |
| KB-F03 | High | Confirmed | [Knowledge Product TDD](../../docs/20-product-tdd/knowledge-base-boundary.md) keeps import service-owned. [Knowledge Workspace](../../src/xenix/ui/knowledge_workspace.py) creates daemon threads; the service is synchronous and creates a row only after acquiring its process-local lock. | Waiting files are absent from the durable queue; process exit can lose work or leave a permanent `running` row. |
| KB-F04 | High | Confirmed | Storage ownership requires services to keep SQLite and owned files consistent. Artifact registration, document/unit/FTS publication, and import success are three separate commits in [KnowledgeImportService](../../src/xenix/services/knowledge_import_service.py). | Lookup may expose a document while its import remains `running`; failures can leave orphan registrations or canonical objects. |
| KB-F05 | High | Confirmed | The [Docling envelope design](../knowledge-base/workstreams/01-import/docling-ir.md) requires document/import/source identity, IR and asset hashes, parser/OCR descriptors, validation, and an immutable generation. The implemented envelope contains only schema version, generation ID, source hash/format, and IR kind. | A frozen blob cannot independently establish its document/import identity, pipeline compatibility, or publication validity. |
| KB-F06 | High | Confirmed | Canonical content should be immutable and content-addressed. [KnowledgeContentStore](../../src/xenix/services/knowledge_content_store.py) addresses canonical bytes by source SHA and returns an existing target without checking the new canonical payload. | Reparse/parser-version changes and a prior orphan blob can make the DB generation disagree with the envelope stored at its path. |
| KB-F07 | High | Confirmed | [Storage guidance](../../src/xenix/services/storage/AGENTS.md) requires a fixed forward edge plus fresh and prior-state upgrade proof. v15→v16 and v16→v17 call current `SQLModel.metadata.create_all()`, and tests provide no real v15/v16 Knowledge fixture with ORM-readability assertions. | Historical migration meaning can drift with future models, and a deployed prior Knowledge schema is not proven upgradeable. |
| KB-F08 | High | Verification gap | [Packaging guidance](../../docs/40-deployment/packaging.md) requires a meaningful packaged exercise for new native/data paths. The ordinary smoke covers startup and existing data/ML paths but does not parse through Docling/PDFium/Zstandard or resolve the packaged Paddle worker resource. | A successful PyInstaller build and generic smoke do not prove Knowledge import works in the frozen application. |
| KB-F09 | Medium | Confirmed | `PaddleOcrDeploymentService.status()` checks worker return code, then trusts `active.json` for `models_ready`; it does not validate returned protocol/package versions or model availability. | A stale manifest or deleted/incompatible model cache can be reported as ready. |
| KB-F10 | High | Confirmed | [Agent local guidance](../../src/xenix/services/agent/AGENTS.md) forbids raw paths in Tool results. `KnowledgeUnitInput.locator` is an unconstrained dictionary that storage and Tool output pass through unchanged. Generic Tool exception normalization also persists `str(exc)`, and an existing test explicitly accepts a private path. | A producer locator or unexpected exception can place a local path into canonical history, provider replay, and Chatbot output. |
| KB-F11 | Medium | Confirmed | [UI guidance](../../src/xenix/ui/AGENTS.md) requires translated user-visible text and separate internal identity. Queue status, `reused/imported`, raw error summaries, OCR phase keys, and Knowledge Tool summaries are not all translated. | Chinese UI can expose English/internal implementation labels and unsafe diagnostic text. |
| KB-F12 | Medium | Confirmed | The Tool schema declares `additionalProperties: false`, but the generic registry does not validate JSON Schema and the Knowledge implementation ignores unknown keys. | Advertised and executable contracts differ; undeclared inputs are silently accepted. |
| KB-F13 | Medium | Verification gap | Generic LLM tests prove direct-value persistence and replay; Knowledge tests invoke a standalone registry, while the live benchmark inspects a final snapshot. There is no offline production-composition test proving Knowledge registration and storage→reload→provider→Chatbot continuity for its actual value. | The exact Knowledge integration depends on a live provider run or generic coverage rather than a deterministic boundary test. |
| KB-F14 | High | Confirmed | The original delivery packet names keyword, semantic, and hybrid retrieval as the target. Current `KnowledgeService` has only jieba-prepared SQLite FTS5 lookup; `knowledge.lookup` always returns `mode_used: "keyword"`. There is no EmbeddingService, vector projection/table, LanceDB dependency, vector query, or rank fusion. | Vector and hybrid retrieval are not supported. Later task/durable wording demoted them to a gated enhancement without a clearly recorded product decision that reconciles the original target. |
| KB-F15 | Medium | Confirmed | The Tool description says only “Find bounded evidence…” and “retrieval strategy is selected by Xenix”; the `query` property has no description. It does not tell the model when user knowledge is relevant, what business knowledge to request, or how to combine it with computed data evidence. | Without activating a Skill, Tool discoverability and correct use depend too heavily on the model inferring product semantics from a generic description. The strategy sentence also describes plumbing rather than helping task completion. |
| KB-F16 | High | Confirmed | Knowledge methodology lives in a separate `xenix-knowledge-retrieval` Skill, while `xenix-data-analysis` does not mention the Knowledge Library or `knowledge.lookup`. Composition gives the Tool common scope, so the separate Skill is not an authorization boundary. | A supporting evidence capability is modeled as an independent user task, fragmenting the data-analysis method and creating unnecessary Skill activation/routing burden. |
| KB-F17 | High | Confirmed | Sir explicitly committed the MVP to TXT, DOC/DOCX, PDF, JPEG, and PNG. The accepted import UI design repeats that set. Current `SUPPORTED_KNOWLEDGE_SUFFIXES` rejects JPEG/PNG and admits PPT/PPTX; the durable Product TDD was changed to describe the shortcut rather than recording a product decision. | Users cannot import the promised image knowledge sources, while implementation scope and documentation advertise an unapproved substitute. Format-routing extensibility is not proven by the central suffix set. |

## Rejected Findings

| ID | Rejected claim | Disproof |
| --- | --- | --- |
| KB-R01 | `python <pip-wheel>/pip ...` cannot execute, so one-click installation always fails. | On 2026-07-21 the exact wheel-internal command returned pip 26.1.2 under CPython, and the isolated Python 3.13 runtime completed real PaddleOCR installation and recognized `雨具补货使用三周平均需求`. Installation robustness still has other findings, but this claim is false. |

## Evidence Interpretation

The rainy-season case imports its rule through production Import and Derivation,
uses a lexical paraphrase, explicitly requests semantic mode, and grades only the
exact final Dataset and grounded terminal answer. With explicit user-controlled
settings, two 2026-07-22 live cells completed: both passed exact-Dataset and all
integrity checks, while `grounded_final_answer` failed. Tool telemetry cannot
substitute for that remaining outcome verdict.
