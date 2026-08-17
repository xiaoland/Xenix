# Evidence Index

Reproducible probes and recorded findings for this packet. Probe scripts regenerate their own inputs under `evidence/_work` (gitignored by cleanup; delete freely).

| File | Purpose |
| --- | --- |
| [`findings.md`](findings.md) | Consolidated findings, measurements, and revised recommendation |
| [`probe_type_alignment.py`](probe_type_alignment.py) | pandas vs DuckDB `read_csv_auto` type inference |
| [`probe_hugeint.py`](probe_hugeint.py) | `auto_type_candidates` HUGEINT rejection + explicit-column control |
| [`probe_cost_binding.py`](probe_cost_binding.py) | CSV binding cost + register big-int behavior |
| [`probe_roundtrip.py`](probe_roundtrip.py) | cursor description/value mapping + result-materialization cost |
| [`probe_sampling_lazy.py`](probe_sampling_lazy.py) | `read_csv_auto` sampling mis-inference + lazy-view LIMIT pushdown |
| [`probe_parquet_path.py`](probe_parquet_path.py) + [`probe_parquet_breakdown.py`](probe_parquet_breakdown.py) | production parquet `data.query` cost breakdown |
| [`probe_connect.py`](probe_connect.py) | `duckdb.connect` cost drivers, temp-object collision, thread-local reuse |
