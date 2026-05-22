# Pytest Temp Cleanup Execution

## Objective & Hypothesis

- Objective: Remove the post-success Windows `PermissionError` emitted by pytest temp symlink cleanup.
- Hypothesis: The warning is caused by pytest's default `%TEMP%/pytest-of-<user>/pytest-current` directory symlink cleanup on Windows. Supplying a unique per-run `--basetemp` under a dedicated system-temp directory avoids that symlink path.

## Pre-Execution Restatement

- Target: `pdm run test` and direct wrapper-driven pytest execution.
- Current state and context: `pdm run pytest tests/test_build_info.py -q` passes tests but emits an ignored `PermissionError` at process exit while unlinking `%TEMP%/pytest-of-yyh/pytest-current`.
- Operation: Add a pytest wrapper that injects a unique `%TEMP%/xenix-native-pytest-runs/<timestamp>-<pid>` basetemp unless the caller explicitly supplies one.
- Scope included: PDM test command, wrapper script, task evidence.
- Scope excluded: Business code, Qt lifecycle code, SQLite engine disposal, existing local ACL-damaged temp directories.
- Invariants: Callers can still pass normal pytest arguments; explicit `--basetemp` remains respected.
- Likely affected files: `pyproject.toml`, `scripts/run_pytest.py`, this task packet.
- Uncertainty: Existing broken temp directories still require one-time local cleanup if tools traverse them directly.

## Guardrails Touched

- Test tooling boundary: pytest invocation behavior changes only through the PDM `pytest` and `test` scripts.
- Local artifact boundary: generated test temp roots stay under a dedicated system temp directory and outside pytest's default `pytest-of-<user>` symlink root.

## Plan

1. Add `scripts/run_pytest.py`.
2. Point `pdm run pytest` and `pdm run test` at the wrapper.
3. Verify targeted pytest execution no longer emits the Windows temp symlink cleanup `PermissionError`.

## Verification

- Command: `pdm run pytest tests/test_build_info.py -q`
- Observed before change: `4 passed`, followed by `PermissionError: [WinError 5] Access is denied: 'C:\\Users\\yyh\\AppData\\Local\\Temp\\pytest-of-yyh\\pytest-current'`.
- Command: `pdm run pytest tests/test_build_info.py -q --basetemp=.tmp/pytest-clean-check-20260522`
- Observed before change: `4 passed`, no cleanup exception.
- Command: `pdm run test -- tests/test_build_info.py -q`
- Observed: `4 passed`, no `%TEMP%/pytest-of-yyh/pytest-current` cleanup exception.
- Command: `pdm run pytest tests/test_build_info.py -q`
- Observed: `4 passed`, no `%TEMP%/pytest-of-yyh/pytest-current` cleanup exception.
- Command: `pdm run pytest tests/test_agent_harness_streaming.py::test_agent_harness_stream_filters_tools_by_thread_files -q`
- Observed: `1 passed`, no cleanup exception.
- Command: `pdm run pytest -q`
- Observed: `131 passed in 114.12s`, no cleanup exception.

## Promotion Notes

- Durable truth candidates: The project PDM `pytest` and `test` entry points should avoid pytest's default Windows temp symlink.
- Keep in task only: Broken historical local directories `.pytest-tmp`, `codex_pytest_tmp`, `.tmp/pytest`, and `%TEMP%/pytest-of-yyh/pytest-current` are machine-local cleanup debt.
