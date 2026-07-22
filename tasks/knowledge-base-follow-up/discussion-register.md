# Knowledge Base Follow-up Discussion Register

Use this register for additional issues raised by Sir. A reported concern is not
silently converted into a defect or repair; first identify its owner and evidence.

| ID | Concern | State | Disposition / next evidence |
| --- | --- | --- | --- |
| KB-D01 | `knowledge.lookup` response exposes IDs and locator details that do not help the Agent. | Confirmed | Replace with the single minimal result in `tool-result-contract.md`; no hidden second result. |
| KB-D02 | Splitting model evidence and provenance into two result planes violates Unit TDD. | Confirmed | Proposal rejected. One direct Tool value remains the only canonical/replay/UI semantic result. |
| KB-D03 | The invalid proposal suggests other implementations may not respect technical design documents. | Confirmed for multiple Knowledge changes | Compliance matrix records confirmed deviations and gaps. Continue auditing each new concern against its owning contract rather than generalizing without evidence. |
| KB-D04 | Earlier “goal complete” conclusion was based on functional tests and benchmark success. | Withdrawn | Engineering completion remains unproven until confirmed contract deviations are repaired and their delivery boundaries verified. |
| KB-D05 | Does the current Knowledge Base support vector or hybrid retrieval? | Phase B implementation verified | With an enabled independent Embedding profile, semantic uses an immutable LanceDB exact-flat cosine generation and hybrid fuses it with SQLite FTS by deterministic RRF. Disabled/unavailable capability remains honest. Frozen delivery is still Phase F evidence. |
| KB-D06 | Is `knowledge.lookup` itself sufficiently simple, direct, and useful without relying on a Skill? | Phase B recheck verified | The Tool explains when to search and how to combine excerpts with current-data evidence; input remains only `query/mode?`, output remains resolved mode plus small source excerpts, and real mode readiness adds no index plumbing. |
| KB-D07 | Is Knowledge retrieval integrated into data-analysis methodology rather than isolated as its own Skill? | Phase A sub-scope verified | Data analysis owns the full method; preprocessing/modeling carry local rules; the standalone Knowledge Skill was removed while `knowledge.lookup` remains common scope. Phase G still performs system acceptance. |
| KB-D08 | May the Agent select retrieval mode explicitly? | Phase B verified | Optional `mode = auto | keyword | semantic | hybrid` defaults to `auto` and reports the resolved mode. Explicit unready modes fail; only expected `auto` unavailability falls back to fresh keyword retrieval. |
| KB-D09 | What should an Agent benchmark grade? | Decided and re-verified in Phase B infrastructure | Grade terminal Assistant content and public Datasets/Artifacts/charts. The semantic case may request a mode and expose diagnostic telemetry, but Tool Calls and ToolResults cannot satisfy semantic success. |
| KB-D10 | What is the correct follow-up slice granularity? | Corrected | KB-F01..F17 plus accepted follow-up decisions form Slice 01. Agent, retrieval, storage, import, runtime/UI, and delivery are internal phases—not seven slices. |
| KB-D11 | Does the implemented import format set still match Sir's explicit MVP promise? | Resolved and verified | One format registry now admits TXT, DOC/DOCX, PDF, JPEG, and PNG; JPEG/PNG have signature/pixel/OCR-or-picture routes and PPT/PPTX are rejected. Workspace copy and tests use the same registry. |
| KB-D12 | Does Phase B pass with the newly configured real Embedding provider? | Confirmed outcome gap | A finite 1024-dimensional probe and 72 focused tests passed. Two live `kimi/kimi-k2.6` cells then produced the exact Dataset and passed all integrity checks, but both failed `grounded_final_answer`. Diagnose the terminal-answer/oracle boundary without awarding semantic credit from Tool telemetry. |
| KB-D13 | May Slice 01 close while the stable final-answer failure is recorded for later repair? | Decided by Sir | Slice 01 closed on 2026-07-22. The failure remains explicit and is carried into Slice 02 as `KB2-F01`; closure does not rewrite the two cells as passing. |
| KB-D14 | Should Knowledge imports execute like ML tasks in an independent process with inspectable logs? | Implemented and locally verified | One spawned process owns heavy work for one attempt; the parent retains SQLite/publication authority. Import Queue opens content-free bounded `logs.jsonl` through a service DTO. |
| KB-D15 | Should the Knowledge Workspace body list Knowledge content? | Implemented and locally verified | A service-backed table lists logical documents only, with explicit empty and unavailable states. Attempts, chunks, assets, and IDs remain internal. |
| KB-D16 | Must an Embedding configuration change confirm vector-index impact? | Decided, implemented, locally verified | Confirm only compatibility-fingerprint changes when searchable content exists. API key, timeout, and batch size do not warn; save-now queues a visible rebuild and lookup never builds. |
| KB-D17 | Where should Knowledge settings live and how should the Workspace open them? | Implemented and locally verified | Knowledge Base Settings owns Embedding, OCR, and index controls. Workspace opens the one shared dialog at the stable `KNOWLEDGE_BASE` tab. |
| KB-D18 | Does Xenix support multimodal Knowledge and how should visual retrieval work? | Capability gap parked by Sir | Current behavior remains text-only over extracted/OCR text. True visual retrieval still needs visual Units, a multimodal embedding profile/generation, and an Agent-consumable evidence operation; none was implied by this slice. |
| KB-D19 | Should users be able to rebuild indexes manually? | Implemented and locally verified | The rebuild sheet selects keyword FTS and configured text vectors, gives unit/request estimates, and does not mislabel extraction/OCR as indexing. Visual vectors remain absent. |

## New-Issue Template

For each new issue, record:

1. Sir's observation in product language;
2. applicable durable owner, Unit TDD, local instruction, or accepted task decision;
3. current source/runtime evidence;
4. whether it is confirmed, contradicted, incomplete, or missing evidence;
5. user-visible or authority impact; and
6. owning phase and whether the finding invalidates its current contract; and
7. decision or next experiment. Findings outside the active phase remain discussable
   without silently expanding an authorized phase.
