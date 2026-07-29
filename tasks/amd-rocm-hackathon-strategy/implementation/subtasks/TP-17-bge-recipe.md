# TP-17 — BGE-M3/vLLM Embedding Recipe

## Outcome

Turn the verified BGE-M3/vLLM ROCm combination into an immutable authenticated
Embedding component recipe that shares only the already defined vLLM launcher
contract.

## Owned Mutation

- add the BGE-M3 component manifest under
  `src/xenix/resources/amd/manifests/components/`;
- add only BGE-specific self-test/recipe code and tests.

Do not edit TP-16's shared launcher contract or the central profile index.

## Recipe

- exact vLLM/runtime/model/tokenizer refs, hashes/licenses/sources, isolated roots,
  launch/capacity/deadline settings, loopback authentication, and attestation;
- protected authentication handoff outside command-line/persisted summaries and
  required unauthenticated rejection;
- OpenAI-compatible Embedding request with `dimensions` omitted;
- response indexes, finite/stable vectors, and observed exact 1024 dimensions;
- model/tokenizer/generation identity exported for TP-05 fingerprinting;
- repeated real workload correlated with ROCm device evidence.

## Acceptance

- exact cold acquisition and launch are reproducible;
- unknown model and unauthenticated access fail;
- sending the forbidden BGE `dimensions` field is not part of product traffic;
- stable 1024-dimensional results pass;
- no CPU/API fallback, ambient plugin, endpoint persistence, or cross-generation
  fingerprint reuse;
- coexists with the selected Granite and RapidOCR recipes within declared capacity.
- its runtime remains a manifest acquisition rather than a desktop base dependency.

## Verification

- focused recipe/self-test tests;
- real-cell TP-19 coexistence run;
- `pdm run check`.
