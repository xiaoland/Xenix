# Contextual Tool Gating

## Objective & Hypothesis

- Objective: reduce per-turn provider input overhead by exposing only context-relevant agent tools.
- Hypothesis: Xenix can keep the same durable data-analysis capabilities while omitting data tools until files are attached, omitting training tools until a column selection exists in the visible thread context, and omitting apply until a trained model exists in the visible thread context.

## Guardrails Touched

- Typed input: Constraint. Product capability stays the same; provider request construction becomes more selective.
- Durable owner: `src/xenix/services/agent/` provider orchestration in Agent Harness. The tool registry remains a static capability directory.
- Blast radius: agent provider requests, tool choice behavior, streaming and non-streaming harness paths, tests that use fixture registries.
- Invariants:
  - Registered tool handlers and execution validation remain unchanged.
  - `AgentToolRegistry.list_specs()` remains a static full registry listing.
  - Hidden system messages and conversation history semantics remain unchanged.
  - Step continuation must compute the same availability from persisted thread attachments and messages.
  - Guard provider requests do not receive business tools.
  - Provider tool calls must target tools attached to the same provider request before persistence or execution.

## Verification

- Added focused tests that inspect tools sent to provider calls for:
  - no attached file: no `data.*` tools
  - attached file: `data.*` tools are available
  - prior thread attachment without a current-turn file: `data.*` tools remain available
  - selected binding in thread context: `model.train` and `model.hyper_train` become available
  - trained model in thread context: `model.apply` becomes available
- Added hard-intercept tests for provider tool calls that were not attached to the request.
- Added a static registry assertion that `AgentToolRegistry.list_specs()` still returns the full capability set.
- Ran `.\.venv\Scripts\python.exe -m pytest tests/test_agent_harness_first_slice.py -q`.
  - Result: 13 passed.
  - Note: pytest emitted a Windows temp symlink cleanup `PermissionError` after the passing result.
- Ran `.\.venv\Scripts\python.exe -m pytest tests/test_agent_harness_streaming.py -q`.
  - Result: 12 passed.
  - Note: same Windows temp symlink cleanup `PermissionError` after the passing result.
- Ran `.\.venv\Scripts\python.exe -m pytest tests/test_agent_harness_foundation.py -q`.
  - Result: 8 passed.
  - Note: same Windows temp symlink cleanup `PermissionError` after the passing result.
