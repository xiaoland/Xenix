# -*- coding: utf-8 -*-
"""Direct IH-4 verification: exercise _register_binding branches without query()'s tempdir."""
import duckdb, pandas as pd
from pathlib import Path
from xenix.config import get_app_paths
from xenix.services.data_transform import DataQueryTransformService, DatasetSqlBinding
from xenix.exceptions import ValidationError

ws = Path(__file__).parent / "_verify"
ws.mkdir(exist_ok=True)

service = DataQueryTransformService(get_app_paths())

def binding(p):
    return DatasetSqlBinding(alias="input", dataset_id="d1", source_path=str(p.resolve()))

# 1) parquet binding registers + queries numerically
con = duckdb.connect(":memory:")
p = ws / "nums.parquet"
pd.DataFrame({"value": [1, 2]}).to_parquet(p)
schema = service._register_binding(con, binding(p), relation_name="input", temp_dir=ws)
print("parquet schema tool_names:", [c.tool_name for c in schema.columns])
val = con.execute("SELECT SUM(value) AS total FROM input").fetchone()[0]
print("parquet SUM:", val)
assert val == 3

# 2) xlsx binding registers + queries
x = ws / "rows.xlsx"
pd.DataFrame({"label": ["a", "b"]}).to_excel(x, index=False)
schema2 = service._register_binding(con, binding(x), relation_name="input2", temp_dir=ws)
val2 = con.execute("SELECT COUNT(*) AS n FROM input2").fetchone()[0]
print("xlsx COUNT:", val2)
assert val2 == 2

# 3) csv binding is rejected
c = ws / "nums.csv"
c.write_text("value\n1\n2\n", encoding="utf-8")
try:
    service._register_binding(con, binding(c), relation_name="input3", temp_dir=ws)
    raise SystemExit("expected ValidationError for CSV binding")
except ValidationError as e:
    print("csv rejected:", str(e))

print("ALL OK")
