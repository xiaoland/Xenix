# -*- coding: utf-8 -*-
"""Probe 6: real data.query cost breakdown over a PARQUET binding (the production path)."""
import duckdb, pandas as pd, numpy as np, time
from pathlib import Path

OUT = Path(__file__).parent / "_work"
OUT.mkdir(exist_ok=True)

# Build a realistic parquet (200k rows), like a converted imported dataset
rng = np.random.default_rng(1)
n = 200_000
df = pd.DataFrame({
    "id": np.arange(n),
    "grp": rng.integers(0, 1000, n),
    "amount": rng.integers(0, 1_000_000, n) / 100.0,
    "flag": rng.integers(0, 2, n).astype(bool),
    "label": rng.choice(["alpha","beta","gamma","delta","epsilon"], n),
    "text": rng.choice(["lorem","ipsum","dolor","sit","amet","consectetur"], n),
    "num2": rng.normal(0, 1, n),
})
parquet = OUT / "realistic.parquet"
df.to_parquet(parquet)
print(f"parquet: {parquet.stat().st_size/1e6:.1f} MB, {n} rows")

def timed(label, fn, repeat=5):
    best = 1e9
    for _ in range(repeat):
        t0 = time.perf_counter(); fn(); best = min(best, time.perf_counter() - t0)
    print(f"  {label:46s} {best*1000:8.2f} ms")
    return best

timed("duckdb.connect(':memory:')", lambda: duckdb.connect(":memory:"))

def full_query():
    con = duckdb.connect(":memory:")
    # header-only schema read (load_tabular_schema -> read_parquet LIMIT 0 fetchdf)
    con.execute(f"SELECT * FROM read_parquet('{parquet}') LIMIT 0").fetchdf()
    # register parquet binding view
    con.execute(f"CREATE TEMP VIEW input AS SELECT * FROM read_parquet('{parquet}')")
    total = con.execute("SELECT COUNT(*) FROM input").fetchone()[0]
    cur = con.execute("SELECT * FROM input LIMIT 50").fetchdf()
    return total, len(cur)

timed("full data.query over parquet (conn+header+view+COUNT+SELECT50)", full_query)

# breakdown within one connection
con = duckdb.connect(":memory:")
timed("  header: read_parquet LIMIT 0 fetchdf", lambda: con.execute(f"SELECT * FROM read_parquet('{parquet}') LIMIT 0").fetchdf())
timed("  CREATE TEMP VIEW over read_parquet", lambda: con.execute(f"CREATE TEMP VIEW i2 AS SELECT * FROM read_parquet('{parquet}')"))
timed("  SELECT COUNT(*)", lambda: con.execute("SELECT COUNT(*) FROM i2").fetchone()[0])
timed("  SELECT * LIMIT 50 fetchdf", lambda: con.execute("SELECT * FROM i2 LIMIT 50").fetchdf())

# no double scan: COUNT + SELECT fused? measure each scan cost
timed("  SELECT COUNT(*) alone (no view cache)", lambda: con.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet}')").fetchone()[0])
