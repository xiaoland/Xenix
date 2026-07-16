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
- Index references use the 0-based indexes returned by `data.query`; a call
  cannot mix index and name forms for one field.
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

## Next Action

Complete. No commit was created; unrelated `tasks/knowledge-base/` content was
left untouched.
