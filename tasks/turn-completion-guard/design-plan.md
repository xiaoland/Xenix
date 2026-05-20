# Turn Completion Guard Design Plan

## Objective & Hypothesis

- Objective: prevent an Agent turn from ending silently when the primary LLM says it will continue an in-turn action but returns no tool call and no final result.
- Hypothesis: a minimal guard LLM pass over only the last assistant text can catch the observed failure mode without adding broad task-completion reasoning.

## Input Classification

- Intent: add a configurable guard that retries the primary LLM before ending a turn.
- Reality: latest local `xenix.db` showed a successful run whose final assistant message said it would check available classification models, while the provider returned `finish_reason=stop` and no `tool_calls`.
- Constraint: keep the slice minimal; do not infer full task completion from all messages or artifacts.

## Current Evidence

- Latest observed thread ended with assistant text: `Now let me check which classification models are available for training.`
- The latest run was persisted as `SUCCEEDED`; the turn was persisted as `ENDED`.
- The provider payload for the final assistant message ended with `finish_reason=stop`.
- No `model.metadata`, `model.train`, or `model.inference` tool call was persisted after `data.feature.select`.
- Current Harness behavior ends the turn when `provider_response.tool_calls` is empty.

## Target Behavior

- The guard runs only when the Harness is about to end a turn because the provider response has no tool calls.
- The guard is skipped when no guard model is configured.
- The guard reuses the current OpenAI-compatible provider connection and overrides only the model.
- The guard sees only the last assistant text.
- The guard returns JSON with:
  - `verdict`: `continue` or `complete`
  - `reason`: short diagnostic text for persistence
- If `verdict=continue`, the Harness persists a system `agent_message` in the current turn and retries the primary LLM.
- If `verdict=complete`, the Harness persists the guard audit row and ends the turn normally.
- The Harness allows at most two `continue` retries per turn. After that, it ends the turn normally.

## System Reminder Message

When the guard returns `continue`, persist a normal `AgentMessageKind.SYSTEM` message in `agent_message` for the active turn. It is part of the conversation history and should be included by `ThreadSnapshot.provider_messages()` on the retry and future turns.

Draft text:

```text
You appear to have stated a next action in this turn but did not complete it. Continue now by using tools or by providing the final answer. Stop only if you truly need user input.
```

## Guard Audit Storage

Add a minimal `agent_turn_completion_guard` table:

- `id`
- `turn_id`
- `attempt_index`
- `input` JSON
- `output` JSON
- `created_at`

`input` should contain the inspected last assistant text, for example:

```json
{
  "last_assistant_text": "Now let me check which classification models are available for training."
}
```

`output` should contain the parsed guard result, for example:

```json
{
  "verdict": "continue",
  "reason": "The assistant stated a next action but did not complete it."
}
```

Do not add `thread_id`, `run_id`, `source_message_id`, `raw_payload`, or standalone `assistant_text` columns in this slice.

## Durable Owner Map

- Product TDD owner: `docs/20-product-tdd/runtime-boundaries.md`
  - Update only if the guard changes the documented Agent tool/provider boundary at product-TDD level.
  - Candidate addition: turn completion guard is a Harness-owned provider-boundary safeguard, not a user-visible tool.
- Unit TDD owner: `docs/30-unit-tdd/agent-harness.md`
  - Document the guard trigger point, retry limit, system-message persistence, guard audit table, and configuration fallback.
  - Document that guard verdicts are not tool calls and do not represent task success.
- Deployment/runtime owner: `docs/40-deployment/runtime-state.md`
  - Update if the new table becomes part of durable local runtime state inspection and recovery guidance.
- Task packet owner: this file
  - Keep implementation notes and verification observations here until behavior is proven.

Durable docs should be updated in the first implementation slice if code changes proceed, because the design changes persisted conversation semantics and local schema.

## Planned Slices

### Slice 0: Solidify Contract

- Confirm final prompt wording, retry limit, and config field names before implementation.
- Decide exact settings location for guard model configuration.

Verification:

- Doc/task review only.

### Slice 1: Storage Schema

- Add `AgentTurnCompletionGuardRow`.
- Add migration from current schema version to the next version.
- Add repository/store methods for creating and listing guard audit rows as needed by tests.

Verification:

- Storage bootstrap test covers new table on fresh DB.
- Migration test or targeted schema inspection covers upgraded DB.

### Slice 2: Guard Provider Path

- Add guard model settings.
- Build a guard request using the current OpenAI-compatible provider connection with model override.
- Parse strict JSON verdicts and fail closed as `complete` on invalid output or provider error.

Verification:

- Unit tests for configured, unconfigured, invalid-output, and provider-error paths.

### Slice 3: Harness Integration

- Insert guard check at the turn-end boundary for streaming and non-streaming provider loops.
- Persist guard audit rows for every guard decision.
- Persist a system `agent_message` and retry the primary LLM when verdict is `continue`.
- Enforce max two `continue` retries.

Verification:

- Harness test where final assistant text triggers `continue`, system message is persisted, primary LLM is retried, and a tool call can then execute.
- Harness test where verdict is `complete`, turn ends normally.
- Harness test where two continues are exhausted, turn ends without infinite loop.

### Slice 4: Durable Docs

- Update `docs/30-unit-tdd/agent-harness.md` with the final behavior.
- Update `docs/20-product-tdd/runtime-boundaries.md` only if the implementation changes provider/tool boundary language enough to require product-TDD ownership.
- Update `docs/40-deployment/runtime-state.md` if local state inspection guidance should include the new table.

Verification:

- Documentation review against implementation behavior.

## Guardrails Touched

- Agent Harness owns turn lifecycle and provider loop progression.
- Conversation storage owns persisted message history and local audit records.
- System messages persisted in `agent_message` are conversation history, not transient prompts.
- Guard audit rows are diagnostic records, not user-visible assistant content.
- No implementation should start until the user explicitly says to start.

## Verification

- Targeted tests passed:
  - `pdm run pytest tests/test_storage_bootstrap.py tests/test_agent_settings.py tests/test_agent_harness_streaming.py -q`
- Full test suite passed:
  - `pdm run pytest -q`
  - Result: `97 passed`
- Initial diagnosis used read-only SQLite inspection of `AppData/Local/Xenix/State/xenix.db`.
- Local subtree rules checked:
  - `src/xenix/services/AGENTS.md`
  - `docs/40-deployment/local-state-evolution.md`
- Durable docs updated:
  - `docs/30-unit-tdd/agent-harness.md`
  - `docs/40-deployment/runtime-state.md`
  - `docs/40-deployment/local-state-evolution.md`

Note: pytest commands passed but emitted a Windows `PermissionError` from pytest temporary-directory cleanup at process exit. The test results themselves were successful.
