# Loader Wrapper Boundary

## Purpose

Loader-specific quirks should be contained near the loader, not spread into Agent Harness, data tools, SQL services, or preprocessing skills.

Examples of loader-specific facts:

- pandas empty-header names such as `Unnamed: 1`;
- pandas duplicate-name suffixes such as `.1` / `.N`;
- Polars/calamine placeholder names such as `__UNNAMED__1`;
- engine-specific dtype inference behavior;
- engine-specific row/column dimension behavior.

These are not business facts. They are adapter facts.

## Boundary Shape

Introduce or evolve a thin tabular loader/schema resolver boundary that returns a service-owned structure, roughly:

```json
{
  "frame": "<dataframe or lazy handle>",
  "schema": {
    "columns": [
      {
        "index": 0,
        "tool_name": "品项销售明细",
        "source_name": "品项销售明细",
        "loader_name": "品项销售明细",
        "name_source": "preserved_source_name"
      },
      {
        "index": 1,
        "tool_name": "column_2",
        "source_name": null,
        "loader_name": "Unnamed: 1",
        "name_source": "generated_loader_placeholder"
      }
    ],
    "resolver_version": 1
  }
}
```

The wrapper owns:

- recognizing known loader placeholders;
- detecting duplicates and unstable names;
- generating canonical `tool_name` values;
- choosing the conservative read/register shape needed for downstream execution, especially string-preserving spreadsheet reads when exported report rows mix labels and values;
- renaming the loaded frame to canonical names before downstream use;
- preserving loader/source names as evidence.

Downstream services own:

- tool argument validation;
- SQL validation;
- query/transform execution;
- provider-facing projection;
- user-facing assistant composition.

Downstream services should not inspect raw loader naming conventions. LLM-facing tool results should normally expose only the executable Xenix column name, column position, and bounded samples. Loader names, source names, and name-generation reasons are internal diagnostics unless a specific repair path proves the LLM needs them.

## Polars/Pandas Notes

Polars provides stable controls that can support wrapper-owned naming:

- CSV can read without headers and generate `column_x` names.
- CSV supports `new_columns` to rename immediately after parsing.
- Excel with `xlsx2csv` can pass CSV `read_options` such as `has_header=False` and `new_columns`.
- Excel/calamine exposes schema and `schema_overrides`, but observed placeholder names are still loader output, not a Xenix contract.

pandas behavior also supports wrapper-owned naming:

- empty headers produce `Unnamed: n` style names;
- duplicate headers are automatically suffixed to keep labels unique;
- explicit `names` require uniqueness.

Conclusion: use loader APIs as input mechanics, but make Xenix `tool_name` the contract.

## Rule

The wrapper should translate loader facts into Xenix facts once. Everything past that boundary should speak Xenix's schema language, not pandas or Polars dialect.
