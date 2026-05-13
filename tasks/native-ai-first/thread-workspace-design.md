# Thread Workspace Design

## Status

- Mode: Explore.
- Scope: decide whether first slice needs a workspace entity beyond thread.

## Current Decision

First slice uses `Thread` as the LLM workspace.

Old UI exits the target path immediately, and `WorkItemService` exits the target service topology.

Agent Harness owns the Thread domain:

- conversation history as Messages
- turns
- user intent
- uploaded file references
- tool calls and tool results
- artifact references

This is enough to replace the earlier WorkItem workspace proposal in the first slice.

## First-Slice Working Context

First slice uses messages, tool-call records, tool-result records, and artifacts as the working record.

Agent Harness may build an ephemeral working-context projection for provider calls or tool execution, but the first slice does not add structured domain state for derived dataset, feature selection, best model, or prediction refs.

Those facts are represented by tool results and artifact records. Later slices can promote repeated derived facts into structured state if the message/tool/artifact record becomes insufficient.

## Tool Contract Implication

First-slice tools do not need `work_item_id`.

They operate in the current thread and accept explicit artifact/dataset/model ids when needed.

## Open Questions

- Exact shape of the ephemeral working-context projection.
- How much context is injected into each LLM provider call.
