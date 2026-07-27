# Retrieval and Agent Contract

## Lookup Is One Agent Tool

Retrieval belongs behind `knowledge.lookup`, not hidden prompt injection or a
provider-specific RAG extension. The Tool is common scope because Knowledge is a
supporting capability inside data work; Skill activation neither grants nor removes
authority.

Input is deliberately small:

```json
{"query":"Which seasonal assumptions should guide this sales analysis?","mode":"auto"}
```

`mode` is optional and accepts `auto`, `keyword`, `semantic`, or `hybrid`. Library,
document filters, result count, index generation, rank-fusion constants, and current
readiness are service-owned until a real Agent operation justifies exposing them.

## One Bounded Canonical Result

```json
{
  "mode":"hybrid",
  "results":[
    {
      "source":"Q3 field journal",
      "location":"page 4",
      "excerpt":"bounded evidence excerpt"
    }
  ]
}
```

The result omits query echo, score, library/document/generation/artifact/unit/citation
IDs, raw locator, path, URI, and index detail. `location` is optional: current
derivation uses an honest page anchor where present and otherwise a passage label.
An empty result is still successful and reports the mode actually used.

There is exactly one semantic result plane. `LLMConversationService` persists this
direct value; provider replay and Chatbot presentation copy it unchanged. Internal
Knowledge identities remain execution state and cannot later enrich canonical
history. Historical richer results remain immutable and replay in their original
shape.

## Retrieval Behavior

| Requested mode | Contract |
| --- | --- |
| `keyword` | Chinese-pretokenized SQLite FTS5 only; never calls Embedding/Lance |
| `semantic` | independent Embedding operation + current immutable Lance exact-cosine generation |
| `hybrid` | deterministic RRF over FTS and vector candidates |
| `auto` | attempts hybrid when configured; falls back only for expected semantic unavailability and reports the executed mode |

Explicit semantic/hybrid requests never silently degrade. Stale, partial, wrong-
profile, wrong-library, dimension-mismatched, or corrupt vector generations are not
eligible. The Tool description states when user knowledge is useful and how to
combine source claims with facts computed from current data without mentioning index
plumbing.

## Conversation Sequence

```text
Agent Tool Call
  -> registry validates advertised JSON Schema
  -> KnowledgeService retrieves current Units read-only
  -> Tool projects one bounded path-safe value
  -> Conversation persists that exact value
  -> provider replay and Chatbot copy it unchanged
```

No raw document, image bytes, absolute path, provider secret/payload, index dump, or
unbounded evidence crosses the Tool boundary. Unexpected exceptions become a generic
bounded Tool failure; useful domain failures are explicit typed values.

## Analysis Method and Evaluation

The three data Skills teach the Agent to retrieve user-specific rules, definitions,
assumptions, or experience when they may change computation/interpretation; separate
source claims from current-data facts; and explain conflicts or missing evidence.
There is no standalone Knowledge Skill.

Agent benchmarks grade terminal Assistant content and public Dataset/Artifact/chart
deliverables. Tool Calls, ToolResults, mode, IDs, scores, and excerpts are diagnostics
only. The rainy-season case imports its rule through production
Import→Canonical→Derivation, then requires the exact restock Dataset and a grounded
final answer. Two real-provider Phase B cells produced the exact Dataset and passed
integrity but failed grounded final-answer wording; repair and rerun are the only
remaining Slice 01 acceptance work.

See the [follow-up single-result contract](../knowledge-base-follow-up/tool-result-contract.md)
and [Agent Tool workstream](workstreams/03-agent-tool/README.md).
