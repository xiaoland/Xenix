# Data Analysis Demand Map

## What Issue 98 Already Covers

`tasks/issue-98/common-descriptive-analysis.py` covers a broad descriptive pass:

- row/field counts and duplicate rows
- field dtype, missingness, non-null counts, cardinality
- numeric, binary, categorical, and datetime grouping
- numeric descriptive statistics
- value frequencies
- datetime ranges
- correlation matrix
- keyword-detected target fields for grouped statistics
- Excel report export

This is a strong baseline for "what is in this dataset?" and "what obvious summaries can be computed?".

Its limits as an Agent-facing contract:

- hard-coded local file path
- hard-coded Excel output
- keyword heuristics for target fields
- no registered dataset boundary
- no bounded output contract for conversation rendering
- no explicit assumptions or warnings
- no user-provided business objective beyond implicit column names

Issue-98's later service direction already resolved much of this baseline into two deterministic tools:

- `analysis.profile`: bounded descriptive evidence over one registered dataset, returned as structured payload plus Markdown.
- `analysis.graph`: bounded graph operation over one registered dataset, returned as registered image artifact metadata.

So the new runtime should avoid competing with issue-98. It should target analytical procedures whose shape cannot be known before the user asks the question.

## Where Rigid Operation Orchestration Works Well

- dataset preview and schema inspection
- common descriptive profile
- standard chart operations
- deterministic data cleaning operations
- SQL-style filtering, joining, grouping, and materialized transforms
- standard model training, tuning, application, and task querying

These have stable semantics and clear validation rules.

## Where Rigid Operation Orchestration Becomes Weak

### Business Metric Construction

Examples:

- "active customer" varies by industry and company policy
- revenue recognition can depend on refunds, taxes, discounts, channel, and time window
- retention, churn, reactivation, and LTV definitions are rarely universal

Why fixed operations fail: the schema would either become too generic to help or too large to remain usable.

Concrete Xenix implication: this is a better fit for an analysis lambda than for expanding `analysis.profile` with keyword heuristics.

### Cohort And Funnel Analysis

Examples:

- first purchase cohort by acquisition channel
- quote-to-order conversion with custom stage ordering
- repeat purchase within 30/60/90 days

Why fixed operations fail: event ordering, windowing, entity identity, and edge cases are business-specific.

Concrete Xenix implication: SQL can compute many of these, but a typed lambda can combine window logic, derived columns, validation warnings, and final presentation in one reviewable analysis unit.

### Hypothesis-Driven Exploration

Examples:

- "Did the promotion help only in some regions?"
- "Which customer segment explains the margin drop?"
- "Is the spike caused by volume, price, mix, or missing data?"

Why fixed operations fail: good analysis often branches after seeing intermediate evidence.

Concrete Xenix implication: the Agent needs enough procedural flexibility to compute intermediate evidence, but every execution should still declare final outputs and assumptions.

### Derived Feature And Segmentation Logic

Examples:

- custom RFM score
- customer health score
- product lifecycle buckets
- exception categories based on multiple fields

Why fixed operations fail: the useful logic is often a compact custom expression or multi-step classification, not a pre-existing operation.

### Data Quality Investigation

Examples:

- suspicious duplicates based on fuzzy keys
- inconsistent units or currencies
- impossible date sequences
- category drift across periods

Why fixed operations fail: checks need to be invented from domain context and local data evidence.

### Small Statistical Comparisons

Examples:

- before/after comparison with custom exclusions
- group difference with sample-size warnings
- correlation conditioned on a segment

Why fixed operations fail: statistical procedure, filtering, and caveats must align with the business question.

### Narrative Analysis Assembly

Examples:

- combine SQL result, profile, chart, and a custom variance decomposition into one answer
- produce an executive summary with traceable supporting tables

Why fixed operations fail: the value is in composing evidence, not in any single operation.

Concrete Xenix implication: Markdown-only profile output is useful evidence, but not enough for "send this to my manager" deliverables. The lambda design should leave room for report artifacts after the MVP.

### Cross-Dataset Comparison And Reconciliation

Examples:

- compare this month vs last month exports with slightly different schemas
- reconcile sales orders against invoices
- explain differences between two vendor reports

Why fixed operations fail: matching keys, tolerance rules, and exception categories are domain-specific.

Concrete Xenix implication: this may require `data.integrate`, `data.query`, or `data.transform` before a lambda. The lambda MVP should support multiple registered dataset bindings, even if the first implementation caps row count and dataset count tightly.

## Useful MVP Target

The best MVP target is not "all Python". It is "custom read-only analysis procedure over registered datasets, with typed outputs and visible assumptions".

That target should focus on:

- business metrics
- cohorts/funnels
- custom segmentation
- variance decomposition
- targeted data-quality checks
- hypothesis-driven slices that need intermediate calculations

It should not focus on:

- replacing `analysis.profile`
- replacing `analysis.graph`
- replacing SQL query/transform
- arbitrary automation
- production ML training
