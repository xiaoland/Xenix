# Knowledge Base Boundary

## Product Topology

Xenix exposes one global Knowledge Library in MVP while retaining an internal
library identity for future multiple-library instances. The Knowledge Workspace is
a secondary window; its Import Queue is modeless. Import, retrieval, and Agent use
remain service-owned rather than UI-owned.

```text
local file
  -> probe / normalize / parse / canonicalize
  -> source CAS + DoclingDocument envelope -> canonical-ready

canonical-ready generation
  -> independent derive / chunk / index publication
  -> retrieval-ready KnowledgeUnits + derived search projections
  -> knowledge.lookup -> bounded source-linked evidence
```

## Import Contract

- Accepted MVP inputs are TXT, DOC/DOCX, PPT/PPTX, and PDF. Markdown, VLM, and
  standalone image import are not implied by parser capabilities.
- `DoclingDocument` JSON is the common content IR. Xenix wraps it in an application
  envelope that owns document identity, format, source hash, canonical location,
  and lifecycle state.
- Legacy DOC/PPT is normalized through LibreOffice before Docling parsing. PDF text
  sufficiency is probed per page; pages without useful native text route through the
  independent OCR service.
- OCR uses a private, one-click-installed local PaddleOCR runtime and model cache.
  OCR runtime ownership is separate from LLM configuration and from import
  orchestration.
- The selected user file is never modified. App-owned source and canonical bytes are
  published through staging plus atomic rename. Same-library SHA-256 content reuses
  the current imported document by default.

## Storage and Retrieval Authority

- SQLite owns bounded business/search metadata: document identity/current state,
  import status, Knowledge Units, source locators, and the FTS5 projection.
- The content-addressed filesystem store owns source bytes and compressed canonical
  envelopes. `ArtifactService` registers user-openable app-owned files; raw paths do
  not become Agent-facing identity.
- A Knowledge Unit is the current retrievable authority for a bounded passage. FTS
  tokens, ranking values, future embeddings, and vector indexes are derived access
  paths and may not become a second content authority.
- For retrieval-ready documents, keyword lookup is the minimum baseline. Semantic
  and hybrid lookup are compatible derived projections; absence of embeddings must
  not disable an available keyword projection or cause an explicit semantic/hybrid
  request to fall back silently. Canonical-ready alone does not imply retrieval-ready.

## Agent Contract

`knowledge.lookup` is the sole MVP Agent operation. It accepts a business-language
query and optional `auto`, `keyword`, `semantic`, or `hybrid` mode; result count and
document scope remain service-owned. Until a requested derived projection is ready,
the Tool returns typed unavailability rather than silently substituting keyword
retrieval. A success reports the resolved mode and bounded
`source`/optional-human-location/`excerpt` results. It never exposes query echo,
scores, document/unit/generation/artifact/citation identities, raw locator objects,
filesystem paths, credentials, index internals, or entire documents.

Knowledge retrieval methodology belongs to the data-analysis Skill, with small local
rules in preprocessing and modeling. The Tool remains commonly advertised; Skill
activation is methodology, not authorization, and does not grant a new tool scope.

## Verification Anchors

- Import formats, deduplication, canonical CAS, PDF routing, and OCR adaptation:
  `tests/test_knowledge_import_service.py` and `tests/test_paddle_ocr_service.py`.
- SQLite/FTS retrieval and tool result shape:
  `tests/test_knowledge_retrieval.py` and `tests/test_knowledge_lookup_tool.py`.
- Workspace and queue composition: `tests/test_knowledge_import_ui.py`.
- Rule-plus-data Agent behavior:
  `benchmarks/agent_harness/test_rainy_season_restock.py`.
- Windows delivery: `pdm run package` followed by `pdm run smoke-package`.

Encrypted-document password flow, resource-limit policy, refresh/removal UX, and
package-size optimization are not established by this contract until their own
executable evidence exists. Semantic/vector execution remains unavailable until its
derived projection has its own delivery evidence; the Agent contract must report
that state honestly.
