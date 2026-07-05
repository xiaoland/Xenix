# XLSX Attachment Import Diagnosis

## Objective & Hypothesis

Diagnose why `assets/4月堂食销售数据.xlsx` contains visible data but Xenix attachment import reports `Dataset file must contain at least one data row.`

Hypothesis confirmed: the attachment metadata path trusts workbook dimension metadata from `openpyxl`, but this workbook declares `<dimension ref="A1"/>` even though rows and columns exist beyond `A1`.

## Guardrails Touched

- Owner: `DatasetService` / `dataset_inspection` source-file inspection boundary.
- No production code mutated during diagnosis.
- UI remains a consumer of service validation; UI parsing is not involved.

## Evidence

- File: `tasks/ml-service-optimizations/assets/4月堂食销售数据.xlsx`
- Zip XML: `xl/worksheets/sheet1.xml` declares `<dimension ref="A1"/>`.
- `openpyxl.load_workbook(..., read_only=True).active.max_row == 1`
- `openpyxl.load_workbook(..., read_only=True).active.max_column == 1`
- After `worksheet.reset_dimensions()`, the first 50 iterated rows expose 50 columns and non-empty rows.
- `inspect_attachment_metadata_file(path)` reproduces `ValidationError: Dataset file must contain at least one data row.`
- `inspect_dataset_file(path)` succeeds through the Polars/calamine tabular path with `row_count=486122`, `column_count=50`.

## Current Understanding

The error is a false negative in the lightweight XLSX attachment metadata inspector, not proof that the workbook is empty.

Relevant implementation:

- `src/xenix/services/dataset_inspection.py::_inspect_xlsx_attachment_metadata`
- It computes `row_count_with_header = int(worksheet.max_row or 0)`.
- It then computes `row_count = row_count_with_header - 1`.
- Because this file reports `max_row == 1`, `row_count` becomes `0`, triggering the validation error.

## Verification

Commands run from repository root:

- Opened workbook with `openpyxl` and printed sheet names, active sheet, `max_row`, `max_column`, and first rows.
- Called `inspect_attachment_metadata_file(path)` and `inspect_dataset_file(path)` directly under `.venv\Scripts\python`.
- Read the XLSX zip member `xl/worksheets/sheet1.xml` and confirmed the stale dimension marker.

## Next Step

Completed for the minimal fix:

- `_inspect_xlsx_attachment_metadata` now treats one-row or one-column worksheet dimensions as suspicious.
- Suspicious XLSX attachments reset worksheet dimensions only for bounded header/column sampling.
- Full row count comes from streaming the active worksheet XML and counting row tags, avoiding full dataframe load and avoiding full openpyxl row decoding.
- Regression test added for an XLSX whose worksheet XML declares `<dimension ref="A1"/>` while data rows exist.

Verification:

- `.\.venv\Scripts\pytest tests\test_services.py` -> 13 passed.
- Real file `assets/4月堂食销售数据.xlsx` attachment metadata check -> `row_count=486122`, `column_count=50`, elapsed about 2.34 seconds.
- Real file through `DatasetService.register_dataset_attachment()` with temporary app home -> dataset id created, `row_count=486122`, `column_count=50`, elapsed about 2.17 seconds.

Deferred:

- Report-style workbooks whose real header starts after title/filter rows still need a separate design. The current fix intentionally only prevents false empty-row rejection.
