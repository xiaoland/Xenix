# -*- coding: utf-8 -*-
"""Probe 4: IH-1 — cursor description/type mapping + result-materialization cost."""
import duckdb, pandas as pd, numpy as np, time, math, datetime as dt
from decimal import Decimal
from pathlib import Path

OUT = Path(__file__).parent / "_work"
con = duckdb.connect(":memory:")

# A result set spanning the types a data.query might return
con.execute("""
CREATE TABLE t AS SELECT * FROM (VALUES
  (1, 1.5, 'a', TRUE, DATE '2024-01-01', TIMESTAMP '2024-01-01 10:00:00.123456', NULL),
  (2, CAST('nan' AS DOUBLE), NULL, FALSE, NULL, NULL, NULL),
  (3, CAST('inf' AS DOUBLE), 'b', NULL, DATE '2024-01-03', TIMESTAMP '2024-01-03 11:00:00', NULL)
) v(i, f, s, b, d, ts, n)
""")

print("=== cursor.description (name, str(type), python type) ===")
cur = con.execute("SELECT i, f, s, b, d, ts, n, 123456789012345678 AS big FROM t")
for name, typecode, *_ in cur.description:
    print(f"  {name:5s} -> {str(typecode)!r:28s} typecode={typecode!r}")

print("\n=== fetchall() value python types ===")
for row in cur.fetchall():
    print("  ", [type(v).__name__ + ":" + repr(v) for v in row])

print("\n=== fetch_arrow_table().to_pylist() value types ===")
arrow = con.execute("SELECT i, f, s, b, d, ts FROM t").fetch_arrow_table()
print("  arrow schema:", [(f.name, str(f.type)) for f in arrow.schema])
for row in arrow.to_pylist():
    print("  ", {k: type(v).__name__ + ":" + repr(v) for k, v in row.items()})

# Decimal / HUGEINT via explicit cast
print("\n=== DECIMAL and HUGEINT value types ===")
cur = con.execute("SELECT CAST(1.23 AS DECIMAL(18,3)) AS dec, CAST(9999999999999999999 AS HUGEINT) AS huge")
print("  description:", [(d[0], str(d[1])) for d in cur.description])
for row in cur.fetchall():
    print("  ", [type(v).__name__ + ":" + repr(v) for v in row])

# Cost: materialize N rows into records
print("\n=== result-materialization cost (LIMIT rows -> JSON-safe records) ===")
big = pd.DataFrame({"a": np.arange(100_000), "b": np.random.default_rng(0).normal(0,1,100_000), "s": ["x"]*100_000, "d": pd.to_datetime("2024-01-01")})
con.register("big", big)

def timed(label, fn, repeat=3):
    best = 1e9
    for _ in range(repeat):
        t0 = time.perf_counter(); fn(); best = min(best, time.perf_counter() - t0)
    print(f"  {label:50s} {best*1000:9.1f} ms")

def norm(v):
    if v is None: return None
    if isinstance(v, dt.datetime): return v.isoformat()
    if isinstance(v, dt.date): return v.isoformat()
    if isinstance(v, dt.time): return v.isoformat()
    if isinstance(v, Decimal): return float(v)
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): return None
    return v

for limit in (50, 1000):
    print(f"  --- LIMIT {limit} ---")
    sql = f"SELECT a, b, s, d FROM big LIMIT {limit}"
    def current():
        f = con.execute(sql).fetchdf()
        cleaned = f.astype(object).where(pd.notna(f), None)
        return cleaned.to_json(orient="records", date_format="iso")
    def via_fetchall():
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        return [{c: norm(v) for c, v in zip(cols, row)} for row in cur.fetchall()]
    def via_arrow():
        return con.execute(sql).fetch_arrow_table().to_pylist()
    timed("current: fetchdf + astype + to_json", current)
    timed("proposed: fetchall + dict build + norm", via_fetchall)
    timed("alt: fetch_arrow_table().to_pylist()", via_arrow)
