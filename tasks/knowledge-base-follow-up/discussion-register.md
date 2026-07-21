# Knowledge Base Follow-up Discussion Register

Use this register for additional issues raised by Sir. A reported concern is not
silently converted into a defect or repair; first identify its owner and evidence.

| ID | Concern | State | Disposition / next evidence |
| --- | --- | --- | --- |
| KB-D01 | `knowledge.lookup` response exposes IDs and locator details that do not help the Agent. | Confirmed | Replace with the single minimal result in `tool-result-contract.md`; no hidden second result. |
| KB-D02 | Splitting model evidence and provenance into two result planes violates Unit TDD. | Confirmed | Proposal rejected. One direct Tool value remains the only canonical/replay/UI semantic result. |
| KB-D03 | The invalid proposal suggests other implementations may not respect technical design documents. | Confirmed for multiple Knowledge changes | Compliance matrix records confirmed deviations and gaps. Continue auditing each new concern against its owning contract rather than generalizing without evidence. |
| KB-D04 | Earlier “goal complete” conclusion was based on functional tests and benchmark success. | Withdrawn | Engineering completion remains unproven until confirmed contract deviations are repaired and their delivery boundaries verified. |
| KB-D05 | Does the current Knowledge Base support vector or hybrid retrieval? | Confirmed: no | Only CJK-prepared SQLite FTS5 keyword lookup exists. Semantic/hybrid is required in Slice 01 Phase B; typed unavailability is only the preceding checkpoint behavior. |
| KB-D06 | Is `knowledge.lookup` itself sufficiently simple, direct, and useful without relying on a Skill? | Resolved in Slice 01 | The Tool now explains when to search and how to combine excerpts with current-data evidence; input is only `query/mode?`, and output is resolved mode plus small source excerpts. |
| KB-D07 | Is Knowledge retrieval integrated into data-analysis methodology rather than isolated as its own Skill? | Resolved in Slice 01 | Data analysis owns the full method; preprocessing/modeling carry local rules; the standalone Knowledge Skill was removed while `knowledge.lookup` remains common scope. |
| KB-D08 | May the Agent select retrieval mode explicitly? | Interface implemented; engine pending | Optional `mode = auto | keyword | semantic | hybrid` defaults to `auto` and reports the resolved mode. Unready modes fail explicitly; real semantic/hybrid behavior is Slice 01 Phase B. |
| KB-D09 | What should an Agent benchmark grade? | Decided: final answer surfaces | Grade terminal Assistant content and public Datasets/Artifacts/charts. Tool Calls and ToolResults are diagnostic telemetry only and cannot satisfy semantic success. |
| KB-D10 | What is the correct follow-up slice granularity? | Corrected | KB-F01..F16 plus accepted follow-up decisions form Slice 01. Agent, retrieval, storage, import, runtime/UI, and delivery are internal phases—not seven slices. |

## New-Issue Template

For each new issue, record:

1. Sir's observation in product language;
2. applicable durable owner, Unit TDD, local instruction, or accepted task decision;
3. current source/runtime evidence;
4. whether it is confirmed, contradicted, incomplete, or missing evidence;
5. user-visible or authority impact; and
6. owning phase and whether the finding invalidates its current contract; and
7. decision or next experiment. Findings outside the active phase remain discussable
   without delaying already-authorized work inside Slice 01.
