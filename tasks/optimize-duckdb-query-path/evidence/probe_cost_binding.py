# -*- coding: utf-8 -*-
"""Probe 3: current end-to-end big-int behavior via connection.register + cost of CSV binding."""
import duckdb, pandas as pd, numpy as np, time
from pathlib import Path

OUT = Path(__file__).parent / "_work"
OUT.mkdir(exist_ok=True)
con = duckdb.connect(":memory:")

print("=== current path: pandas read_csv -> register -> DESCRIBE (big_int / zip_code / amount) ===")
pdf = pd.read_csv(OUT / "representative.csv")
con.register("cur", pdf)
for row in con.execute("DESCRIBE cur").fetchall():
    print(f"  {str(row[0]):14s} -> {str(row[1])}")
print("  big_int values through register:")
print("   ", con.execute("SELECT big_int FROM cur").fetchall())
print("  zip_code through register (pandas already dropped leading zero):", con.execute("SELECT zip_code FROM cur").fetchall())

# Build a realistic medium CSV
print("\n=== cost measurement (200k rows x 8 cols) ===")
rng = np.random.default_rng(0)
n = 200_000
big = pd.DataFrame({
    "id": np.arange(n),
    "grp": rng.integers(0, 1000, n),
    "amount": rng.integers(0, 1_000_000, n) / 100.0,
    "flag": rng.integers(0, 2, n).astype(bool),
    "label": rng.choice(["alpha","beta","gamma","delta","epsilon"], n),
    "dt": np.datetime64("2024-01-01") + rng.integers(0, 365, n).astype("timedelta64[D]"),
    "text": rng.choice(["lorem","ipsum","dolor","sit","amet","consectetur"], n),
    "num2": rng.normal(0, 1, n),
})
# dates as ISO strings (pandas read_csv keeps strings, duckdb detects DATE) to mimic real CSV
big["dt"] = big["dt"].astype(str)
csv_path = OUT / "cost.csv"
big.to_csv(csv_path, index=False)
size_mb = csv_path.stat().st_size / 1e6
print(f"  csv size: {size_mb:.1f} MB, {n} rows")

def timed(label, fn, repeat=3):
    best = 1e9
    for _ in range(repeat):
        t0 = time.perf_counter(); fn(); best = min(best, time.perf_counter() - t0)
    print(f"  {label:55s} {best*1000:8.1f} ms")
    return best

# (a) current path: pandas read + register + COUNT
def current_csv():
    c = duckdb.connect(":memory:")
    f = pd.read_csv(csv_path)
    c.register("t", f)
    return c.execute("SELECT COUNT(*) FROM t").fetchone()[0]

# (b) proposed: read_csv_auto view + COUNT
def proposed_csv():
    c = duckdb.connect(":memory:")
    return c.execute(f"SELECT COUNT(*) FROM read_csv_auto('{csv_path}')").fetchone()[0]

timed("(a) pd.read_csv + register + COUNT", current_csv)
timed("(b) read_csv_auto + COUNT", proposed_csv)

# breakdown of (a): read only vs register only
c = duckdb.connect(":memory:")
timed("  pd.read_csv only", lambda: pd.read_csv(csv_path))
f = pd.read_csv(csv_path)
timed("  register(pandas frame) only", lambda: c.register("t2", f))
