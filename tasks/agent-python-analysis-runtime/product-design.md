# Product Design

## Product Claim Draft

Xenix should not expose "run arbitrary Python" as a user-facing Agent superpower. It should expose an analysis-native capability where the Agent can write a small, typed Python function against registered datasets, then return bounded evidence that Xenix can render, save, and audit.

The product value is not code execution itself. The value is allowing the Agent to answer business questions whose exact analytical procedure is not known ahead of time.

## First-Principles Framing

Data analysis has three layers:

1. Evidence access: load registered datasets, inspect columns, filter rows, aggregate values.
2. Analytical procedure: choose transformations, comparisons, derived metrics, tests, and visuals.
3. Communication: explain what changed, why it matters, and what decision it supports.

Current operation orchestration is strong at layer 1 and stable parts of layer 2. It becomes weak when layer 2 needs custom composition, local judgment, or one-off business definitions.

## Candidate MVP: `analysis.lambda`

Working name only.

Input shape:

- registered dataset bindings, not local paths
- declared parameters with JSON schema
- declared output contract
- optional natural-language analysis objective
- code body shaped as one function, not a script

Execution shape:

- read-only dataset access through a Xenix context object
- no arbitrary filesystem paths
- no network access
- bounded runtime, memory, rows, output size, and artifact count
- cancellation through Agent Harness
- every successful output becomes structured tool payload and/or registered artifact
- MVP does not require user approval before execution

Output shape:

- the lambda returns one JSON-serializable `dict`
- `analysis.lambda` returns that value through `result.output`
- the `dict` may include Markdown strings, scalar metrics, bounded table-like records, warnings, and artifact references
- generated charts or files are created through an exposed artifact creation API, then referenced from Markdown by `artifact://...`

## User Experience Proposal

MVP should present the run as "Agent generated an analysis function" rather than "Agent ran a script".

Suggested flow:

1. Agent explains the intended analysis in plain language.
2. The function runs inside a managed analysis runtime after schema/runtime validation.
3. Results appear as normal assistant evidence through `result.output`.

MVP explicitly does not include a user approval step. This makes runtime guardrails mandatory rather than optional.

## Product Boundaries

In scope for MVP:

- registered CSV/XLS/XLSX datasets already known to the thread
- pandas/numpy-style data analysis
- derived metrics, custom groupings, cohorts, simple statistical comparisons, and bounded charts/tables
- read-only analysis and artifact creation
- one-off execution only; generated lambdas are not saved as reusable operations

Out of scope for MVP:

- arbitrary local file reads/writes
- network access
- package installation
- long-running training jobs
- mutation of source datasets
- production automation or scheduled recurring runs
- generic notebooks
- user-authored plugin marketplace semantics
- saved/reusable lambda operations

## Product Risk

The main risk is false confidence plus unreviewed execution. A flexible runtime will let the Agent produce analyses that look precise but encode questionable assumptions, and MVP no longer relies on a human approval gate. MVP should make assumptions visible in output and require runtime validation before execution.

No-approval MVP should still be positioned as a bounded analysis tool, not as a trusted automation engine.

MVP threat posture:

- protect against accidental bad Agent code: syntax/runtime errors, infinite or long-running execution, oversized output, non-serializable return values, artifact overproduction, and unsupported API usage
- do not claim protection against hostile code intentionally trying to escape the runtime, access arbitrary local files, or bypass subprocess limits
