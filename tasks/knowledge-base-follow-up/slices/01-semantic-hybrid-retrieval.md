# Slice 01 / Phase B — Semantic and Hybrid Retrieval

**Phase state:** local implementation/delivery verified; live Agent outcome failed twice and is carried to Slice 02
**Authorized:** research, plan, and implementation authorized by Sir on 2026-07-21

## Objective

Make `semantic`, `hybrid`, and `auto` truthful production behaviors while preserving
SQLite Knowledge Units as content authority, SQLite FTS5 as the only lexical
projection, and one small Agent-facing result. A failed or stale vector projection
must never masquerade as a valid semantic result.

This phase also keeps the corrected Agent benchmark boundary: grade the final answer
surface, not Tool Calls, ToolResults, retrieval mode, IDs, or scores.

## Research Gleanings and Decisions

Research was checked against current primary sources on 2026-07-21:

- [LanceDB Python 0.34.0 on PyPI](https://pypi.org/project/lancedb/) publishes one
  CPython 3.9+ ABI3 Windows x86-64 wheel, covering Xenix's Python 3.12–3.14 range.
  This proves wheel availability, not PyInstaller delivery.
- [LanceDB vector search](https://docs.lancedb.com/search/vector-search) supports
  exact flat search without an ANN index. Phase B chooses flat cosine search for the
  MVP corpus; an ANN index needs measured scale/latency evidence first.
- [LanceDB hybrid guidance](https://docs.lancedb.com/search/hybrid-search) uses RRF by
  default and accepts explicit vectors, but Xenix will not use LanceDB FTS. SQLite's
  Chinese-pretokenized FTS5 ranking and Lance vector ranking are fused in Xenix so
  there is only one lexical projection authority.
- [The OpenAI embedding protocol](https://developers.openai.com/api/reference/resources/embeddings/methods/create)
  accepts batched strings, returns indexed float vectors, and may support an explicit
  output dimension. Xenix implements that wire shape as one initial adapter; it does
  not reuse `LLMService`, chat settings, or chat retry semantics.

## Authority Topology

```text
EmbeddingSettingsService ── frozen operation ──> EmbeddingService adapter
                                             |
SQLite current Knowledge Units ──────────────+──> KnowledgeSemanticService
        (content authority)                        | build immutable generation
                                                  v
SQLite generation metadata ── publishes ──> LanceDB generation directory
        (readiness authority)                    (derived vector bytes)

query ──> KnowledgeService
          ├─ keyword rank: SQLite FTS5
          ├─ semantic rank: KnowledgeSemanticService / LanceDB
          └─ hybrid: bounded deterministic RRF ──> current SQLite units ──> Tool
```

LanceDB never owns text, titles, locators, document activity, or readiness. A vector
hit is only a candidate `unit_id`; `KnowledgeService` resolves and revalidates the
current SQLite row before returning a match.

## Embedding Service Contract

Phase B adds an independent `embedding_settings.json` and these concepts:

- one enabled OpenAI-compatible embedding profile for the MVP;
- provider key, base URL, model, optional expected dimensions, batch size, and
  timeout;
- API key only in the user-controlled settings file, never in SQLite, LanceDB,
  errors, Tool values, logs, or fingerprints; and
- a profile fingerprint over non-secret behavior fields, including normalized base
  URL, model, requested dimensions, and adapter/preprocessing versions.

One embedding operation freezes a deep-copied, validated settings snapshot before
the first request and retains it across query and document embedding. Batched
responses must contain exactly one finite, same-sized vector for
each input and preserve response `index` ordering. Empty inputs, count mismatch,
non-finite values, mixed dimensions, and a configured-dimension mismatch fail with a
bounded domain error. Document units are character-bounded before transmission;
query and document embedding use the same text preparation version.

The UI reuses the existing AI tab's visual/settings pattern but adds an independent
Embedding card. Saving LLM settings cannot alter or rebuild embedding generations;
saving embedding settings cannot alter the selected chat model.

## Immutable Semantic Generation

Phase B adds `knowledge_vector_generation` metadata with:

```text
id
library_id
corpus_fingerprint
profile_fingerprint
provider_key
model
dimensions
distance_metric = cosine
relative_path
unit_count
created_at
```

Only a completely written, validated generation receives a SQLite row. Pending and
failed builds are not persisted as pseudo-ready rows; absence of an exact usable row
means semantic retrieval is unavailable and can be retried. This keeps MVP state
small because recovery/audit history is not the primary product goal.

`corpus_fingerprint` covers the ordered current unit IDs, document generation IDs,
and text digests for one `library_id`. `profile_fingerprint` covers embedding
behavior but no secret. Multiple libraries therefore remain a natural filter even
though only `global` is user-visible in MVP.

Each LanceDB directory is immutable and contains only `unit_id` plus a fixed-size
float vector. It is written under Knowledge staging, reopened and validated, then
atomically renamed under `artifacts/knowledge/indexes/<generation-id>`. Its bounded
manifest v1 binds the generation ID, corpus/profile fingerprints, dimensions, row
count, and an ordered-unit-ID digest. SQLite stores a path relative to the Knowledge
root. Reuse requires the literal `indexes/<generation-id>` path, an exact manifest,
and the same ordered unit IDs in the actual Lance table. Old/orphan generations are
ignored; cleanup policy remains Phase D/F work.

### Publication sequence

```text
semantic/hybrid lookup
  -> freeze one embedding operation (settings, secret, profile)
  -> snapshot current SQLite units + corpus fingerprint
  -> embed query first to discover/validate the provider's actual dimension
  -> use an exact usable generation if one exists
  -> otherwise batch-embed the snapshot through the same frozen operation
  -> write and validate isolated LanceDB staging directory
  -> atomic rename to immutable final directory
  -> re-read SQLite corpus fingerprint
     -> changed: do not publish; report unavailable to this attempt
     -> unchanged: insert ready generation metadata in one SQLite transaction
  -> cosine search for bounded candidate unit IDs
  -> resolve current SQLite units
  -> revalidate candidate corpus/profile currentness after rehydration
```

The query is embedded before generation selection because a provider-default
dimension is not known from settings alone. Query and corpus still use exactly the
same frozen operation, so a mid-call settings or credential change cannot split one
retrieval across profiles.

`KnowledgeSemanticService` owns this sequence. `KnowledgeImportService` receives no
Embedding or LanceDB dependency. Phase B may build a missing generation on the first
semantic-capable lookup. Phase E has since moved Unit/FTS publication into the
independent `KnowledgeDerivationService` after canonical-ready publication.

## Retrieval Modes

| Requested mode | Production behavior | Reported mode |
| --- | --- | --- |
| `keyword` | SQLite FTS5 only; never calls Embedding/LanceDB | `keyword` |
| `semantic` | Requires enabled profile and an exact usable generation; flat cosine rank | `semantic` |
| `hybrid` | Requires semantic readiness; fuses SQLite FTS and vector ranks even if either candidate list is empty | `hybrid` |
| `auto` | Attempts hybrid only when an embedding profile is enabled; expected semantic readiness/provider/vector unavailability falls back to a fresh keyword lookup | actual `hybrid` or `keyword` |

Explicit `semantic`/`hybrid` never silently degrade. They return the existing bounded
`knowledge_retrieval_mode_unavailable` failure with the currently usable modes.
`auto` degrades honestly and reports `keyword`; no warning field is added to the
canonical Tool value. Semantic candidate identity/currentness remains one internal
domain value, not a second result plane. Unexpected or integrity failures propagate
to the Tool's bounded generic failure instead of being mislabeled as keyword success.

## Hybrid Ranking

For each leg, fetch `candidate_k = min(32, max(20, top_k * 4))`. Fuse candidate IDs
with reciprocal-rank fusion using `k = 60` and 1-based ranks:

```text
score(unit) = sum(1 / (60 + rank_in_leg))
```

Sort by fused score descending, then best individual rank ascending, then `unit_id`
for deterministic ties. The service returns at most `top_k` current units. Scores,
vector distances, generation IDs, and profile details remain internal.

RRF is chosen over normalized raw-score mixing because SQLite BM25 and cosine
distance have unrelated scales; rank fusion is deterministic, explainable, and does
not require an unmeasured weight. Revisit only with a labelled retrieval corpus.

## Failure Preplay

| Scenario | Expected behavior |
| --- | --- |
| Lexical miss, semantic hit | `semantic`/`hybrid` returns the meaning match; `auto` resolves to `hybrid`. |
| Exact term hit | keyword remains strong; hybrid rewards a unit present in both ranks. |
| Conflicting ranks | deterministic RRF and tie-breaks; no raw-score normalization. |
| Embedding disabled | keyword works; explicit semantic/hybrid is typed unavailable; auto is keyword. |
| Empty current corpus | explicit semantic/hybrid is typed unavailable; auto returns a fresh empty keyword result. |
| Provider outage or malformed response | no generation is published; explicit modes fail safely; auto is keyword. |
| Unexpected service/integrity defect | no silent auto downgrade; the Tool emits its bounded generic failure. |
| Model/base URL/dimension changes | profile mismatch excludes old generations; a new generation is required. |
| Corpus changes during build | post-build fingerprint check rejects publication; the immutable orphan is not selected. |
| Missing/corrupt Lance directory | its metadata row is unusable; rebuild may publish a later generation; explicit mode never reads it. |
| Partial vector build | no SQLite ready row, so no partial corpus can answer semantic queries. |
| Deleted/replaced document | corpus fingerprint changes; the prior generation is stale immediately. |
| Concurrent builders | both write isolated IDs; only exact ready generations are eligible; duplicate immutable generations do not change answers. |
| Restart on Windows | vector adapter uses operation-scoped handles so directory publication is not held by app lifetime. |

## Migration Constraint

Phase B requires schema v18. The implementation replaced the mutable
`SQLModel.metadata.create_all()` behavior in v15→v16 and v16→v17 with fixed SQL for
their historical target shapes, then added one explicit v17→v18 edge. Fresh v18 and
a static v17 upgrade with ORM readability were covered at this checkpoint. Phase D
has since extended the fixed migration chain through v20 and added broader
historical/cleanup evidence; this section remains the Phase B snapshot.

## Impact Handshake

- **Address and object:** embedding settings/adapter; Knowledge semantic/vector
  services; storage layout, generation model/repository, and v18 migration; Knowledge
  retrieval/mode routing; Agent composition; AI settings UI/translations; LanceDB
  dependency/package discovery; focused tests; Phase B and durable contracts.
- **State diff:** `semantic`/`hybrid` change from typed-unavailable placeholders to
  real modes when a compatible user profile and full current generation exist;
  `auto` changes from always-keyword to truthful hybrid-or-keyword resolution.
- **Blast radius:** settings persistence/UI, database bootstrap and migration,
  Knowledge lookup latency/provider traffic, import-to-retrieval freshness,
  dependency lock, Windows native packaging, headless benchmark composition.
- **Invariants:** SQLite owns text/readiness; LanceDB is rebuildable; Import gains no
  Embedding/Lance dependency; one canonical Tool value stays minimal; explicit modes
  never fake success; auto fallback reports actual mode; credentials/raw paths never
  cross storage/Tool/log boundaries; historical ToolResults are untouched.
- **Verification:** embedding wire-contract tests; real local Lance write/close/
  rename/reopen/search spike; lexical-miss semantic-hit and deterministic RRF tests;
  stale/profile/dimension/outage/partial tests; Tool mode tests; v17→v18 and fresh
  bootstrap tests; settings UI tests; Agent composition/continuity tests; project
  check; benchmark collection and, when dedicated provider settings are supplied,
  the live final-answer case. Packaged Lance execution was a Phase F acceptance item
  and has since been exercised in the frozen Knowledge smoke.

## Implemented Sequence

1. Proved the pinned LanceDB wheel and operation-scoped Windows directory lifecycle.
2. Added independent embedding settings and a black-box-tested OpenAI-compatible
   adapter with one frozen operation boundary.
3. Fixed the minimum historical migration construction, added v18 generation
   metadata/layout, and proved static v17 upgrade plus fresh bootstrap.
4. Added the immutable Lance vector adapter, bounded generation manifest, and
   `KnowledgeSemanticService`.
5. Moved mode resolution into `KnowledgeService`; the Agent Tool remains validation,
   failure mapping, and minimal result projection only.
6. Wired one shared embedding-settings authority into production/headless composition
   and the independent AI settings card.
7. Reworked the rainy-season benchmark fixture into a lexical paraphrase, required an
   explicit semantic request, and added an external Embedding-settings seam while
   keeping its oracle exclusively on the final Dataset and Assistant answer. The
   later closeout replaced direct retrieval seeding with production Import→Derivation
   preparation.

## Verification Evidence

- The Windows/Python 3.14 spike wrote, closed, atomically renamed, reopened, and
  searched a real LanceDB generation with exact flat cosine search.
- `pdm run test tests/test_knowledge_vector_store.py tests/test_knowledge_semantic_service.py tests/test_knowledge_retrieval.py tests/test_knowledge_lookup_tool.py tests/test_embedding_service.py tests/test_agent_composition.py tests/test_settings_dialog.py tests/test_migrations.py tests/test_storage_bootstrap.py tests/test_agent_harness_benchmark_infra.py`
  — 95 passed.
- `RainySeasonRestockCase.validate_input()` accepts the pinned paraphrased fixture;
  Agent Harness collection finds all 3 live cases without provider access.
- `pdm run check` passed. Full repository verification passed all 453 non-UI tests;
  the UI phase passed 57 of 58 tests. Its only failure was the fresh-home smoke being
  unable to acquire the Windows global Xenix single-instance mutex while Sir's
  existing debug app was running; no user process was terminated.
- The benchmark result schema is v3 and records only the external Embedding settings
  SHA-256 identity, never its URL or secret. The external file is checked unchanged.
- User-controlled settings were structurally valid; a minimal real Embedding request
  returned one finite 1024-dimensional vector. The related focused suite passed 72
  tests across Embedding, Lance, semantic/hybrid retrieval, benchmark infrastructure,
  and production Agent composition.
- Two isolated live cells ran with `kimi/kimi-k2.6` and
  `qwen3.7-text-embedding`. Both completed without provider retry, invoked
  `knowledge.lookup`, created exactly one 2×2 derived Dataset with `U100→130` and
  `R200→75`, and passed canonical-completion/source/settings isolation. Both failed
  only `grounded_final_answer` (`final_answer_missing_rule_or_restock_actions`). The
  first used 18,218 tokens / 45.083 seconds; the repeat used 24,638 tokens / 61.501
  seconds. This is a stable acceptance failure, not permission to inspect ToolResult
  as semantic credit.

Phases C–G closed canonical identity, post-canonical derivation, Import
atomicity/queue ownership, packaged native proof, dynamic UI safety, and the global
Import/Storage/Tool review. Sir closed Slice 01 on 2026-07-22; the failed
real-provider final-answer outcome remains explicit and is carried to Slice 02 as
`KB2-F01` for later diagnosis, repair, and an independent rerun.
