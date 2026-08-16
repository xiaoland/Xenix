# Impact Handshake O4-A3 — Cleaning Tool and Skill Authority

**Status:** Consumed; implementation verified and paid-characterized on 2026-08-11. The route-minimality target missed because every valid cell retained a broad result query.

## Evidence Trigger

Retained O4 runs prove two independent planning ambiguities after service correctness and result facts are repaired:

1. neither the Provider schema nor the Tool description says that `data.clean.operations` execute strictly left-to-right against the preceding operation's frame;
2. the preprocessing Skill routes generic row filters to `data.transform` even when an advertised atomic `data.clean` validation operation already owns that filter.

The direct recipes also omit `text.lowercase` and `validation.non_negative`, forcing otherwise unnecessary metadata discovery.

## Address and Object

- `CleaningOperationInput` and `DataCleanInput` Provider-schema descriptions;
- `data.clean`, `data.clean.metadata`, and `data.transform` Tool descriptions;
- the canonical `xenix-data-preprocessing` Skill plus `references/preprocessing-tools.md`;
- generated Skill catalog;
- provider-free schema/Skill contract tests;
- task-local ignored retained-run adapter and three paid exact cleaning-case characterizations;
- task-packet evidence and execution records.

No cleaning service semantics, O4-A2 result projection, benchmark prompt/oracle, Agent Harness budgets, Provider settings, model selection, or general SQL capability changes are authorized.

## State Diff

- **From:** operation ordering is implicit; `filter` points to `data.transform`; common lowercase/non-negative operations appear unfamiliar; one exact request may validly branch through query, metadata, transform, or multiple derived Datasets.
- **To:** Tool schema and Skill state that operations execute strictly left-to-right on the current intermediate frame. Supported atomic validation is the cleaning owner for row rejection; `data.transform` is reserved for filters/predicates without an atomic cleaning operation, joins, derivations, reshaping, aggregation, or grain changes. Lowercase and non-negative rejection are direct recipes.

## Authority Rules

1. Use `analysis.profile` as the default structural/quality evidence.
2. Use one focused `data.query` only when a business decision requires values absent from the bounded profile.
3. If `data.clean` advertises an atomic operation for the requested cleaning, use it in the same ordered call.
4. `validation.non_negative`, `validation.min`, `validation.max`, `validation.not_null`, `validation.allowed_values`, and `validation.regex` own their supported row checks/actions.
5. Use `data.transform` for unsupported predicates or for relational/derived-data semantics; it remains fully available and unchanged.
6. Use metadata only for unfamiliar operation names or parameters not covered by direct recipes.

## Invariants

- Operation order remains an execution fact enforced by the service, not a prompt-only invention.
- Column-index invalidation boundaries remain unchanged and explicitly override the one-call preference.
- User confirmation remains required where dropping business-significant records is not already authorized.
- `data.transform` remains the owner for joins, aggregates, reshaping, grain changes, and unsupported predicates.
- Agent benchmarks remain outcome-first and do not prescribe Tool traces; route minimality is an O4 diagnostic measurement.
- The paid ablation uses the same fixture, case, model, budgets, and semantic/integrity oracle as the historical characterization.

## Verification

1. Provider schema mechanically contains the left-to-right/current-frame contract at `operations` and nested operation fields.
2. Tool descriptions mechanically distinguish atomic cleaning filters from unsupported SQL predicates.
3. Generated Skill catalog contains the versioned direct recipes and authority rule.
4. Existing service and Tool projection tests remain green; no result rows re-enter Agent context.
5. Full tests, check, smoke, packet links, and diff checks pass.
6. Three retained paid runs are assessed by semantic/integrity outcome first, then exact SQLite Tool order, Dataset lineage, rounds, tokens, and elapsed time.

## Paid Acceptance Target

- 3/3 semantic and integrity pass;
- one source descendant and one `data.clean` result Dataset per run;
- no `data.transform`, broad raw-row query, or `data.clean.metadata`;
- median fill `21` and validation effects grounded from the clean result;
- median sampling rounds no greater than 5, with all hard budgets unchanged.

A target miss is valid evidence, not permission to weaken the outcome oracle or add another optimization in this slice.
