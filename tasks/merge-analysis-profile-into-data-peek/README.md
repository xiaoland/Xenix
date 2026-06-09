# Merge analysis.profile into data.peek

## Objective & Hypothesis

Merge the Agent-facing `analysis.profile` tool behavior into `data.peek` behind an `analysis` boolean parameter, defaulting to enabled. Keep `AnalysisProfileService` as the deterministic descriptive-analysis owner.

## Guardrails Touched

- Agent tool registry and provider-facing schema.
- Dataset registration and inspection tool result payload.
- Agent Harness contextual tool exposure expectations.
- Product/unit TDD text for tool boundaries.

## Verification

- Targeted unit tests around analysis profile service/tool behavior.
- Targeted Agent Harness exposure/schema tests.
- Compact test run after implementation if dependency/runtime permits.
- Verified with project virtualenv:
  - `.venv\Scripts\python.exe -m pytest tests/test_analysis_profile.py`
  - `.venv\Scripts\python.exe -m pytest tests/test_agent_harness_first_slice.py`
  - `.venv\Scripts\python.exe -m pytest tests/test_data_cleaning.py -k "data_clean_tool_schema_stays_compact"`
  - `.venv\Scripts\python.exe -m pytest tests/test_agent_harness_streaming.py -k "stream_filters_tools_by_thread_files or stream_rejects_provider_tool_call_that_was_not_exposed"`
  - `.venv\Scripts\python.exe -m compileall src tests`

## Current Understanding

Implemented as: remove the Agent-facing `analysis.profile` registry entry, add `analysis` plus profile controls to `data.peek`, and have `_data_peek` call `AnalysisProfileService` after registration/inspection when enabled. `analysis` defaults to `true`; `analysis=false` returns only registration and inspection output.

## Next Step

No further local step pending.
