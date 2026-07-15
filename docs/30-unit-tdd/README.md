# LLM Conversation / Agent Harness Unit Design

## Admission

The [LLM conversation boundary](../20-product-tdd/llm-conversation-boundary.md)
is the sole cross-unit authority for topology, ownership, and primary
sequences. This document records only local seams that are expensive to
reconstruct while changing the LLM Conversation / Harness implementation; it
does not restate or supersede that contract.

Exact records, event shapes, Tool schemas, fields, registries, and method
signatures remain source and test truth. UI rendering contracts remain in typed
Chatbot events, UI code, and integration tests.

## Local Seams

- **Submission:** Harness validates UI input, coordinates source import through
  DatasetService, then asks `LLMConversationService` to append the User
  Message. Dataset blocks are canonical context; source attachments are
  presentation-only data derived later from Dataset provenance.
- **Sampling:** Harness owns the live loop and converts LLM Conversation live
  notifications into Thinking/activity/connection Events. Its cancellation maps
  are callback aids keyed by a pending Message identity and must be cleared on
  finalization, cancellation, or generator abandonment; they are never another
  execution-state store.
- **Pending completion:** LLMConversationService keeps private pending-exchange
  staging and performs Tool invocation/finalization. Harness must consume the
  resulting snapshot and decide only whether the new final frontier needs the
  next sample.
- **Projection:** First run the pure structural snapshot projection. Then, and
  only then, enrich Dataset blocks through DatasetService's read-only source
  presentation resolver. A failed resolver is a soft omission, not a Thread
  open failure. The Chatbot renderer determines displayability: reasoning-only
  Assistant events allocate no Bubble. The derived source-attachment
  presentation is neither a canonical block nor provider context; its
  originating DatasetBlock remains both.
- **Deletion and usage:** Route deletion through the LLM Conversation service
  so its writer gate and repository dependency order remain intact. Project
  usage only from LLM Conversation's observability-derived overview after the
  matching terminal Assistant event.

## Current Non-assumptions

The current Conversation/Harness lifecycle does not rely on completion-guard or
step-budget pause/resume behavior. Their product disposition is outside this
document; do not use their configuration or UI remnants as a lifecycle contract
without a separately approved implementation and verification.

## Change Guidance

Preserve the public command/snapshot seam. A new provider, Tool, stream path,
cancellation path, or source presentation must still converge on the canonical
snapshot specified by Product TDD, and must not make Chatbot UI infer protocol
state from storage or raw Tool payloads.

Read the nearest `src/xenix/services/agent/AGENTS.md` before changing this
loop. Source and tests decide exact method/field behavior; this document only
guards local ownership and sequence traps.

## Verification

- Conversation lifecycle, typed blocks, titles, retry, and usage:
  `tests/test_llm_conversation_lifecycle.py`, `tests/test_llm_message_blocks.py`,
  `tests/test_llm_conversation_titles.py`, `tests/test_llm_service_retry.py`, and
  `tests/test_llm_usage_observability.py`.
- Harness coordination, projection, source enrichment, and UI convergence:
  `tests/test_agent_harness_foundation.py`,
  `tests/test_agent_harness_first_slice.py`,
  `tests/test_agent_harness_streaming.py`,
  `tests/test_dataset_service_source_presentation.py`, and `tests/test_main.py`.
- Deletion, migration, and bootstrap: `tests/test_repositories.py`,
  `tests/test_migrations.py`, and `tests/test_storage_bootstrap.py`.
