# Agent Harness Cleaning Efficiency

## Objective & Hypothesis

Reduce the token and round-trip cost of Agent-driven tabular cleaning without
weakening the evidence, provenance, or deterministic execution contract. The
hypothesis is that a compact, indexed cleaning-operation contract plus
conditional metadata discovery will let Kimi K2.6 choose valid cleaning calls
with fewer tool calls and substantially smaller tool-result context.

## Status

complete

## Durable Owners / Blast Radius

- `src/xenix/services/data_cleaning.py` owns cleaning-operation metadata and
  deterministic column-reference validation.
- `src/xenix/services/agent/tools.py` owns concrete data-tool definitions and
  adapters; `src/xenix/services/llm/` remains the sole tool protocol and
  canonical-message authority.
- `src/xenix/services/agent/skills/xenix-data-preprocessing/` owns Agent
  guidance; `catalog.json` is its generated projection.
- `tests/` owns executable service-boundary regression proof.

## State Diff: From -> To

- Full `data.clean.metadata` schema/example payload by default -> compact
  operation signatures with enum-advertised, per-group fault-tolerant filtering
  and only the facts required to construct a call.
- `column` / `columns` name-only cleaning parameters -> explicit,
  non-ambiguous `column_index(es)` preferred references with name fallbacks;
  mixed references reject deterministically.
- Name-only role binding and SQL access -> request-scoped zero-based index
  references for role binding, `data.query`, and `data.transform`, resolved
  against the current dataset schema without ever persisting an index as a
  durable column identity.
- Name-only `data.tokenize` selection -> request-scoped zero-based
  `text_column_index` and `id_column_indexes`, resolved against the loaded
  source frame before tokenization so reports and artifacts retain canonical
  names.
- Per-service loader/index-to-name implementations -> one tabular schema
  boundary that materializes an ordered canonical `tool_name` projection and
  resolves all operation indexes from that projection.
- Skill rule requiring metadata on every cleaning plan -> metadata only when
  the supported operation or its parameters remain uncertain.
- A post-activation full registry advertisement -> the active Skill's bounded
  tool union; the LLM registry still freezes and enforces the scope.
- Verbose repeated preprocessing instructions -> a 5,152-byte direct path
  (from 6,912 bytes) with one-query-per-response guidance and common direct
  cleaning recipes.
- Hand-written unit-level checks only -> an isolated AgentHarness service
  black-box replay that observes canonical result, tool-call count and usage
  measurements; live Kimi use remains opt-in.

## Invariants

- `LLMConversationService` remains the only canonical conversation writer and
  the LLM-owned registry remains the only Tool dispatcher.
- A source dataset is never mutated; cleaning produces a derived dataset.
- Index references use the 0-based indexes from a source-schema `data.query`
  result, not a projected result's ordinals; a call cannot mix index and name
  forms for one field.
- A role-binding index resolves to the current dataset's canonical column name
  before persistence; SQL index aliases exist only inside the one query or
  transform execution that requested them.
- `data.tokenize` accepts exactly one text selector and at most one identifier
  selector form; indexes are never persisted or emitted as durable columns.
- Loader-specific names (for example pandas `.1` and Polars
  `_duplicated_0`) never escape the tabular boundary as executable column
  identity; canonical application is position-safe.
- Tool results retain bounded executable facts and never expose paths,
  credentials, or raw local-runtime evidence.
- The composition root may project tool advertisements and request hints, but
  it never gains conversation-writing or tool-dispatch authority.
- Default test runs do not contact an external provider or read a production
  database/configuration.

## Decisions Consumed

- `ledger/canonical-columns.md`: executable names remain the durable authority;
  indexes are an explicit separate reference channel.
- `ledger/tool-results-boundary.md`: canonical bounded result payload is the
  authority; provider presentation is a projection, not a second truth.

## Open Questions

- Whether long-history deterministic tool-result masking earns its additional
  boundary complexity is deferred until the compact contract and replay
  measurements are available.
- Dynamic Tool Search is not justified with the current small tool registry;
  it remains a future option if the exposed surface grows materially.
- Reintroducing the historic full `analysis.profile`/`data.peek` surface is
  deferred: prior traces showed a ~28 KB result and it has no row/column or
  payload budget. A future compact profile tool would need a new bounded
  contract, not a registry switch.

## Verification Plan

1. Measure compact metadata bytes against the prior all-group metadata payload.
2. Prove index/name validation and equivalent cleaning output with service tests.
3. Run black-box Harness cases through a scripted provider, asserting tool
   protocol, final derived dataset, call count, bounded provider request size,
   and no pending canonical message.
4. Run an opt-in isolated Kimi K2.6 replay against a small workbook and record
   only aggregate request/usage/call metrics.
5. Run affected PDM tests, skill-catalog verification, compilation and diff
   checks.
6. Reproduce the U+2019/U+0027 column-name mismatch through the index forms
   for query, transform, and role binding, while preserving name-mode
   compatibility.
7. Prove tokenization index selection with a Unicode-header source and an
   AgentHarness replay, including mixed-form, invalid-index, duplicate-ID, and
   text/ID collision rejection.
8. Prove one malformed source schema yields the same ordered canonical names
   and index mapping across cleaning, tokenization, role binding, inspection,
   and SQL query/transform paths for CSV, Parquet, and XLSX where applicable.

## Verification Run Log

- 2026-07-15 baseline: read production SQLite with a read-only connection;
  second-most-recent Kimi K2.6 thread had one attachment user turn, three
  `data.query` calls, and two provider requests. No production rows changed.
- 2026-07-15 isolated live baseline: attachment-only replay issued three K2.6
  requests with input tokens 4,381 / 5,082 / 6,060 and output tokens 278 /
  386 / 531. The provider reported 4,096 cached input tokens on the latter two
  requests. The temporary runtime was removed after measurement.
- 2026-07-15 static baseline: all-group `data.clean.metadata` is about 11.2 KB
  JSON; the full exposed tool definition payload is about 12.8 KB per request.
- 2026-07-15 compact contract: all-group metadata is 3,952 bytes (the missing
  group is 1,075 bytes); column indexes are preferred, legacy names remain
  compatible, and index use after column-set-changing operations rejects.
- 2026-07-15 final static advertisement: full registry is 16 tools / 15,589
  bytes; an active preprocessing Skill is 10 tools / 8,016 bytes, saving 7,573
  bytes (48.6%) per subsequent provider request. The active Skill body is
  5,152 bytes, down from 6,912 bytes (25.5%).
- 2026-07-15 deterministic Harness replay: exactly activation, one evidence
  query, and one `data.clean` call; no metadata call; derived data and canonical
  messages verified. It records 4 provider observations totaling 2,400 input,
  768 cached input, 180 output, and 2,580 total tokens.
- 2026-07-15 isolated Kimi K2.6 final replay over
  `客户聚类模拟数据-无真实标签.xlsx`, with a four-request cap, completed
  successfully: 4 provider requests, 3 canonical
  calls (`data.query`, `data.query`, `data.clean`), no metadata call; 25,307
  input, 16,384 cached input, 1,048 output, and 26,355 total tokens. Temporary
  runtime was removed. This is a controlled trace, not a cross-prompt cost
  benchmark.
- 2026-07-15 verification: targeted suites passed; `pdm run check` passed;
  full `pdm run test -q` passed 347 tests (3 existing sklearn warnings).
- 2026-07-16 metadata group contract: provider schema advertises the nine
  valid group names as an enum; an invalid requested group returns one bounded
  `invalid_groups` entry while valid groups still return normally.
- 2026-07-16 index-reference slice: an isolated Harness replay over an XLSX
  whose source header contains U+2019 completed activation, indexed query,
  and indexed role binding without spelling that header. The query returned
  `c2`/`c5` values, while the persisted binding retained the canonical U+2019
  source name. Direct read-only replay against the historical source gave the
  same result. `pdm run test -q tests/test_agent_harness_cleaning_efficiency.py
  tests/test_data_cleaning.py tests/test_data_transform.py` passed 41 tests;
  `pdm run test -q tests/test_ml_execution.py -k column_binding` passed 7
  tests (15 deselected); `pdm run check` and `git diff --check` passed.
- 2026-07-16 tokenization index slice: `data.tokenize` accepts
  `text_column_index` and `id_column_indexes`, resolves them against the
  loaded source-frame order into canonical names, and retains names—not
  indexes—in the derived data and report. An isolated Harness replay tokenized
  an XLSX with a U+2019 header without spelling it. The service rejects mixed
  selector forms, bool/non-integer/out-of-range indexes, duplicate IDs, and a
  text/ID collision. `pdm run test -q tests/test_data_tokenization.py
  tests/test_agent_harness_cleaning_efficiency.py tests/test_data_cleaning.py
  tests/test_data_transform.py` passed 62 tests; `pdm run check` and
  `git diff --check` passed.
- 2026-07-16 final regression: full `pdm run test -q` passed 367 tests in
  206 seconds, with three existing sklearn warnings.
- 2026-07-16 canonical-column consolidation: `tabular` now owns ordered
  schema materialization, position-safe Pandas/Polars projection, strict
  index-to-`tool_name` resolution, and header-only reconciliation for
  malformed XLSX trailing cells. Import, inspection, cleaning, tokenization,
  SQL registration, role binding, and ML loading consume that boundary.
  Service-boundary regression covers CSV/Parquet/XLSX duplicate and empty
  headers, numeric XLSX headers, multi-sheet selection, malformed report
  headers, and local `cN` SQL aliases. `pdm run check` and `git diff --check`
  passed; full `pdm run test -q` passed 388 tests in 220 seconds with the same
  three sklearn warnings.

## Next Action

Complete. No new commit was created. Unrelated `tasks/knowledge-base/` and
`tests/.mock-data/` content remains untouched.
