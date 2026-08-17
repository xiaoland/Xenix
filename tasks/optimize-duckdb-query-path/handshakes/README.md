# Impact Handshake Index

Each handshake authorizes one bounded `From -> To` state diff. Evidence from [findings](../evidence/findings.md) superseded the original IH-1/IH-2 and redirected the work to IH-3/IH-4.

| ID | Intended scope | Status |
| --- | --- | --- |
| [`IH-1`](IH-1-pandas-roundtrip.md) — remove pandas round-trip | Replace `fetchdf()` + pandas `to_json` result materialization with cursor materialization | superseded (win ≈1.6–3.6 ms; visible type-string change) |
| [`IH-2`](IH-2-csv-direct-scan.md) — CSV bindings scan via DuckDB | Register CSV bindings as `read_csv_auto` views | superseded (dead path + correctness hazards) |
| [`IH-3`](IH-3-connection-reuse.md) — reuse the in-memory connection | Reuse a thread-local `:memory:` connection across `query()`/`transform()` calls, with temp-object teardown | proposed |
| [`IH-4`](IH-4-dead-code-cleanup.md) — remove dead CSV binding path | Remove `DataQueryTransformService`'s CSV fallback and unreachable helpers; move the smoke query to parquet | consumed |

Each detailed handshake contains: Address and Object, State Diff, Blast Radius, Invariants, Verification, prerequisite Evidence IDs, status, and return-to-discussion triggers.
