# TP-12 — AMD Chat Adapter

## Outcome

Implement the LLM-owned operation port for a managed exact generation using the
private AMD runtime directory, while reusing the ordinary OpenAI-compatible wire
adapter.

## Owned Mutation

- add `src/xenix/services/amd/adapters/llm.py`;
- add `tests/test_amd_llm_adapter.py`.

Do not modify the deployment facade, settings schema, SSH driver, or `app.py`.

## Behavior

- resolve exact `(installation, component generation)` only;
- acquire one TP-09 permit and one runtime-incarnation binding for the complete
  outer complete/stream operation;
- provide a redacted ordinary OpenAI-compatible client to TP-04;
- allow retry only while TP-04 proves no dispatch;
- never switch generation/incarnation inside a semantic operation;
- release in `finally`, including stream close/abandon.

## Acceptance

- complete, SSE usage, Tool Call, follow-up, retry-before-dispatch, disconnect
  after dispatch, and abandoned stream cases pass;
- two simultaneous installations resolve their own sessions;
- retired/unverified/missing generation fails typed and closed;
- errors/settings/logs expose no URL, port, token, or credential;
- no call enters `AmdAiDeploymentService` from the request path.

## Verification

- `pdm run pytest --direct tests/test_amd_llm_adapter.py`;
- focused TP-04 retry/stream tests;
- `pdm run check`.
