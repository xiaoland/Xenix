# -*- coding: utf-8 -*-
"""Probe 2b: explicit-column control of CSV types (big-int + date mitigation)."""
import duckdb
from pathlib import Path

OUT = Path(__file__).parent / "_work"
path = OUT / "representative.csv"
con = duckdb.connect(":memory:")

def show(label, sql):
    print(f"\n=== {label} ===")
    try:
        for row in con.execute(sql).fetchall():
            print(f"  {str(row[0]):14s} -> {str(row[1])}")
    except Exception as e:
        print("  FAILED:", type(e).__name__, str(e)[:200])

# Does columns= act as full schema (auto_detect=false) or as override (auto_detect=true)?
show("read_csv columns={big_int:HUGEINT} auto_detect=true (override only?)", f"DESCRIBE SELECT * FROM read_csv('{path}', columns={{'big_int':'HUGEINT'}}, auto_detect=true, header=true)")

show("read_csv columns={big_int:HUGEINT} auto_detect=false (full schema required?)", f"DESCRIBE SELECT * FROM read_csv('{path}', columns={{'big_int':'HUGEINT'}}, auto_detect=false, header=true)")

# Can we override just the types that pandas got differently, leaving the rest to auto-detect?
# pandas 3.0.3 produced: id int64, zip_code int64, amount float64, price/score/ratio float64,
#   label str, flag bool, mixed str, dates str, empty_num float64, big_int uint64
full_schema = "{'id':'BIGINT','zip_code':'BIGINT','amount':'DOUBLE','price':'DOUBLE','score':'DOUBLE','ratio':'DOUBLE','label':'VARCHAR','flag':'BOOLEAN','mixed':'VARCHAR','date_iso':'VARCHAR','date_us':'VARCHAR','timestamp_col':'VARCHAR','empty_num':'DOUBLE','big_int':'HUGEINT'}"
show("read_csv columns=<full pandas-mirror schema> auto_detect=false", f"DESCRIBE SELECT * FROM read_csv('{path}', columns={full_schema}, auto_detect=false, header=true)")
print("  big_int exact?", con.execute(f"SELECT big_int FROM read_csv('{path}', columns={full_schema}, auto_detect=false, header=true)").fetchall())
print("  zip_code (pandas dropped leading zero -> BIGINT):", con.execute(f"SELECT zip_code FROM read_csv('{path}', columns={full_schema}, auto_detect=false, header=true)").fetchall())
