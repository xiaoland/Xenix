# TP-13 — AMD Embedding Adapter

## Outcome

Implement the Embedding-owned operation port for a managed exact generation while
preserving resource-free `freeze()` and atomic vector publication behavior.

## Owned Mutation

- add `src/xenix/services/amd/adapters/embedding.py`;
- add `tests/test_amd_embedding_adapter.py`.

Do not modify deployment, settings, Knowledge index policy, placement, or
composition.

## Behavior

- factory/profile resolution is resource-free;
- `embed_texts()` acquires one exact-generation permit and binding across all
  batches;
- response dimension and manifest/model/tokenizer identity agree with TP-05/10;
- possible-dispatch disconnect returns no partial result and performs no semantic
  retry or generation switch;
- next operation may rematerialize a new binding/incarnation.

## Acceptance

- one multi-batch call enters/exits one permit;
- batch-2 server-received disconnect returns no vectors and leaks no permit;
- BGE request omits `dimensions`; 1024 response is validated;
- runtime port/incarnation changes do not change vector fingerprint;
- two installations remain independently addressable;
- retired/unverified/missing generation fails typed.

## Verification

- `pdm run pytest --direct tests/test_amd_embedding_adapter.py`;
- focused Embedding/index tests;
- `pdm run check`.
