# -*- coding: utf-8 -*-
"""Probe 7: duckdb.connect cost drivers + reuse feasibility."""
import duckdb, time, threading

def timed(label, fn, repeat=7):
    best = 1e9
    for _ in range(repeat):
        t0 = time.perf_counter(); fn(); best = min(best, time.perf_counter() - t0)
    print(f"  {label:52s} {best*1000:8.2f} ms")

timed("connect(':memory:') default", lambda: duckdb.connect(":memory:").close())
timed("connect(':memory:') autoload=false", lambda: duckdb.connect(":memory:", config={"autoload_known_extensions": "false"}).close())
timed("connect(':memory:') autoload+autoinstall=false", lambda: duckdb.connect(":memory:", config={"autoload_known_extensions": "false", "autoinstall_known_extensions": "false"}).close())

# reuse: one connection, execute a trivial query per call
con = duckdb.connect(":memory:")
timed("reused conn: execute SELECT 1 (amortized)", lambda: con.execute("SELECT 1").fetchone())

# temp object collision on reuse
con.execute("CREATE TEMP VIEW v AS SELECT 1 AS x")
try:
    con.execute("CREATE TEMP VIEW v AS SELECT 2 AS x")
    print("  CREATE TEMP VIEW again: OK (no collision)")
except Exception as e:
    print("  CREATE TEMP VIEW again: COLLISION ->", type(e).__name__, str(e)[:80])
try:
    con.execute("CREATE OR REPLACE TEMP VIEW v AS SELECT 2 AS x")
    print("  CREATE OR REPLACE TEMP VIEW: OK")
except Exception as e:
    print("  CREATE OR REPLACE: FAILED ->", type(e).__name__, str(e)[:80])

# enumerate temp objects for teardown
print("  temp tables:", con.execute("SELECT table_name, table_type FROM duckdb_tables() WHERE schema_name='temp'").fetchall())
print("  temp views:", con.execute("SELECT view_name FROM duckdb_views() WHERE schema_name='temp'").fetchall())

# thread-local check
tl = threading.local()
def worker():
    if not hasattr(tl, "con"):
        tl.con = duckdb.connect(":memory:")
    return tl.con.execute("SELECT 42").fetchone()
print("  thread-local reuse works:", worker())
