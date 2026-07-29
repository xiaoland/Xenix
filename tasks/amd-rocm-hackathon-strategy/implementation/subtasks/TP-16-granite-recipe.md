# TP-16 — Granite/vLLM Chat Recipe

## Outcome

Turn the verified Granite 3.1 8B/vLLM ROCm combination into one immutable product
component recipe with authenticated launch, exact acquisition, and capability
self-test.

## Owned Mutation

- add the Granite component manifest under
  `src/xenix/resources/amd/manifests/components/`;
- add the shared vLLM component launcher/self-test helper under
  `src/xenix/services/amd/components/`;
- add Granite/vLLM recipe tests.

TP-17 consumes the shared vLLM helper and may not redesign it concurrently. TP-19
owns final profile-index aggregation.

## Recipe

- exact vLLM ROCm 7.2.1 build, framework/runtime/plugin allow-list, model revision,
  artifact hashes/licenses/sources, isolated cache/config roots, launch arguments,
  resource requirements, and phase deadlines;
- loopback-only listener and runtime-generated authentication;
- protected authentication handoff outside command-line/persisted summaries, with
  unauthenticated rejection as an admission test;
- process/start/generation/incarnation attestation;
- readiness waits for model service, not merely an open port;
- OpenAI-compatible non-stream, SSE usage, automatic Tool Call, follow-up, and
  ROCm workload/device proof.

No endpoint, token, PID, or live health is added to the manifest.

## Acceptance

- cold exact acquisition and hash verification are reproducible;
- unauthenticated request is rejected;
- Chat/stream/Tool contracts pass through the ordinary product client;
- endpoint-open-before-ready and slow-first-compile phases are diagnosed correctly;
- ambient plugins/caches and CPU/API fallback are absent;
- no vLLM/ROCm/model runtime becomes a desktop base dependency;
- server/process cleanup is exact-identity guarded.

## Verification

- focused manifest/launcher/self-test tests;
- real-cell TP-19 run;
- `pdm run check`.
