# Source Notes

## Polars Documentation Notes

Checked current Polars Python API through Context7.

Relevant facts:

- Local `polars==1.42.1` `read_excel` supports `sheet_name` / `sheet_id`, engines including `calamine`, `openpyxl`, and `xlsx2csv`, `schema_overrides`, `infer_schema_length`, `read_options`, `engine_options`, `has_header`, and `columns`.
- Local `polars==1.42.1` `read_excel` does not accept a top-level `n_rows` argument, but `engine="calamine"` accepts `read_options={"n_rows": N}`. On the case XLSX, `read_options={"n_rows": 5}` returned shape `(5, 50)` with Polars placeholder names such as `__UNNAMED__1`.
- Not every option belongs in `read_options`: for local `calamine`, `read_options={"has_header": False}` fails, while `has_header=False` is a top-level `read_excel` argument.
- `polars.read_csv` supports `has_header`, `new_columns`, `schema_overrides`, `infer_schema`, and `infer_schema_length`.
- When CSV `has_header=False`, Polars autogenerates `column_x` names.
- With the `xlsx2csv` engine, Excel reading can pass CSV `read_options`, including `has_header=False` and `new_columns`.
- Polars docs recommend increasing `infer_schema_length`, scanning all rows, or using `schema_overrides` when schema inference is wrong.

Interpretation:

- Polars exposes useful controls, but its generated placeholder names are still adapter output.
- Xenix should not rely on Polars placeholder names as a product contract.
- The thin wrapper can use Polars controls when useful, then publish Xenix-owned `tool_name` values.
- For large XLSX structure row windows, `calamine` plus `read_options={"n_rows": N}` is a valid bounded load and aligns with Polars loader names. It is not necessarily the cheapest structural probe: the real 486k-row XLSX still took about 19.3s for `n_rows=5`, while the existing openpyxl/reset-dimensions metadata path is better for cheap physical row/window evidence.

## pandas Documentation Notes

Checked current pandas docs through Context7.

Relevant facts:

- pandas generates `Unnamed: n` names for empty headers.
- pandas disambiguates duplicate headers with suffixes such as `.1` / `.N`.
- explicit `names` are supported, but duplicate names are not permitted.

Interpretation:

- pandas placeholder and duplicate suffix behavior is also adapter output, not a business fact.
- The wrapper should detect these names at the loader edge and convert them into Xenix schema facts.
- `pd.read_excel(..., dtype=str)` is a viable local mitigation for mixed header/data rows before DuckDB registration: a 5-row sample from the case file keeps `销售数量` as string instead of forcing a numeric column that later rejects the header-like row.

## Local Asset Script Notes

Inspected scripts under `tasks/ml-service-optimizations/assets`.

Potentially useful patterns:

- Some scripts use `read_engine=auto`: try Polars first, fall back to pandas for compatibility.
- Config files separate `selected_columns`, `exclude_columns`, `target_columns`, and detection rules, which supports our decision not to mix names and indexes in one ambiguous field.
- Scripts emit field/encoding explanation artifacts, which reinforces that preprocessing decisions need traceability.
- Several scripts include column classification heuristics for modeling readiness, such as ID-like, date-like, name-like, long-text, high-cardinality, and target-like fields.

Not directly reusable for Phase 1:

- The scripts assume ordinary business column names are already available.
- They do not provide a general loader schema contract for messy exported spreadsheets.
- Their modeling-oriented semantic heuristics should not be pulled into `data.peek` structure detection.

Conclusion: learn the separation of config, field traceability, and read fallback pattern; do not hard-copy the semantic preprocessing heuristics into the loader/schema boundary.
