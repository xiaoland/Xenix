# Workstream 03 — Agent Tool and Analysis Method

## Product Contract

Expose user knowledge through one atomic common-scope Tool, `knowledge.lookup`.
The model asks one business-language question and may select a truthful retrieval
mode:

```json
{"query":"华东雨季的补货规则是什么？","mode":"auto"}
```

Accepted modes are `auto`, `keyword`, `semantic`, and `hybrid`. The service—not the
Agent—owns result count, candidate bounds, library scope, current-generation checks,
ranking parameters, and fallback policy.

The only success value is:

```json
{
  "mode":"hybrid",
  "results":[
    {"source":"华东备货规则","location":"passage 1","excerpt":"……"}
  ]
}
```

It contains no query echo, scores, library/document/generation/artifact/unit/citation
IDs, raw locator, path, URI, or index detail. An actionable identity may be added
only together with a Tool/UI operation that consumes it, and must remain in this one
canonical value rather than a second provenance plane.

## Tool Description

The Tool is understandable without activating a Skill: search the user's Knowledge
Library for business rules, definitions, assumptions, and experience relevant to the
current data task; ask in business language and combine returned source excerpts with
computed data evidence. Its property descriptions explain mode meaning but never
mention FTS5, LanceDB, embedding models, or rank-fusion plumbing.

Explicit semantic/hybrid requests fail with a bounded typed result when no compatible
Embedding profile/current generation is usable. `auto` may fall back only for
expected semantic unavailability and reports the mode actually executed. The generic
Tool registry validates advertised JSON Schema before invocation and normalizes
unexpected failures without persisting paths or raw exceptions.

## Analysis-method Ownership

Knowledge retrieval is part of data analysis, not an independent user task. The
three data Skills own the method:

- analysis asks whether user-specific rules, definitions, assumptions, or experience
  could change the computation or interpretation, retrieves when relevant, and
  separates source claims from current-data facts;
- preprocessing uses business taxonomy and meaning-sensitive cleaning rules; and
- modeling uses target meaning, thresholds, constraints, and interpretation rules.

There is no standalone `xenix-knowledge-retrieval` Skill and Skill activation is not
an authorization toggle. `knowledge.lookup` remains a common advertised capability.

## Canonical-result Topology

```text
Agent Tool Call
  -> registry schema validation
  -> KnowledgeService current retrieval
  -> one minimal path-safe public value
  -> LLMConversationService canonical ToolResult
  -> provider replay copies it
  -> Chatbot projection copies it
```

Historical richer ToolResults remain immutable and replay in their original shape;
new calls use the minimal contract. No repository/UI plane enriches canonical history
later.

## Benchmark Contract

Agent benchmarks grade the terminal Assistant content and public Dataset/Artifact/
chart deliverables. Tool Calls, ToolResults, mode, IDs, scores, or excerpts are
diagnostic telemetry only and cannot satisfy semantic success.

The rainy-season case imports a paraphrased rule through production
Import→Canonical→Derivation, requests semantic retrieval, and requires an exact
restock Dataset plus a grounded action-oriented answer. Its local fixture/oracle is
verified, and the configured real LLM/Embedding run now passes both final-answer and
Dataset/integrity verdicts. Tool Calls and ToolResults remain diagnostics only.

## Verification

- exact Tool schema and unknown/type/enum/bound rejection;
- keyword/semantic/hybrid/auto success and honest failure/fallback behavior;
- bounded path-safe source/location/excerpt projection, including query-centered
  lexical excerpts;
- production Import→Derivation→Tool→Conversation persistence/reopen/provider/UI
  continuity and shape-preserving historical replay;
- Skill catalog and data-method assets; and
- benchmark collection/oracle isolation with no ToolResult semantic assertions.

See the [single-result contract](../../../knowledge-base-follow-up/tool-result-contract.md)
and [Slice 01 closeout](../../../knowledge-base-follow-up/slices/01-phases-c-g-closeout.md).
