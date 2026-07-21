# Corrected `knowledge.lookup` Contract

## Governing Rule

There is exactly one semantic result of a Tool invocation: the bounded direct value
returned to `LLMConversationService`. That same value is persisted as the canonical
ToolResult, encoded for provider replay, and copied into Chatbot projection. Static
presentation labels may describe activity but may not enrich or reconstruct evidence.

Knowledge repository rows and retrieval candidates are domain state used while
executing the Tool; they are not a second conversation result and cannot be used to
repair or enrich canonical history later.

## Agreed MVP Shape

Input:

```json
{
  "query": "华东雨季的雨具补货规则",
  "mode": "auto"
}
```

Canonical result:

```json
{
  "mode": "keyword",
  "results": [
    {
      "source": "华东备货规则",
      "location": "第 3 页",
      "excerpt": "雨具目标库存按三周平均需求计算……"
    }
  ]
}
```

`mode` is optional on input and defaults to `auto`; accepted values are `auto`,
`keyword`, `semantic`, and `hybrid`. The result reports the strategy actually used so
an `auto` call is intelligible. Until semantic/vector indexing is implemented,
explicit `semantic` or `hybrid` requests return one typed Tool failure with the
currently available modes; they must never fall back silently or claim success.

- `auto` selects the best currently ready mode;
- `keyword` matches explicit words and phrases;
- `semantic` matches meaning when wording differs; and
- `hybrid` combines term and meaning evidence.

`location` is optional when no honest human-readable locator exists. Empty lookup is
`{"mode": "keyword", "results": []}`. Result count remains service-owned.

The result does not expose query echo, score, library ID, document
ID, generation ID, artifact ID, unit/chunk ID, citation alias, raw locator object,
filesystem path, or index detail. An identifier may be added later only when an
explicit user/Agent operation consumes it; it must then be added to this same
canonical result contract, not to a hidden presentation/provenance channel.

## Tool Description and Discoverability

The Tool must be independently understandable. A Skill may teach a broader workflow,
but it must not be required for the model to discover the Tool's purpose or use it
correctly. Proposed description:

> Search the user's Knowledge Library for business rules, definitions, assumptions,
> and experience relevant to the current data task. Ask in business language; choose
> a retrieval mode only when useful, and use returned source excerpts as guidance
> alongside computed data evidence.

The `query` property should explain that it is the business question, rule,
definition, or experience needed for the current task—not IDs or SQL. The `mode`
property should recommend `auto`, name the exact mode semantics, and state current
availability honestly without discussing index implementation.

Do not mention FTS5, LanceDB, embedding models, rank-fusion algorithms, or other
implementation details in the provider-facing description. `keyword`, `semantic`,
and `hybrid` are user/Agent choices; their plumbing is not.

## Skill Ownership

Knowledge retrieval is a supporting capability inside data work, not an independent
analysis goal. Its methodology belongs primarily in `xenix-data-analysis`:

1. identify whether user-specific rules, definitions, assumptions, or experience may
   change the computation or interpretation;
2. retrieve that knowledge when relevant;
3. distinguish the source claim from facts calculated from the current data; and
4. explain the conclusion or action produced by combining them, including conflicts
   or missing evidence.

Preprocessing may use knowledge for business taxonomy and meaning-sensitive cleaning;
modeling may use it for target meaning, thresholds, constraints, and interpretation.
Those Skills should carry only their local application rules. A separate
`xenix-knowledge-retrieval` Skill adds routing and activation complexity without
owning a distinct user task and should not be required by the target design.

`knowledge.lookup` remains a common advertised Tool. Skill activation neither grants
nor removes its authority.

## Benchmark Consequence

The Tool contract is verified by component and conversation-continuity tests, not by
making an Agent benchmark inspect the ToolResult. The rainy-season benchmark grades
the final exact restock Dataset, a grounded terminal answer, source immutability, and
state isolation without requiring a `knowledge.lookup` call or any particular result
payload. Insight/advice cases grade the terminal answer against bounded fixture facts
and a rubric. Tool telemetry may diagnose failure but cannot satisfy semantic success.

## Open Decisions

- How to produce concise, honest locations for DOCX/PPTX/TXT without inventing page
  numbers.
- Whether a future source-opening action justifies one actionable identity in the
  canonical value, and what typed UI behavior would consume it.

`top_k` and document filtering remain service-owned until an Agent operation shows a
concrete need. Semantic and hybrid retrieval are required in Phase B of the active
Slice 01; Phase A's typed unavailability is a checkpoint state, not the final engine.
