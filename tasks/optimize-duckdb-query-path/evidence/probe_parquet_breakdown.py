# -*- coding: utf-8 -*-
import duckdb, time
from pathlib import Path
OUT = Path(__file__).parent / "_work"
parquet = OUT / "realistic.parquet"
con = duckdb.connect(":memory:")

def timed(label, fn, repeat=5):
    best = 1e9
    for _ in range(repeat):
        t0 = time.perf_counter(); fn(); best = min(best, time.perf_counter() - t0)
    print(f"  {label:46s} {best*1000:8.2f} ms")

timed("CREATE TEMP VIEW over read_parquet (fresh)", lambda: con.execute(f"CREATE OR REPLACE TEMP VIEW i2 AS SELECT * FROM read_parquet('{parquet}')"))
timed("SELECT COUNT(*) over view", lambda: con.execute("SELECT COUNT(*) FROM i2").fetchone()[0])
timed("SELECT * LIMIT 50 fetchdf", lambda: con.execute("SELECT * FROM i2 LIMIT 50").fetchdf())
timed("SELECT * LIMIT 50 + to_json (result materialize)", lambda: con.execute("SELECT * FROM i2 LIMIT 50").fetchdf().astype(object).to_json(orient="records", date_format="iso"))
timed("COUNT + SELECT50 combined (no double scan)", lambda: (con.execute("SELECT COUNT(*) FROM i2").fetchone()[0], con.execute("SELECT * FROM i2 LIMIT 50").fetchdf()))
