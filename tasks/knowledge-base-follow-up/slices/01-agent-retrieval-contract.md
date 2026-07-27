# Slice 01 / Phase A — Agent Retrieval Contract and Analysis Methodology

**Phase state:** verified checkpoint; Slice 01 remains in progress
**Authorized:** 2026-07-21 by Sir

## Objective

Make Knowledge retrieval a small, independently understandable supporting capability
inside data work. Stabilize one canonical ToolResult, expose honest mode selection,
integrate the method into the existing data Skills, and prove the production
composition persists/reloads/replays/projects that same value.

## Phase Scope

- Verify the Phase A sub-scope of KB-F01, KB-F15, and KB-F16.
- Verify the Phase A sub-scope of KB-F13 with deterministic production-composition continuity evidence.
- Verify the Knowledge Tool portions of KB-F10 and KB-F12: no raw locator/path in its
  result or error, and undeclared arguments are rejected.
- Stabilize the interface-only part of KB-F14. Semantic execution, vector projection,
  and rank fusion continue in Phase B of the same Slice 01.

## Impact Handshake

- **Agent API:** `knowledge.lookup` changes from `query/document_ids/top_k` to
  `query/mode?`; its success changes from internal identities to
  `mode/results[{source, location?, excerpt}]`.
- **Failure API:** unavailable explicit modes and invalid calls return one typed,
  bounded Tool failure. Unexpected Knowledge errors use a safe generic message and
  never persist `str(exc)`.
- **Conversation data:** no migration and no rewrite. Old canonical ToolResults remain
  immutable and replay in their historical shape; new calls use the new shape.
- **Skills:** remove the standalone Knowledge Skill; add its methodology to analysis
  and small context-specific rules to preprocessing/modeling. Knowledge remains a
  common advertised Tool, not permission granted by Skill activation.
- **Benchmark:** Tool-result shape is proven by component/continuity tests. Product
  benchmarks grade final answer surfaces and do not use ToolResults as semantic
  evidence.
- **Deferred at this historical checkpoint:** storage schemas, import lifecycle, real
  vector/hybrid retrieval, Knowledge Workspace UI, OCR deployment, packaging
  exercises, and generic exception normalization for unrelated Tools. Phase B has
  since implemented the vector/hybrid item; the others retain their later owners.

## Target Contract

Input:

```json
{"query":"华东雨季的雨具补货规则","mode":"auto"}
```

Success:

```json
{
  "mode":"keyword",
  "results":[
    {"source":"华东备货规则","location":"page 3","excerpt":"雨具目标库存按三周平均需求计算……"}
  ]
}
```

`location` is omitted when the internal locator cannot be projected to an honest,
bounded human-readable label. No query echo, score, IDs, raw locator, path, URI, or
index implementation detail crosses the Tool boundary.

| Requested mode | Phase A checkpoint behavior |
| --- | --- |
| omitted / `auto` | Resolve to the best ready mode; currently `keyword` |
| `keyword` | Execute current CJK-prepared SQLite FTS lookup |
| `semantic` | Typed `knowledge_retrieval_mode_unavailable`; no silent fallback |
| `hybrid` | Typed `knowledge_retrieval_mode_unavailable`; no silent fallback |

## Authority Topology

```text
Agent Tool Call
  -> knowledge.lookup validates its public arguments and requested mode
  -> KnowledgeService performs the currently selected retrieval
  -> knowledge.lookup projects domain matches once into the public value
  -> LLMConversationService persists that exact value
  -> provider replay encodes that value; Chatbot projection copies that value
```

Internal document/unit identities remain Knowledge-domain state during execution.
They are not a hidden ToolResult and cannot enrich a historical result later.

## Implementation Preplay

1. **Schema advertisement:** the provider sees only `query` and optional `mode`, both
   described in task language. Unknown keys, booleans, arrays, blank/oversized query,
   and unknown modes converge to `invalid_knowledge_lookup` before service access.
2. **Auto/keyword success:** lookup uses a service-owned result bound; each match is
   projected to title/source, safe page/passage location when present, and quote.
   Empty evidence is still a successful `results: []` value.
3. **Unavailable modes:** semantic/hybrid never touch keyword lookup and return the
   requested mode, currently available modes, a repair hint, and `retryable: false`.
4. **Path simulation:** a future producer supplies `{"path":"F:/private/a.pdf"}` or
   an exception contains that path. Neither string appears in success/failure output.
5. **Historical conversation:** no backfill is attempted. A pending old call carrying
   `document_ids/top_k` is rejected safely by the new implementation; persisted old
   results remain readable.
6. **Skill routing:** a normal data-analysis activation now teaches when and how to
   retrieve Knowledge. Preprocessing/modeling receive only local semantic rules; no
   fourth task Skill is advertised.
7. **Benchmark:** fixture setup imports Knowledge through the production Import and
   Derivation services; only isolated component tests may use an explicitly named
   test seeder. The oracle grades the final Assistant/Dataset/Artifact/chart
   deliverable and never freezes Tool Calls or ToolResults as a golden result.
8. **Production continuity:** build the real headless graph, assert registration,
   invoke a staged Knowledge call, reopen the conversation service on the same
   SQLite state, and verify provider replay plus Chatbot projection carry exactly the
   persisted value without reconstruction.

## Expected File Surface

- `src/xenix/services/agent/knowledge_tool.py`
- `src/xenix/services/agent/composition.py`
- `src/xenix/services/agent/skills/xenix-data-analysis/SKILL.md`
- `src/xenix/services/agent/skills/xenix-data-preprocessing/SKILL.md`
- `src/xenix/services/agent/skills/xenix-data-modeling/SKILL.md`
- `src/xenix/services/agent/skills/xenix-data-analysis/assets/analysis-plan-template.json`
- `src/xenix/services/agent/skills/xenix-data-analysis/assets/management-report-template.md`
- remove `src/xenix/services/agent/skills/xenix-knowledge-retrieval/SKILL.md`
- regenerate `src/xenix/services/agent/skills/catalog.json`
- `benchmarks/agent_harness/test_rainy_season_restock.py`
- `docs/20-product-tdd/knowledge-base-boundary.md`
- `docs/30-unit-tdd/agent-harness-benchmark.md`
- targeted tests for Tool contract, Skill catalog/scope, production composition, and
  canonical continuity

## Acceptance Checks

- Tool spec is exact, independently useful, and advertises no storage selector.
- Auto and keyword calls return the same minimal success contract.
- Explicit semantic/hybrid calls fail honestly and never execute keyword fallback.
- Invalid/extra arguments and unsafe locator/exception simulations cannot leak paths.
- Default Skill catalog has only the three data task Skills, and data-analysis owns
  the combined Knowledge/data evidence method.
- Benchmark semantic oracles do not inspect Knowledge Tool Calls or ToolResults.
- A deterministic production-composition test observes one identical value at direct
  invocation, persisted snapshot, reopened snapshot, provider replay, and Chatbot
  projection.
- A historical rich Knowledge result reopens and replays byte-for-JSON-value without
  conversion to the new shape.
- Relevant tests, Skill generation/check, compile/check, and diff whitespace pass.

## Phase Closeout

Phase verified on 2026-07-21. The former claim that this closed Slice 01 was
withdrawn after Sir corrected the slice granularity.

Evidence:

- `pdm run test tests/test_knowledge_lookup_tool.py tests/test_agent_composition.py tests/test_agent_skill_catalog.py` — 26 passed after review corrections.
- `pdm run test tests/test_agent_harness_first_slice.py tests/test_llm_message_blocks.py` — 16 passed for generic single-value persistence/replay.
- `pdm run check` — Skill catalog generation/check and compile verification passed.
- `pdm run benchmark-agent-harness -- --collect-only` — all 3 live cases collected without provider access.
- Full repository verification completed the non-UI phase with 400 passed. The UI
  run passed 57 tests; its fresh-home smoke remained unverified because an existing
  `scripts/run_dev.py` process owned Xenix's Windows single-instance mutex,
  so the fresh-home smoke test could not acquire it. No user process was terminated.
- Follow-up packet relative links and `git diff --check` passed.

Review corrections made before closeout:

- separated canonical-ready from retrieval-ready in durable topology;
- described all four provider-facing modes without index implementation language;
- sanitized Windows, POSIX, relative, tilde, and URL-like source paths;
- removed the benchmark's exact excerpt/location/single-result golden payload;
- separated Knowledge claims from current-data computed evidence in Skill prose and
  analysis/report assets; and
- locked historical rich Knowledge ToolResults to shape-preserving replay.

Remaining work is intentionally routed, not hidden, into later phases of this same
Slice 01. Phase B has since implemented real semantic/hybrid execution; import,
storage, migration, OCR, UI, schema/path closure, and packaged delivery retain their
phase owners. The final Import/Storage/Tool cross-review remains mandatory before
Slice 01 can close.
