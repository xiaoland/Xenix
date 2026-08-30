# ML Service Guidance

## Scope

Applies only to native ML execution under `src/xenix/services/ml/`.

## Tripwires

- Keep worker runners, pools, and adapters as execution helpers. Do not move task lifecycle branching or artifact finalization into this subtree; those cross-unit contracts are owned by [Product TDD](../../../../docs/20-prd-tdd/README.md).
- Keep process entrypoints top-level and `spawn`-compatible so packaged Windows execution does not depend on an external Python CLI or inherited process state.
- Keep registry metadata typed and provider/UI-facing parameter schemas shallow and predictable. Do not expose nested machinery without an explicit consumer contract.
- Evaluation policy belongs in `src/xenix/services/ml/evaluation.py`; change it with focused evaluation and execution tests.
- Do not restate cross-worker authority, no-failover behavior, local finalization, or artifact/storage meaning here.

Verify affected paths in `tests/ml/test_ml_execution.py` and `tests/ml/test_ml_registry.py`.
