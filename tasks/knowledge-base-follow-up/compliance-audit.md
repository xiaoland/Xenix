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
sub-scope named in its own acceptance checks; Slice 01 stays open until all rows and
the global review converge.

## Current Disposition Inside Slice 01

The Findings table below preserves the audit-at-open evidence. This table is the
current remediation state and prevents repaired source from being described as if it
were still unchanged.

| Finding | Current disposition | Remaining phase |
| --- | --- | --- |
| KB-F01 | Phase A verified: the one canonical value is now `mode/results[{source, location?, excerpt}]`; no private Knowledge identity crosses the Tool. | Final Slice 01 cross-review. |
| KB-F02 | Open: Import still crosses canonical-ready into retrieval derivation. | Phase E. |
| KB-F03 | Open: Import execution/queue ownership remains in UI daemon threads. | Phase E. |
| KB-F04 | Open: Artifact, document/index publication, and import status do not converge atomically. | Phase E. |
| KB-F05 | Open: canonical envelope is incomplete. | Phase C. |
| KB-F06 | Open: canonical content addressing is based on source hash rather than payload identity. | Phase C. |
| KB-F07 | Open: historical Knowledge migration edges and real prior fixtures remain inadequate. | Phase D. |
| KB-F08 | Open verification gap: packaged Knowledge native/data paths lack a meaningful exercise. | Phase F, then Phase G. |
| KB-F09 | Open: OCR readiness trusts insufficient manifest/process evidence. | Phase F. |
| KB-F10 | Partially verified: Knowledge source/locator/error projection is allowlisted and path-safe. | Generic Tool exception normalization and other cross-cutting path seams remain Phase F. |
| KB-F11 | Open: dynamic Knowledge UI/tool presentation state is not fully translated or presentation-safe. | Phase F. |
| KB-F12 | Partially verified: `knowledge.lookup` rejects every undeclared argument at execution. | Generic registry-wide JSON Schema enforcement remains Phase F. |
| KB-F13 | Verified: production composition registration plus new and historical values are proven across persistence, reopen, provider replay, and Chatbot copy. | None. |
| KB-F14 | Interface verified: mode selection is explicit and unavailable modes cannot fake keyword success. | Semantic/vector and hybrid execution remain Phase B. |
| KB-F15 | Phase A verified: Tool and property descriptions explain business purpose, evidence use, and exact mode semantics without index plumbing. | Revisit during Phase B readiness changes. |
| KB-F16 | Verified: methodology is integrated into the three data Skills and their analysis assets; the standalone Knowledge Skill is removed. | None. |

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

## Rejected Findings

| ID | Rejected claim | Disproof |
| --- | --- | --- |
| KB-R01 | `python <pip-wheel>/pip ...` cannot execute, so one-click installation always fails. | On 2026-07-21 the exact wheel-internal command returned pip 26.1.2 under CPython, and the isolated Python 3.13 runtime completed real PaddleOCR installation and recognized `雨具补货使用三周平均需求`. Installation robustness still has other findings, but this claim is false. |

## Evidence Interpretation

The successful rainy-season benchmark remains valid evidence that the model can use
the current Tool to retrieve a rule and create the exact derived Dataset. It does not
prove that the Tool payload is minimal, imports are correctly owned, publication is
atomic, migrations are stable, or the packaged application exercises the same path.
