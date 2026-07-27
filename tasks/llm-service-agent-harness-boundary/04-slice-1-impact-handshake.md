# Superseded Draft — Adapter Integrity and Terminal Convergence

## Status

Do not approve or implement this draft as written. The adapter-correctness evidence remains valid, but the bundled terminal-convergence change assumes the old Harness-owned persistence shape. Refined Option A now requires a new narrow adapter handshake and a separate canonical-state migration handshake. This file remains only to preserve the original evidence and rejected state diff.

## Address and Object

- `src/xenix/services/llm/providers.py`: normalize malformed provider response/stream shapes and reject provider function calls that were not exposed in the request.
- `src/xenix/services/agent/conversation_store.py`: add one atomic failure-finalization operation for an existing run and its interaction turn.
- `src/xenix/services/agent/harness_service.py`: use that operation from normal and streaming failure paths.
- `tests/test_llm_service_retry.py`: prove adapter normalization and configured retry behavior.
- `tests/test_agent_harness_streaming.py`: prove actual LLM-to-Harness failure convergence and failed-turn projection.

## State Diff

| From | To |
| --- | --- |
| An unexposed provider function name is silently skipped by the OpenAI-compatible adapter; Harness sees apparent zero-tool completion. | The adapter rejects it as a structured, retryable invalid provider response. It can never invoke a tool or become a synthetic zero-tool completion. |
| Empty/malformed provider response structures leak incidental exceptions such as `IndexError`; stream chunk shape failures are not normalized. | Adapter failures use stable domain `ValidationError` details and configured retry classification, with no raw exception shape as the public contract. |
| Provider/tool failure stores `Run=FAILED` but can leave `Turn=OPEN`. | Superseded target. The selected architecture requires one LLM-owned atomic terminal interaction transition; its exact retained-Turn/no-Turn shape is not approved yet. |

## Blast Radius

- Provider response parsing and retry telemetry.
- Historical proposed blast radius: Harness normal and streaming exception handling, persisted provider-request/run/turn state, usage/connection event projection, and error rendering.
- This is no longer a bounded slice because the selected owner changed. The replacement handshake must state whether it includes canonical-state migration, telemetry split, and retained-Turn/no-Turn behavior.

## Invariants

- Harness remains the tool-authorization owner; adapter validation cannot silently weaken its fail-closed rule.
- The replacement slice must use the selected LLM-owned canonical-state boundary; it must not preserve Harness direct persistence merely for convenience.
- A provider request is still recorded before provider side effects; one canonical tool result remains the replay source.
- Observability loss, rotation, delay, duplication, and exporter failure cannot affect thread reload, pause/resume, tool replay, or terminal state.
- The exact retained-Turn/no-Turn status model and migration are part of the replacement handshake.

## Verification

1. Adapter-level tests: empty choices, malformed stream chunk, and unexposed provider function each become domain errors with the intended retry classification.
2. The replacement integration test must prove retry telemetry never becomes a recovery input and never permits an unexposed tool.
3. The replacement terminal-state test must prove the selected LLM interaction state is terminal and a reloaded snapshot is correct even when observability data is absent.
4. Regression command:

   ```powershell
   pdm run test tests/test_llm_service_retry.py tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py
   ```

5. `git diff --check` passes.

## Non-goals

- Decide the LLM interaction-state migration or `Turn` model.
- Change the buffered-text streaming/retry product contract.
- Bound raw provider payload retention.
- Merge the normal and streaming causal loops.
