# Workstream 03 — Agent Tool and Skill

## Product Contract

Expose Knowledge Base evidence through one atomic tool, `knowledge.lookup`. The model
asks a business-language query; the service owns keyword/semantic/hybrid selection.
Optional document IDs narrow scope and `top_k` is bounded. Results contain stable
citation/document/unit IDs, title, locator, and a bounded quote.

The tool is available only when the user has enabled Knowledge for the canonical
conversation. Tool advertisement and execution both enforce that state. Activating a
Skill does not grant access.

## Skill Contract

`xenix-knowledge-retrieval` is short and methodology-only:

- use it when the user asks to apply saved organizational knowledge or experience;
- begin with one compact business query and refine only when essential evidence is
  missing;
- cite evidence actually used and do not treat ranking as truth;
- distinguish what a knowledge source claims from what current data proves;
- activate the data-analysis Skill as well when calculation is required;
- say when evidence is absent instead of inventing it.

The Skill contains no retrieval-engine jargon, case recipes, hidden authorization, or
large reference bundle.

## Verification

The rainy-season restock case in ../../11-agent-benchmark-cases.md is the executable
product gate. The promotion-reuse case is a future candidate pending a typed result
oracle. Unit tests additionally cover advertised/execution scope, bounded output,
empty results, document filtering, canonical ToolResult replay, and coexistence with
data Skills.
