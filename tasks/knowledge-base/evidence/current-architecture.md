# Current Architecture Evidence

This is task-local evidence, not a durable contract owner. It records the facts used
to form the current proposal on 2026-07-14.

## Storage and Artifact Facts

- `pyproject.toml` already declares `sqlmodel`, and storage uses SQLModel/
  SQLAlchemy; an ORM introduction is unnecessary.
- `docs/20-product-tdd/storage-ownership.md` assigns bounded app state to SQLite and
  large/user-openable bytes to the filesystem.
- `src/xenix/services/artifact_service.py` registers an existing absolute path,
  resolves `artifact://` URIs, and activates files. `ArtifactRow` is defined in
  `src/xenix/services/storage/models.py`.
- `src/xenix/services/storage/layout.py` centralizes existing artifact roots;
  Knowledge Base needs an analogous dedicated root rather than UI-made paths.
- `src/xenix/services/storage/migrations.py` currently has a forward migration chain
  and schema version 14. Storage guidance requires a new forward edge plus fresh and
  upgrade proof.

## Agent and Attachment Facts

- `src/xenix/services/agent/tools.py` owns the registered provider-facing tool list
  and validates/executes calls with `ToolExecutionContext`.
- `src/xenix/services/agent/harness_service.py` materializes source attachments by
  resolving their artifact then passing them to `DatasetService`; that flow supports
  tabular formats, not PDF/DOCX document ingestion.
- `src/xenix/services/agent/conversation_store.py` persists canonical tool results
  and rebuilds provider replay from them. Agent guidance forbids raw local paths or
  unbounded evidence in provider schemas/results.
- Current LLM provider DTOs are text/tool oriented; they do not carry a general
  multimodal document/image message contract. The initial Knowledge Base design
  therefore does not depend on provider multimodal transport.

## Missing Capability Facts

- The source tree and dependencies currently contain no general document parser,
  OCR, VLM, embedding service, vector index, document/chunk model, or knowledge
  import lifecycle.
- `src/xenix/services/ml/models/text_analysis.py` contains a TF-IDF similarity
  analyzer over tokenized tabular data. It is not a persistent document retrieval
  index and should not be repurposed as one.

## Relevant Guardrails

- `docs/20-product-tdd/artifact-links.md` requires tool results to expose stable
  identities rather than prebuilt URIs or local paths; presentation constructs links.
- `src/xenix/services/agent/AGENTS.md` requires one canonical tool result and
  prohibits credentials, raw paths, and unbounded evidence at the provider boundary.
- `src/xenix/services/storage/AGENTS.md` requires forward migrations and ORM
  readability proof.

## Nearby Boundary Debt (Out of This Scope)

Some ML task and Agent/UI paths currently expose absolute artifact paths or use
`MLTaskArtifactRow.id` as if it were a generic Artifact ID. This task should not
expand to repair that unrelated work, but its designs/tests must not repeat the
pattern. A separate untracked task packet, `tasks/llm-service-agent-harness-boundary/`,
is already addressing the wider boundary discussion.
