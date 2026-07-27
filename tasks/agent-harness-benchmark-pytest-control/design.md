# Pytest-Controlled Benchmark Design

## Boundary

`benchmarks/agent_harness` is an explicit evaluation surface, not a second
ordinary test suite. A case module owns an open-ended business request and its
final-outcome oracle. `_infra` owns only reusable execution, metrics, bounded
judge dispatch, persistence, and the pytest fixture that starts a cell.

```text
pdm benchmark command
        |
        v
pytest collection / -k selection
        |
        v
case test module ─────> agent_harness_benchmark fixture
                                  |
                                  v
                       generic isolated cell runner
                                  |
                   +--------------+--------------+
                   |                             |
              subject metrics               case final outcome
                   |                             |
                   +------------> persisted result
```

The CLI neither parses benchmark cases nor owns a model loop. It only gives
pytest a target path and the explicit live switch.

## Outcome Semantics

Pytest failure means the benchmark infrastructure could not provide a usable
measurement: no cells, failed persistence, invalid setup, runtime error, or
measurement error. A completed cell with a semantic `pass`, `partial`, `fail`,
or `inconclusive` remains a successful pytest item because it is an observation
about the subject, not a framework assertion.

## Deliberate Non-Coverage

The offline suite does not recreate one unit test per case, inspect Tool
arguments, or restate facts that schemas, type checking, fixture validation, or
the component's own tests already establish. Its only job is dynamic generic
behavior that would otherwise be invisible before a paid run.
