# Data Quality Considerations

Investigate quality dimensions that affect the requested operation, using existing context, profile facts, or SQL as appropriate. This is not an ordered checklist.

- Grain and keys affect counting, joins, and duplicate removal.
- Missing values may represent absence, unknown status, or a business state.
- Numeric and date strings may need explicit conversion; identifiers may need leading zeros preserved.
- Category normalization should preserve meaningful distinctions.
- Implausible values and mixed units can distort calculations; genuine extremes are not automatically errors.
- Time gaps matter for forecasting; repeated entities and post-outcome fields matter for model evaluation.

Choose transformations according to the user's intended meaning. A completed tool report is usable evidence of its effects. Inspect further when a needed fact is missing or a reported issue changes the decision, rather than rechecking every operation. Ask about unresolved business choices, not routine execution of already requested cleaning.
