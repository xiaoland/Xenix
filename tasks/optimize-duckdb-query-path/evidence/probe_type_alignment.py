# -*- coding: utf-8 -*-
"""Probe: pandas read_csv vs DuckDB read_csv_auto type inference, plus alignment options."""
import duckdb, pandas as pd
from pathlib import Path

print("duckdb", duckdb.__version__, "| pandas", pd.__version__)

OUT = Path(__file__).parent / "_work"
OUT.mkdir(exist_ok=True)

CSV = """id,zip_code,amount,price,score,ratio,label,flag,mixed,date_iso,date_us,timestamp_col,empty_num,big_int
1,001,100,10.5,3.14,0.5,alpha,true,10,2024-01-01,01/02/2024,2024-01-01 10:00:00,1,9223372036854775807
2,002,200,20.5,,,beta,false,text2,2024-01-02,01/03/2024,2024-01-02 11:00:00,,9223372036854775808
3,003,,30.0,5.5,1.5,,true,3,2024-01-03,01/04/2024,2024-01-03 12:00:00,3,9999999999999999999
"""
path = OUT / "representative.csv"
path.write_text(CSV, encoding="utf-8")

print("\n=== pandas read_csv dtypes ===")
pdf = pd.read_csv(path)
for c in pdf.columns:
    print(f"  {c:14s} -> {pdf[c].dtype}")
print("\npandas values (id, zip_code, amount, flag, date_iso, big_int):")
print(pdf[["id","zip_code","amount","flag","date_iso","big_int"]].to_dict("records"))

print("\n=== duckdb read_csv_auto DESCRIBE ===")
con = duckdb.connect(":memory:")
for row in con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{path}')").fetchall():
    print(f"  {str(row[0]):14s} -> {str(row[1])}")

print("\n=== duckdb read_csv_auto values ===")
for row in con.execute(f"SELECT id, zip_code, amount, flag, date_iso, big_int FROM read_csv_auto('{path}')").fetchall():
    print("  ", [type(v).__name__ + ":" + repr(v) for v in row])

print("\n=== read_csv_auto with auto_type_candidates=[BIGINT,DOUBLE,VARCHAR] ===")
try:
    for row in con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{path}', auto_type_candidates=['BIGINT','DOUBLE','VARCHAR'])").fetchall():
        print(f"  {str(row[0]):14s} -> {str(row[1])}")
except Exception as e:
    print("  FAILED:", type(e).__name__, e)

print("\n=== read_csv_auto all_varchar=true ===")
for row in con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{path}', all_varchar=true)").fetchall():
    print(f"  {str(row[0]):14s} -> {str(row[1])}")
print("  SUM(amount) under all_varchar:", end=" ")
try:
    print(con.execute(f"SELECT SUM(amount) FROM read_csv_auto('{path}', all_varchar=true)").fetchone())
except Exception as e:
    print("FAILED:", type(e).__name__, str(e)[:120])
