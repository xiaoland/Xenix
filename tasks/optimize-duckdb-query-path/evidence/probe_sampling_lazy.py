# -*- coding: utf-8 -*-
"""Probe 5: read_csv_auto sampling mis-inference + lazy-view/LIMIT pushdown."""
import duckdb, pandas as pd, numpy as np, time
from pathlib import Path

OUT = Path(__file__).parent / "_work"
OUT.mkdir(exist_ok=True)
con = duckdb.connect(":memory:")

# 1) Sampling mis-inference: numeric for first 30000 rows, string at row 30001 (> default sample 20480)
print("=== sampling mis-inference (string beyond default sample_size=20480) ===")
p = OUT / "sample_trap.csv"
rows = ["v"] + [str(i) for i in range(30000)] + ["oops"] + [str(i) for i in range(30001, 40000)]
p.write_text("\n".join(rows), encoding="utf-8")
def describe_csv(path, extra=""):
    try:
        d = con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{path}'{extra})").fetchall()
        return str(d[0][1])
    except Exception as e:
        return "ERR " + type(e).__name__ + ": " + str(e)[:90]
print("  default sample_size:", describe_csv(p))
print("  sample_size=-1 (full scan):", describe_csv(p, ", sample_size=-1"))
# what does the full scan yield at the trap row?
try:
    r = con.execute(f"SELECT v FROM read_csv_auto('{p}') WHERE v = 'oops'").fetchall()
    print("  full scan finds 'oops' row:", r)
except Exception as e:
    print("  full scan ERROR:", type(e).__name__, str(e)[:120])

# 2) Lazy view + LIMIT pushdown
print("\n=== lazy view + LIMIT pushdown (cost.csv, 200k rows) ===")
csv_path = OUT / "cost.csv"
def timed(label, fn, repeat=3):
    best = 1e9
    for _ in range(repeat):
        t0 = time.perf_counter(); fn(); best = min(best, time.perf_counter() - t0)
    print(f"  {label:52s} {best*1000:8.1f} ms")

def create_view():
    c = duckdb.connect(":memory:")
    c.execute(f"CREATE TEMP VIEW v AS SELECT * FROM read_csv_auto('{csv_path}')")
    return c
timed("CREATE VIEW over read_csv_auto (registration)", create_view)

c = create_view()
timed("SELECT COUNT(*) FROM view (full scan)", lambda: c.execute("SELECT COUNT(*) FROM v").fetchone()[0])
timed("SELECT * FROM view LIMIT 50 (pushdown)", lambda: c.execute("SELECT * FROM v LIMIT 50").fetchdf())

# pandas current path for comparison: full read + register happens even for LIMIT 50
def pandas_register():
    c2 = duckdb.connect(":memory:")
    f = pd.read_csv(csv_path)
    c2.register("v2", f)
    return c2
timed("pd.read_csv + register (current, always full read)", pandas_register)
