# Implementation Slices

## Slice 1 — Ownership and Import Topology

Move the benchmark package to `benchmarks/agent_harness`, place reusable code
in `_infra`, turn each case into one `test_*.py` module, and remove the CLI case
registry. Add the repository root to pytest's explicit import path and include
`benchmarks` in compile verification.

Status: completed.

## Slice 2 — Pytest Control Surface

Install a local plugin through `conftest.py`. It provides only the live gate,
external settings/model/judge/source/output options, a case-agnostic runner
call, and a bounded terminal summary. Replace the old argparse runner with a
thin adapter into the existing PDM pytest wrapper.

Status: completed.

## Slice 3 — Dynamic Regression Boundary

Replace case self-tests with a small offline file for generic judge privacy,
failure classification, matrix continuation, metrics folding, persistence, and
real pytest collection/gating. Update local and durable guidance.

Status: completed.
